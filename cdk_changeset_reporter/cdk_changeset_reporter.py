from typing import NamedTuple
import aws_cdk.cx_api as cx_api
import botocore
import boto3
import datetime
from dateutil.tz import tzlocal
from terminaltables import GithubFlavoredMarkdownTable as Table
import logging


class StackInfo(NamedTuple):
    name: str
    role_arn: str
    region: str


class CdkChangesetReporter:
    """
    Collects and prints CFN changeset information for one or more stacks in a Cloud Assembly folder.
    The CFN changeset information is accessed using each stack's CDK lookup role as defined in the Cloud Assembly entry for the stack.

    Usage:
        reporter = CdkChangesetReporter("/path/to/cloud_assembly_dir")

        # then either:
        reporter.add_stacks("staging")
        reporter.add_stacks("base")
        # to select all stacks in the cloud assembly:
        # reporter.add_stacks("*")
        changes = reporter.gather_changes()
        reporter.report(changes)

        # or, in one go
        reporter.gather_and_report("staging")


    """

    def __init__(
        self,
        *,
        change_set_name: str,
        cloud_assembly_dir: str = "cdk.out",
        log_level: str = "INFO",
    ) -> None:
        """

        :param change_set_name: The name of the Cloudformation changeset to look for
        :param cloud_assembly_dir: Path to the Cloud Assembly dir, defaults to "cdk.out"
        :param log_level: Log level, defaults to INFO
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(log_level)
        logging.basicConfig()

        self.change_set_name = change_set_name
        self.reset_stack_selection()
        self.cloud_assembly = cx_api.CloudAssembly(
            cloud_assembly_dir,
            topo_sort=True,
        )

    def reset_stack_selection(self):
        self.stacks = set()

    def add_stacks(
        self,
        stack_selector: str,
    ) -> None:
        def _should_be_included(s: cx_api.CloudFormationStackArtifact) -> bool:
            return s.stack_name.startswith(stack_selector) or stack_selector == "*"

        self.logger.debug(f"Selection: {stack_selector}")

        result = [
            StackInfo(
                name=s.stack_name,
                role_arn=s.lookup_role.arn.replace("${AWS::Partition}", "aws")
                .replace("${AWS::AccountId}", s.environment.account)
                .replace("${AWS::Region}", s.environment.region),
                region=s.environment.region,
            )
            for s in self.cloud_assembly.stacks_recursively
            if _should_be_included(s)
        ]
        if not result:
            self.logger.warn(f"No stacks found using selector: {stack_selector}")
        self.logger.debug(f"Result: {result}")
        self.stacks.update(result)

    def assumed_role_session(
        self, role_arn: str, base_session: botocore.session.Session = None
    ):
        base_session = base_session or boto3.session.Session()._session
        fetcher = botocore.credentials.AssumeRoleCredentialFetcher(
            client_creator=base_session.create_client,
            source_credentials=base_session.get_credentials(),
            role_arn=role_arn,
        )
        creds = botocore.credentials.DeferredRefreshableCredentials(
            method="assume-role",
            refresh_using=fetcher.fetch_credentials,
            time_fetcher=lambda: datetime.datetime.now(tzlocal()),
        )
        botocore_session = botocore.session.Session()
        botocore_session._credentials = creds
        return boto3.Session(botocore_session=botocore_session)

    def gather_changes(
        self,
    ) -> dict[str, dict]:
        self.logger.debug(f"Assembly: {self.cloud_assembly.directory}")
        self.logger.debug(f"Changeset: {self.change_set_name}")

        changes = {}
        for stack in self.stacks:
            self.logger.debug(f"Query: {stack}")
            session = self.assumed_role_session(role_arn=stack.role_arn)
            cfn = session.client("cloudformation", region_name=stack.region)
            change_sets = cfn.list_change_sets(StackName=stack.name)["Summaries"]
            available_change_sets = [
                # TODO ensure only cdk-owned changesets?
                c
                for c in change_sets
                if c["ChangeSetName"] == self.change_set_name
                and c["ExecutionStatus"] == "AVAILABLE"
            ]
            if available_change_sets:
                changes[stack.name] = cfn.describe_change_set(
                    ChangeSetName=available_change_sets[0]["ChangeSetName"],
                    StackName=stack.name,
                )["Changes"]
        if not changes:
            self.logger.warn(f"No changesets matching {self.change_set_name} found")
        return changes

    def report(self, changes):
        for stack_name, changes in changes.items():
            print(self.generate_table(stack_name, changes))

    def gather_and_report(self, stack_selection: str):
        self.add_stacks(stack_selection)
        changes = self.gather_changes()
        self.report(changes)

    def truncate(self, max_length: int, text: str) -> str:
        if len(text) > max_length:
            text = (
                text[: int(max_length / 2 - 2.5)]
                + "(...)"
                + text[-int(max_length / 2 - 2.5) :]
            )
            return str(text)

    def generate_table(self, stack_name: str, reported_changes: dict):
        """
        Generate a table of the changes in the given stack.
        """
        changes = []
        recreate = False
        for change in reported_changes:
            # Extract the details
            details = change["ResourceChange"]["Details"]
            resource_id = change["ResourceChange"]["LogicalResourceId"]

            # Truncate the resource ID if it's too long. Do this in the middle as
            # the important parts are at the beginning and end of the string
            resource_id = self.truncate(50, resource_id)

            # Some changes have no details
            if details:
                change_target = details[0]["Target"].get("Name", "")
                change_reason = details[0]["ChangeSource"]
                requires_recreate = details[0]["Target"]["RequiresRecreation"]
            else:
                change_target = change_reason = ""
                requires_recreate = "No"

            if requires_recreate == "Always" or requires_recreate == "Conditionally":
                # If the resource requires recreation, mark the changeset as requiring recreation
                # and add a warning to the change reason
                recreate = True
                requires_recreate = f"🚨{requires_recreate}🚨"

            # Add the formatted details to the list of changes
            changes.append(
                [
                    change["ResourceChange"]["Action"],
                    requires_recreate,
                    change["ResourceChange"]["ResourceType"],
                    resource_id,
                    change_target,
                    change_reason,
                ]
            )
        # Sort by action
        changes.sort(key=lambda x: x[0])

        # Add the headings for the table
        changes.insert(
            0,
            [
                "Action",
                "Requires Recreation",
                "Resource Type",
                "Logical Resource Id",
                "Change Target",
                "Change Reason",
            ],
        )

        # Generate the table
        table = Table(changes)

        # Generate the Github flavored markdown formatting
        return f"""
<details>
<summary>Changeset for stack <strong>{stack_name}</strong>{' (🚨 resources requires recreation 🚨)' if recreate else ''}</summary>

{table.table}

</details>
"""

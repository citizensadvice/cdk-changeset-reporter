from typing import NamedTuple
import aws_cdk.cx_api as cx_api
import botocore
import boto3
import datetime
from dateutil.tz import tzlocal
import yaml


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
        reporter.add_stacks_starting_with("staging")
        reporter.add_stacks_starting_with("training")
        changes = reporter.gather_changes()
        reporter.report(changes)

        # or, in one go
        reporter.gather_and_report("staging")


    """

    def __init__(self, cloud_assembly_dir: str = "cdk.out") -> None:
        self.stacks: list[StackInfo] = []
        self.cloud_assembly = cx_api.CloudAssembly(
            cloud_assembly_dir,
            topo_sort=True,
        )

    def reset_stack_selection(self):
        self.stacks = []

    def add_stacks_starting_with(
        self,
        stack_prefix: str,
    ) -> None:
        self.stacks += [
            StackInfo(
                name=s.stack_name,
                role_arn=s.lookup_role.arn.replace("${AWS::Partition}", "aws"),
                region=s.environment.region,
            )
            for s in self.cloud_assembly.stacks_recursively
            if s.stack_name.startswith(stack_prefix)
        ]

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
        changes = {}
        for stack in self.stacks:
            session = self.assumed_role_session(role_arn=stack.role_arn)
            cfn = session.client("cloudformation", region_name=stack.region)
            change_sets = cfn.list_change_sets(StackName=stack.name)["Summaries"]
            available_change_sets = [
                # TODO ensure only cdk-owned changesets?
                c
                for c in change_sets
                if c["ExecutionStatus"] == "AVAILABLE"
            ]
            if available_change_sets:
                changes[stack.name] = cfn.describe_change_set(
                    ChangeSetName=available_change_sets[0]["ChangeSetName"],
                    StackName=stack.name,
                )["Changes"]
        return changes

    def report(self, changes):
        for k, v in changes.items():
            print(yaml.dump({k: v}))
            print()

    def gather_and_report(self, stack_selection: str):
        self.add_stacks_starting_with(stack_selection)
        changes = self.gather_changes()
        self.report(changes)

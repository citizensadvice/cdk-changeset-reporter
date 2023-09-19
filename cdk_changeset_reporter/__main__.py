from argparse import ArgumentParser
from .cdk_changeset_reporter import CdkChangesetReporter

parser = ArgumentParser(
    prog="cdk_changeset_reporter",
    description="Pretty prints the CFN changesets of CloudAssembly stacks",
    usage="""cdk_changeset_reporter -n <changeset name> -s <stack selector>
                e.g
                    cdk_changeset_reporter -n cdk-change-set-1 -s test dev mystack
                    # or all stacks in the cloud assembly folder
                    cdk_changeset_reporter cdk-change-set-1
            """,
)
parser.add_argument(
    "-a", "--app", type=str, default="cdk.out", help="Path to the Cloud Assembly folder"
)
parser.add_argument(
    "-n",
    "--change_set_name",
    type=str,
    required=True,
    help="Name of an existing CFN changeset to report on",
)
parser.add_argument(
    "-s",
    "--stacks",
    default="*",
    nargs="+",
    help="Cloud Assembly stack selector. Accepts exact stack names, prefixes or '*' ( the default )",
)

parser.add_argument(
    "--level",
    default="INFO",
    type=str.upper,
    choices=["INFO", "DEBUG"],
    help="Log level",
)

if __name__ == "__main__":
    args = parser.parse_args()

    reporter = CdkChangesetReporter(
        cloud_assembly_dir=args.app,
        change_set_name=args.change_set_name,
        log_level=args.level,
    )
    stack_selectors = ["*"] if "*" in args.stacks else args.stacks
    for selector in stack_selectors:
        reporter.add_stacks(selector)

    changes = reporter.gather_changes()
    reporter.report(changes)

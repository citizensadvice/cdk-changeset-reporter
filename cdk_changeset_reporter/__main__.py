from .cdk_changeset_reporter import CdkChangesetReporter
from sys import argv

if __name__ == "__main__":
    if len(argv) < 2:
        raise ValueError(
            "A stage name must be provided, e.g. develop, staging, production"
        )

    reporter = CdkChangesetReporter()

    for stage in argv[1:]:
        reporter.add_stacks_starting_with(stage)

    changes = reporter.gather_changes()
    reporter.report(changes)

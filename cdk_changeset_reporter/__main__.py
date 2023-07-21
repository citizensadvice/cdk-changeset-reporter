from .cdk_changeset_reporter import main
from sys import argv

if __name__ == "__main__":
    if len(argv) < 2:
        raise ValueError("A stage name must be provided, e.g. dev, test, prod")

    main(argv[1])

# CDK Changeset Reporter

The CDK Changeset Reporter is a Python script that collects and prints CloudFormation (CFN) changeset information for one or more AWS Cloud Development Kit (CDK) stacks in a Cloud Assembly folder. The reporter uses each stack's CDK lookup role as defined in the Cloud Assembly entry for the stack to access the changeset information.

## Usage

The CDK Changeset Reporter can be used in three ways:

### Method 1: Report Changes for Multiple Stacks Individually

1. Create an instance of the `CdkChangesetReporter` class, providing the path to the Cloud Assembly directory (default is `"cdk.out"`).

```python
reporter = CdkChangesetReporter("/path/to/cloud_assembly_dir")
```

2. Add stacks to be included in the report using `add_stacks_starting_with` method. This method filters the stacks based on the given stack prefix.

```python
reporter.add_stacks_starting_with("staging")
reporter.add_stacks_starting_with("training")
```

3. Gather changes for the selected stacks using the `gather_changes` method.

```python
changes = reporter.gather_changes()
```

4. Generate and print the reports for each stack using the `report` method.

```python
reporter.report(changes)
```

### Method 2: Gather and Report Changes in one go

You can combine the steps from Method 1 into a single function call.

```python
reporter.gather_and_report("staging")
```

Replace `"staging"` with the desired stack prefix.

### Method 3: Call the module directly in the CDK project directory

You can execute the module in a CDK project directory with one or more stack prefixes as arguments.

```bash
puthon3 -m cdk_changeset_reporter staging
```


## License

This script is licensed under the [Apache License](LICENSE).

## Disclaimer

This script is provided as-is and without warranty. Use it at your own risk. Always review the changesets before applying them to your stacks.

**Note:** The script may depend on external libraries and AWS services, which may have their own licenses and terms of use. Please review and comply with the respective licenses and terms.

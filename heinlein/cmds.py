from pathlib import Path

import click

from heinlein import api


@click.command()
@click.argument("dataset_name")
@click.argument("data_type")
@click.argument("path")
@click.option("force", "-f", "--force", is_flag=True)
def add(dataset_name, data_type, path, force=False) -> bool:
    """
    Add a location on disk to a dataset
    """
    api.add(dataset_name, data_type, path, force)
    return True


@click.command()
@click.argument("dataset_name")
@click.argument("data_type")
def remove(dataset_name, data_type):
    api.remove(dataset_name, data_type)
    return True


@click.command()
@click.argument("dataset_name")
@click.argument("data_type")
def get(dataset_name, data_type) -> str:
    """
    Get the path to a specific data type in a specific datset
    """
    path = api.get(dataset_name, data_type)
    return str(path)


@click.command
@click.argument("dataset_name")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def prep_catalog(dataset_name: str, path: Path):
    """
    Prepare a catalog for a dataset. The path should be a directory containing
    the data as CSV files. The database will be created in the same directory.
    """
    print(path)
    api.prep_catalog(dataset_name, path)
    return True

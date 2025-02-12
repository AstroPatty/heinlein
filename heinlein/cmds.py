import io
from contextlib import redirect_stdout

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
def get(dataset_name, data_type) -> bool:
    """
    Get the path to a specific data type in a specific datset
    """
    # Capture any print statements

    with redirect_stdout(io.StringIO()) as _:
        path = api.get(dataset_name, data_type)

    click.echo(path)

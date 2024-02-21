import click
from godata import load_project
from godata.project import GodataProjectError

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
    try:
        project = load_project(dataset_name, ".heinlein")
    except GodataProjectError:
        print(f"Error: dataset {dataset_name} does not exist!")
        return False
    try:
        path = project.get("data/" + data_type, as_path=True)
    except GodataProjectError:
        print(f"Error: data type {data_type} does not exist in dataset {dataset_name}")
        return False
    click.echo(path)

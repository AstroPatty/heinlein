<<<<<<< HEAD
import io
from contextlib import redirect_stdout
=======
from pathlib import Path
>>>>>>> e5fe91f (Add some commands)

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
<<<<<<< HEAD
    # Capture any print statements

    with redirect_stdout(io.StringIO()) as _:
        path = api.get(dataset_name, data_type)

    click.echo(path)
=======
    path = api.get(dataset_name, data_type)
    return str(path)


@click.command(name="prep")
@click.argument("dataset_name")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-d",
    "--data-type",
    required=False,
    type=click.Choice(["catalog", "mask", "image"]),
    default="catalog",
)
def prep(dataset_name: str, path: Path, data_type: str = "catalog"):
    """
    Prepare a catalog for a dataset. The path should be a directory containing
    the data as CSV files. The database will be created in the same directory.
    """
    match data_type:
        case "catalog":
            api.prep_catalog(dataset_name, path)
        case _:
            raise NotImplementedError()
    return True
>>>>>>> e5fe91f (Add some commands)

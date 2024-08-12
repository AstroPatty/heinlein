import click

from . import cmds


@click.group()
def cli():
    pass


cli.add_command(cmds.add)
cli.add_command(cmds.remove)
cli.add_command(cmds.get)
cli.add_command(cmds.prep)

if __name__ == "__main__":
    cli()

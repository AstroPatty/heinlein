import click

from . import cmds


@click.group()
def cli():
    pass


cli.add_command(cmds.add)
cli.add_command(cmds.remove)
cli.add_command(cmds.get)

if __name__ == "__main__":
    cli()

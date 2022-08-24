import argparse
import json
from heinlein import cmds

from heinlein.locations import INSTALL_DIR, MAIN_CONFIG_DIR
from heinlein.config import globalConfig

cmd_config_location = MAIN_CONFIG_DIR / "cmds.json"
with open(cmd_config_location, 'rb') as cfg:
    commands = json.load(cfg)


parser = argparse.ArgumentParser("heinlein")
subparsers = parser.add_subparsers(help="help")
for key, data in commands.items():
    p = subparsers.add_parser(name=key, help = data['help'])
    cmd_key = data.pop("function", key)
    f = getattr(cmds, cmd_key)
    p.set_defaults(function=f)
    for key_, data_ in data['options'].items():
        p.add_argument(key_, **data_)



def delegate_command():
    globalConfig.interactive = True
    args = parser.parse_args()
    args.function(args)


import argparse
import json
from heinlein import cmds
from pydoc import locate

from heinlein.locations import INSTALL_DIR, MAIN_CONFIG_DIR
from heinlein.config import globalConfig

cmd_config_location = MAIN_CONFIG_DIR / "cmds.json"
with open(cmd_config_location, 'rb') as cfg:
    commands = json.load(cfg)

top_options = commands.pop("options")

parser = argparse.ArgumentParser("heinlein")
for opt_name, opt_d in top_options.items():
    flag = opt_d.pop("flag", False)
    if 'type' in opt_d.keys():
        opt_d['type'] = locate(opt_d['type'])
    if flag:
        name = [flag, opt_name]
    else:
        name = [opt_name]
    parser.add_argument(*name, **opt_d)

sp = parser.add_subparsers(help="help")
for key, data in commands.items():
    cmd_key = data.pop("function", key)
    f = getattr(cmds, cmd_key)
    options = data.pop('options')
    p = sp.add_parser(key, help=data['help'])
    for opt_key, opt_values in options.items():
        flag = opt_values.pop("flag", False)
        if flag:
            name = [flag, opt_key]
        else:
            name = [opt_key]
        p.add_argument(*name, **opt_values)
    p.set_defaults(function=f)


def delegate_command():
    globalConfig.interactive = True
    args = parser.parse_args()
    args.function(args)

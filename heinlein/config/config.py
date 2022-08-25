
from dynaconf import Dynaconf
from heinlein.locations import MAIN_CONFIG_DIR


globalConfig = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=[MAIN_CONFIG_DIR / 'config.json', '.secrets.json'],
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.

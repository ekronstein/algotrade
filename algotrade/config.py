import toml


class InvalidConfigError(Exception):
    pass


class ConfigNotSetupError(Exception):
    pass


def valid_or_raise(config):  # TODO STUB
    if not config:
        raise InvalidConfigError("empty config dictionary")


DEFAULT_CONFIG_FILE = "config.toml"
_config = {}

def set_config(file=DEFAULT_CONFIG_FILE):
    """
    Initialzies _dict to represent a toml config file. If not called before get_config(), the default config toml is used
    Arguments:
        file: the toml configuration file to load
    """
    with open(file, "r") as f:
        _config.update(toml.load(f))
    with open(_config["secrets_file"], "r") as f:
        _config.update({"secrets": toml.load(f)})
    valid_or_raise(_config)

def get_config() -> dict:
    if not _config:
        set_config()
    return _config

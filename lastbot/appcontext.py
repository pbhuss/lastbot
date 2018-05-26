import yaml
from flask import g
from pylast import LastFMNetwork


YAML_CONF_PATH = 'instance/config.yaml'


def get_config():
    if 'config' not in g:
        with open(YAML_CONF_PATH, 'r') as fp:
            g.config = yaml.load(fp)
    return g.config


def get_last():
    if 'last' not in g:
        config = get_config()
        g.last = LastFMNetwork(
            api_key=config['lastfm_api_key'],
            api_secret=config['lastfm_api_secret']
        )

    return g.last

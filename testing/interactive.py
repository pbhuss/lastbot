import yaml
from pylast import LastFMNetwork
from lastbot import app
from lastbot import db  # noqa
from lastbot.models import *    # noqa


def get_last():
    with open('instance/config.yaml', 'r') as fp:
        config = yaml.load(fp)
    return LastFMNetwork(
        api_key=config['lastfm_api_key'],
        api_secret=config['lastfm_api_secret']
    )


last = get_last()
app.app_context().push()

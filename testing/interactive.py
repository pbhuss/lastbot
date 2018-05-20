import sqlite3
import yaml
from pylast import LastFMNetwork


def get_last():
    with open('api.yaml', 'r') as fp:
        api_config = yaml.load(fp)
    return LastFMNetwork(
        api_key=api_config['lastfm_api_key'],
        api_secret=api_config['lastfm_api_secret']
    )


last = get_last()
db = sqlite3.connect('lastbot.db')

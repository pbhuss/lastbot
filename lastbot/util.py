import time
from functools import wraps

import pylast
from flask import Response, request, jsonify, url_for

import lastbot
from lastbot.appcontext import get_config


class ResponseType(object):

    EPHEMERAL = 'ephemeral'
    IN_CHANNEL = 'in_channel'


def get_response(type, text, attachments=None):
    response = {
        "response_type": type,
        "text": text,
    }
    if attachments:
        response["attachments"] = attachments

    return jsonify(response)


def get_verification_token():
    return get_config()['slack_verification_token']


def get_admin_password():
    return get_config()['admin_password']


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == get_admin_password()


def auth_response():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials',
        status=401,
        headers={'WWW-Authenticate': 'Basic realm="Login Required"'}
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return auth_response()
        return f(*args, **kwargs)
    return decorated


def requires_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.form.get('token') != get_verification_token():
            return Response(status=400)
        return f(*args, **kwargs)
    return decorated


def quote_user_id(user_id):
    return '<@{}>'.format(user_id)


def default_attachment_data(start_time=None):
    homepage_url = url_for('index', _external=True)
    if start_time:
        footer = "<{}|LastFM Bot {}> | response took {} ms".format(
            homepage_url,
            lastbot.__version__,
            round(1000 * (time.time() - start_time), 0)
        )
    else:
        footer = "<{}|LastFM Bot {}>".format(homepage_url, lastbot.__version__)

    return {
        "color": "#f50000",
        "footer": footer,
        "footer_icon": url_for(
            "static", filename="lastfm.ico", _external=True),
    }


def now_playing_attachment(user_id, track, start_time):
    attachment = {
        "pretext": '{} is listening to:'.format(quote_user_id(user_id)),
        "fallback": "{} - {}".format(track.artist.name, track.title),
        "fields": [
            {
                "title": "Artist",
                "value": "<{}|{}>".format(
                    track.artist.get_url(),
                    track.artist.name
                ),
                "short": True
            },
        ],
        **default_attachment_data(start_time)
    }

    album = track.get_album()
    if album:
        attachment["fields"].append(
            {
                "title": "Album",
                "value": "<{}|{}>".format(
                    album.get_url(),
                    album.get_name()
                ),
                "short": True
            }
        )
        attachment["image_url"] = album.get_cover_image(pylast.SIZE_LARGE)
    else:
        attachment["image_url"] = track.artist.get_cover_image(
            pylast.SIZE_LARGE)

    attachment["fields"].append(
        {
            "title": "Title",
            "value": "<{}|{}>".format(
                track.get_url(),
                track.title
            ),
            "short": True
        }
    )

    return attachment

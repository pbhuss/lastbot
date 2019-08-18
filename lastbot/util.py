import hmac
import time
from functools import wraps, lru_cache

import redis
from flask import Response, request, jsonify, url_for

import lastbot


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


def get_signing_secret():
    return lastbot.app.config['SIGNING_SECRET'].encode('utf-8')


@lru_cache(maxsize=1)
def get_redis():
    return redis.Redis.from_url(lastbot.app.config['REDIS_URL'])


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return (
        username == lastbot.app.config['ADMIN_USERNAME']
        and password == lastbot.app.config['ADMIN_PASSWORD']
    )


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


def verify_signature(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if (
            'X-Slack-Request-Timestamp' not in request.headers
            or 'X-Slack-Signature' not in request.headers
        ):
            lastbot.log.warning('Request missing expected headers!')
            return Response(status=400)

        if abs(
            time.time() - request.headers.get(
                'X-Slack-Request-Timestamp', type=int)
        ) > 60 * 5:
            # The request timestamp is more than five minutes from local time.
            # It could be a replay attack, so let's ignore it.
            lastbot.log.warning('Request is possible replay attack!')
            return Response(status=400)

        msg = b':'.join((
            b'v0',
            request.headers.get('X-Slack-Request-Timestamp', as_bytes=True),
            request.get_data()
        ))
        digest = hmac.new(get_signing_secret(), msg, 'sha256').hexdigest()
        signature = request.headers['X-Slack-Signature']
        if not hmac.compare_digest(f'v0={digest}', signature):
            lastbot.log.warning('Request failed signature check!')
            return Response(status=400)
        return f(*args, **kwargs)
    return decorated


def quote_user_id(user_id):
    return '<@{}>'.format(user_id)


def default_attachment_data(start_time=None):
    homepage_url = url_for('main.index', _external=True)
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


def now_playing_attachment(api, user_id, track, start_time):
    artist = api.artist.get_info(track['artist']['#text'])
    attachment = {
        "pretext": '{} is listening to:'.format(quote_user_id(user_id)),
        "fallback": "{} - {}".format(track['artist']['#text'], track['name']),
        "fields": [
            {
                "title": "Artist",
                "value": "<{}|{}>".format(
                    artist['url'],
                    artist['name']
                ),
                "short": True
            },
        ],
        **default_attachment_data(start_time)
    }

    album = track.get('album')
    if album:
        attachment["fields"].append(
            {
                "title": "Album",
                "value": "<{}|{}>".format(
                    album['url'],
                    album['#text']
                ),
                "short": True
            }
        )

    image = track.get('image')
    if image:
        attachment["image_url"] = image[2]['#text']
    else:
        pass    #TODO
        # attachment["image_url"] = track.artist.get_cover_image(
        #     pylast.SIZE_LARGE)

    attachment["fields"].append(
        {
            "title": "Title",
            "value": "<{}|{}>".format(
                track['url'],
                track['name']
            ),
            "short": True
        }
    )

    return attachment

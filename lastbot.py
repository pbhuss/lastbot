import sqlite3
import time
from functools import wraps

import pylast
import yaml
from datetime import datetime
from flask import g
from flask import url_for
from flask import Flask
from flask import request
from flask import jsonify
from flask import render_template
from flask import Response
from pylast import LastFMNetwork


__version__ = '0.0.2'


app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('lastbot.db')
        c = g.db.cursor()
        c.execute("""
          CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id STRING,
            user_id STRING,
            lastfm_user STRING
          )
        """)
        g.db.commit()
        c.close()

    return g.db


@app.teardown_appcontext
def teardown_db(exc):
    db = g.pop('db', None)
    if db:
        db.close()


def get_last():
    if 'last' not in g:
        with open('api.yaml', 'r') as fp:
            api_config = yaml.load(fp)
        g.last = LastFMNetwork(
            api_key=api_config['lastfm_api_key'],
            api_secret=api_config['lastfm_api_secret']
        )

    return g.last


def get_verification_token():
    if 'slack_verification_token' not in g:
        with open('api.yaml', 'r') as fp:
            api_config = yaml.load(fp)
        g.slack_verification_token = api_config['slack_verification_token']

    return g.slack_verification_token


def get_admin_password():
    if 'admin_password' not in g:
        with open('api.yaml', 'r') as fp:
            api_config = yaml.load(fp)
        g.admin_password = api_config['admin_password']
    return g.admin_password


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == get_admin_password()


def authenticate():
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
            return authenticate()
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


@app.route('/')
def index():
    return render_template('index.html', version=__version__)


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


def build_attachment(track, start_time):
    attachment = {
        "fallback": "{} - {}".format(track.artist.name, track.title),
        "color": "#f50000",
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
        "footer": "LastFM Bot | response took {} ms".format(
            round(1000 * (time.time() - start_time), 0)
        ),
        "footer_icon": url_for(
            "static", filename="lastfm.ico", _external=True),
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


@app.route('/playing', methods=['POST'])
@requires_token
def playing():
    start_time = time.time()
    form_text = request.form.get('text')
    if form_text:
        if not form_text[:2] == '<@':
            return get_response(
                ResponseType.EPHEMERAL,
                'Username must begin with `@`.'
            )
        user_id = form_text.split('|')[0][2:]
    else:
        user_id = request.form.get('user_id')

    team_id = request.form.get('team_id')

    if not user_id:
        return get_response(ResponseType.EPHEMERAL, 'Username required')

    c = get_db().cursor()
    row = c.execute(
        "SELECT lastfm_user FROM users WHERE team_id = ? AND user_id = ?",
        (team_id, user_id,)
    ).fetchone()
    c.close()

    if row is None:
        return get_response(
            ResponseType.EPHEMERAL,
            'No LastFM user registered to {}'.format(quote_user_id(user_id))
        )
    lastfm_user, = row

    try:
        track = get_last().get_user(lastfm_user).get_now_playing()
    except pylast.WSError as e:
        return get_response(ResponseType.EPHEMERAL, e.details)

    if track:
        text = '{} is listening to:'.format(quote_user_id(user_id))
        attachment = build_attachment(track, start_time)
        return get_response(ResponseType.IN_CHANNEL, text, [attachment])
    else:
        text = '{} isn\'t listening to anything.'.format(
            quote_user_id(user_id))
        return get_response(ResponseType.IN_CHANNEL, text)


@app.route('/userinfo', methods=['POST'])
@requires_token
def user_info():
    start_time = time.time()
    form_text = request.form.get('text')
    if form_text:
        if not form_text[:2] == '<@':
            return get_response(
                ResponseType.EPHEMERAL,
                'Username must begin with `@`.'
            )
        user_id = form_text.split('|')[0][2:]
    else:
        user_id = request.form.get('user_id')

    team_id = request.form.get('team_id')

    if not user_id:
        return get_response(ResponseType.EPHEMERAL, 'Username required')

    c = get_db().cursor()
    row = c.execute(
        "SELECT lastfm_user FROM users WHERE team_id = ? AND user_id = ?",
        (team_id, user_id,)
    ).fetchone()
    c.close()

    if row is None:
        return get_response(
            ResponseType.EPHEMERAL,
            'No LastFM user registered to {}'.format(quote_user_id(user_id))
        )
    lastfm_user, = row

    last = get_last()
    user = last.get_user(lastfm_user)
    playcount = user.get_playcount()
    signup_date = datetime.fromtimestamp(user.get_unixtime_registered())
    days_since_signup = (datetime.now() - signup_date).days
    url = user.get_url()
    plays_per_day = round(float(playcount) / days_since_signup, 1)
    artists = user.get_top_artists(period=pylast.PERIOD_1MONTH, limit=5)

    main_attachment = {
        "pretext": "LastFM info for {}:".format(quote_user_id(user_id)),
        "title": "<{}>".format(url),
        "fields": [
            {
                "title": "Subscriber since",
                "value": str(signup_date.date()),
                "short": True
            },
            {
                "title": "Scrobbles",
                "value": "{} ({} per day)".format(
                    playcount,
                    plays_per_day
                ),
                "short": True
            }
        ],
        "fallback": "{}".format(lastfm_user),
        "color": "#f50000",
    }

    artist_fields = [
        {
            "title": artist.item.name,
            "value": "{} plays".format(artist.weight),
            "short": False
        }
        for artist in artists
    ]

    artist_attachment = {
        "pretext": "*Top Artists (last 30 days)*",
        "fields": artist_fields,
        "color": "#f50000",
        "footer": "LastFM Bot | response took {} ms".format(
            round(1000 * (time.time() - start_time), 0)
        ),
        "footer_icon": url_for(
            "static", filename="lastfm.ico", _external=True),
    }

    return get_response(
        ResponseType.IN_CHANNEL, None, [main_attachment, artist_attachment])


@app.route('/register', methods=['POST'])
@requires_token
def register():
    team_id = request.form.get('team_id')
    user_id = request.form.get('user_id')
    lastfm_user = request.form.get('text')
    if not all((team_id, user_id, lastfm_user)):
        return "Missing required field"

    # Validate LastFM user
    try:
        get_last().get_user(lastfm_user).get_registered()
    except pylast.WSError as e:
        return 'LastFM user `{}` not found'.format(lastfm_user)

    db = get_db()
    c = db.cursor()

    row = c.execute(
        "SELECT id, lastfm_user FROM users WHERE team_id = ? AND user_id = ?",
        (team_id, user_id,)
    ).fetchone()
    if row:
        id_, prev_lastfm_user, = row
        if prev_lastfm_user != lastfm_user:
            c.execute(
                "UPDATE users SET lastfm_user = ? WHERE id = ?",
                (lastfm_user, id_,)
            )
            db.commit()
            c.close()
            return "Updated LastFM user for {} to `{}`".format(
                quote_user_id(user_id), lastfm_user)
        else:
            c.close()
            return "LastFM user `{}` already registed to {}".format(
                lastfm_user, quote_user_id(user_id))
    else:
        c.execute(
            "INSERT INTO users (team_id, user_id, lastfm_user)"
            "VALUES (?, ?, ?)",
            (team_id, user_id, lastfm_user,)
        )
        db.commit()
        c.close()
        return "Registed LastFM user `{}` to {}".format(
            lastfm_user, quote_user_id(user_id))


@app.route('/unlink', methods=['POST'])
@requires_token
def unlink():
    team_id = request.form.get('team_id')
    user_id = request.form.get('user_id')
    if not all((team_id, user_id)):
        return "Missing required field"

    db = get_db()
    c = db.cursor()

    row = c.execute(
        "SELECT id, lastfm_user FROM users WHERE team_id = ? AND user_id = ?",
        (team_id, user_id,)
    ).fetchone()
    if row:
        id_, lastfm_user, = row
        c.execute(
            "DELETE FROM users WHERE id = ?",
            (id_,)
        )
        db.commit()
        c.close()
        return "Unlinked LastFM user `{}` from {}".format(
            lastfm_user, quote_user_id(user_id))
    else:
        c.close()
        return get_response(
            ResponseType.EPHEMERAL,
            'No account registered to {}'.format(quote_user_id(user_id))
        )


@app.route('/users')
@requires_auth
def users():
    c = get_db().cursor()
    rows = c.execute("SELECT * FROM users;").fetchall()
    c.close()

    return render_template('users.html', users=rows)


@app.route('/commands')
def commands():
    return render_template('commands.html')


if __name__ == '__main__':
    app.run()

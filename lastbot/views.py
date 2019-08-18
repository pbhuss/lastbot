import time
import lastbot

from datetime import datetime
from flask import request, Blueprint
from flask import render_template

from lastbot import db
from lastbot.lastfm import LastFMAPIError, LastFMAPI
from lastbot.util import (
    requires_auth,
    verify_signature,
    quote_user_id,
    get_response,
    now_playing_attachment,
    ResponseType,
    default_attachment_data
)


main = Blueprint('main', __name__)


@main.route('/')
def index():
    return render_template('index.html', version=lastbot.__version__)


@main.route('/commands')
def commands():
    return render_template('commands.html')


@main.route('/users')
@requires_auth
def users():
    rows = [
        {'team_id': team_id, 'user_id': user_id, 'lastfm_user': lastfm_user}
        for team_id in db.get_teams()
        for user_id, lastfm_user in db.get_user_map(team_id)
    ]
    return render_template('users.html', users=rows)


@main.route('/playing', methods=['POST'])
@verify_signature
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

    lastfm_user = db.get_lastfm_user(team_id, user_id)

    if lastfm_user is None:
        return get_response(
            ResponseType.EPHEMERAL,
            'No LastFM user registered to {}'.format(quote_user_id(user_id))
        )

    api = LastFMAPI.from_app(lastbot.app)

    try:
        track = api.user.get_now_playing(lastfm_user)
    except LastFMAPIError as e:
        return get_response(ResponseType.EPHEMERAL, 'LastFM API error occurred')

    if track:
        attachment = now_playing_attachment(api, user_id, track, start_time)
        return get_response(ResponseType.IN_CHANNEL, None, [attachment])
    else:
        text = '{} isn\'t listening to anything.'.format(
            quote_user_id(user_id))
        return get_response(ResponseType.IN_CHANNEL, text)


@main.route('/userinfo', methods=['POST'])
@verify_signature
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

    row = User.query.filter_by(
        team_id=team_id,
        user_id=user_id,
    ).one_or_none()

    if row is None:
        return get_response(
            ResponseType.EPHEMERAL,
            'No LastFM user registered to {}'.format(quote_user_id(user_id))
        )

    last = get_last()
    user = last.get_user(row.lastfm_user)
    playcount = user.get_playcount()
    signup_date = datetime.fromtimestamp(user.get_unixtime_registered())
    days_since_signup = max(1, (datetime.now() - signup_date).days)
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
        "fallback": "{}".format(row.lastfm_user),
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
        "fallback": "Top Artists (last 30 days): {}".format(
            ','.join((artist.item.name for artist in artists))
        ),
        "fields": artist_fields,
        **default_attachment_data(start_time)
    }

    return get_response(
        ResponseType.IN_CHANNEL, None, [main_attachment, artist_attachment])


@main.route('/register', methods=['POST'])
@verify_signature
def register():
    team_id = request.form.get('team_id')
    user_id = request.form.get('user_id')
    lastfm_user = request.form.get('text')
    if not lastfm_user:
        return "LastFM username required"

    # Validate LastFM user
    try:
        get_last().get_user(lastfm_user).get_registered()
    except pylast.WSError as e:
        return 'LastFM user `{}` not found'.format(lastfm_user)

    row = User.query.filter_by(
        team_id=team_id,
        user_id=user_id,
    ).one_or_none()

    if row:
        if row.lastfm_user != lastfm_user:
            row.lastfm_user = lastfm_user
            db.session.add(row)
            db.session.commit()
            return "Updated LastFM user for {} to `{}`".format(
                quote_user_id(user_id), lastfm_user)
        else:
            return "LastFM user `{}` already registed to {}".format(
                lastfm_user, quote_user_id(user_id))
    else:
        row = User(team_id=team_id, user_id=user_id, lastfm_user=lastfm_user)
        db.session.add(row)
        db.session.commit()
        return "Registed LastFM user `{}` to {}".format(
            lastfm_user, quote_user_id(user_id))


@main.route('/unlink', methods=['POST'])
@verify_signature
def unlink():
    team_id = request.form.get('team_id')
    user_id = request.form.get('user_id')

    row = User.query.filter_by(
        team_id=team_id,
        user_id=user_id,
    ).one_or_none()

    if row:
        db.session.delete(row)
        db.session.commit()
        return "Unlinked LastFM user `{}` from {}".format(
            row.lastfm_user, quote_user_id(user_id))
    else:
        return get_response(
            ResponseType.EPHEMERAL,
            'No account registered to {}'.format(quote_user_id(user_id))
        )

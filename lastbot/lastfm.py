import requests


LASTFM_ROOT = 'http://ws.audioscrobbler.com/2.0/'


class LastFMAPIError(Exception):
    pass


class LastFMAPI:

    def __init__(self, api_key, api_secret):
        self._api_key = api_key
        self._api_secret = api_secret

    @classmethod
    def from_app(cls, app):
        return cls(app.config['LASTFM_API_KEY'], app.config['LASTFM_API_SECRET'])

    @property
    def user(self):
        return UserAPI(self)

    @property
    def artist(self):
        return ArtistAPI(self)

    def get_resp(self, **extra_params):
        params = {
            'api_key': self._api_key,
            'format': 'json'
        }
        for k, v in extra_params.items():
            if v is not None:
                params[k] = v
        resp = requests.get(LASTFM_ROOT, params=params)
        if resp.status_code != 200:
            raise LastFMAPIError()
        return resp.json()


class UserAPI:

    def __init__(self, api: LastFMAPI):
        self._api = api

    def get_info(self, user):
        method = 'user.getinfo'
        return self._api.get_resp(method=method, user=user)

    def get_recent_tracks(self, user, limit=None, page=None, from_=None, extended=None, to=None):
        method = 'user.getrecenttracks'
        return self._api.get_resp(method=method, user=user, limit=limit, page=page, from_=None, extended=None, to=None)

    def get_now_playing(self, user):
        resp = self.get_recent_tracks(user=user, limit=1)
        track = resp['recenttracks']['track'][0]
        attrs = track['@attr']
        if not attrs or not attrs.get('nowplaying', False):
            return None
        return track


class ArtistAPI:

    def __init__(self, api: LastFMAPI):
        self._api = api

    def get_info(self, artist):
        method = 'artist.getinfo'
        return self._api.get_resp(method=method, artist=artist)['artist']

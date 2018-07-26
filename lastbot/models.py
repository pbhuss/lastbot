from lastbot import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.String)
    user_id = db.Column(db.String)
    lastfm_user = db.Column(db.String)


class Tracks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.String)
    channel_id = db.Column(db.String)
    artist = db.Column(db.String)
    title = db.Column(db.String)
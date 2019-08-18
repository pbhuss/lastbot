from flask import Flask
from flask.logging import create_logger

from lastbot.views import main


__version__ = '0.1.0'


def create_app(config_filename):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile(config_filename)
    app.register_blueprint(main)
    return app


app = create_app('config.py')
log = create_logger(app)

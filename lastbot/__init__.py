from flask import Flask
from flask_sqlalchemy import SQLAlchemy

__version__ = '0.0.3'

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)

import lastbot.views
import lastbot.models

db.create_all()

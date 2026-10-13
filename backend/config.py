from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_session import Session


UPLOAD_FOLDER = 'uploads'

app = Flask(__name__)
app.secret_key = 'secret'

CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_building_educational_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SESSION_TYPE'] = 'filesystem'  # Utiliza el sistema de archivos para almacenar sesiones
app.config['SESSION_FILE_DIR'] = 'flask_session'  # Directorio donde se almacenan los archivos de sesión
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

Session(app)

db = SQLAlchemy(app)
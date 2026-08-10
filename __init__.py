import os
from flask import Flask
from .extensions import db


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///lookout.sqlite")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    db.init_app(app)
    from .web import bp
    app.register_blueprint(bp)
    with app.app_context():
        db.create_all()
        from .seed import seed_system_templates, bootstrap_owner
        seed_system_templates(); bootstrap_owner()
    return app

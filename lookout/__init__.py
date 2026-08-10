import os
import secrets
from flask import Flask, request, session, abort
from .extensions import db, migrate


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    secret_key = os.getenv("FLASK_SECRET_KEY", "").strip()
    if not secret_key:
        if os.getenv("LOOKOUT_ALLOW_INSECURE_DEV") == "1":
            secret_key = "dev-change-me"
        else:
            raise RuntimeError("FLASK_SECRET_KEY is required")

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///lookout.sqlite")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("LOOKOUT_COOKIE_SECURE", "0") == "1"

    db.init_app(app)
    migrate.init_app(app, db)

    from .web import bp
    app.register_blueprint(bp)

    @app.context_processor
    def inject_csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return {"csrf_token": token}

    @app.before_request
    def csrf_protect():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        expected = session.get("_csrf_token")
        supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            abort(400, description="Invalid CSRF token")

    with app.app_context():
        db.create_all()
        from .seed import seed_system_templates, bootstrap_owner
        seed_system_templates()
        bootstrap_owner()
    return app

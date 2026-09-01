from flask_migrate import upgrade
from . import create_app
from .seed import seed_system_templates, bootstrap_owner


def main():
    app = create_app()
    with app.app_context():
        upgrade()
        seed_system_templates()
        bootstrap_owner()


if __name__ == "__main__":
    main()

import os, time
from . import create_app
from .models import Project
from .security import decrypt_secret
from .telegram import tg_call, process_update


def main():
    app = create_app()
    offsets = {}
    poll_seconds = float(os.getenv("TELEGRAM_POLL_SECONDS", "2"))
    with app.app_context():
        while True:
            projects = Project.query.filter_by(is_active=True).all()
            for project in projects:
                if not project.telegram_bot_token_enc: continue
                try:
                    token = decrypt_secret(project.telegram_bot_token_enc)
                    updates = tg_call(token, "getUpdates", offset=offsets.get(project.id, 0), timeout=1, allowed_updates=["message","edited_message"])
                    for update in updates or []:
                        offsets[project.id] = max(offsets.get(project.id, 0), update["update_id"] + 1)
                        process_update(project, token, update)
                except Exception as exc:
                    print(f"telegram project={project.id} error={exc}", flush=True)
            time.sleep(poll_seconds)

if __name__ == "__main__": main()

import os, time
from datetime import datetime, timezone
from . import create_app
from .extensions import db
from .models import Community, ContentAutomation
from .content import fire, due


def main():
    app = create_app()
    interval = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "30"))
    with app.app_context():
        while True:
            now = datetime.now(timezone.utc)
            for auto in ContentAutomation.query.filter_by(enabled=True).all():
                communities = Community.query.filter(Community.id.in_(auto.community_ids or [])).all()
                for community in communities:
                    is_due, key = due(auto, community, now)
                    if is_due:
                        fire(auto, only_community_id=community.id)
                        keys = dict(auto.last_run_keys or {})
                        keys[str(community.id)] = key
                        auto.last_run_keys = keys
                        db.session.commit()
            time.sleep(interval)

if __name__ == "__main__": main()

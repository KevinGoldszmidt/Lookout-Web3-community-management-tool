from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from .ai import generate
from .extensions import db
from .models import Community, ContentAutomation, PostHistory, Project
from .security import decrypt_secret
from .telegram import send_message


def render_automation(project: Project, automation: ContentAutomation, community: Community) -> str:
    system = f"You create community content for {project.name}. Write useful, factual Web3 community content. Never invent company-specific claims, promotions, fees, or offers. Target language: {community.primary_language}. Keep Telegram formatting readable and concise."
    prompt = automation.prompt
    if automation.translate:
        prompt += f"\n\nWrite the final post in {community.primary_language}."
    return generate(project.id, system, prompt, max_tokens=900)


def fire(automation: ContentAutomation, force=False, only_community_id: int | None = None):
    project = Project.query.get(automation.project_id)
    if not project or not project.telegram_bot_token_enc: return
    token = decrypt_secret(project.telegram_bot_token_enc)
    communities = Community.query.filter(Community.project_id==project.id, Community.id.in_(automation.community_ids or [])).all()
    if only_community_id is not None:
        communities = [c for c in communities if c.id == only_community_id]
    for community in communities:
        if not community.scheduled_content_enabled: continue
        try:
            text = render_automation(project, automation, community)
            target = community.announcement_chat_id or community.group_chat_id
            result = send_message(token, target, text)
            db.session.add(PostHistory(project_id=project.id, community_id=community.id, automation_id=automation.id, status="sent", content=text, telegram_message_id=str((result or {}).get("message_id", ""))))
        except Exception as exc:
            db.session.add(PostHistory(project_id=project.id, community_id=community.id, automation_id=automation.id, status="failed", error=str(exc)))
        db.session.commit()


def due(automation: ContentAutomation, community: Community, now_utc: datetime) -> tuple[bool, str]:
    try:
        local = now_utc.astimezone(ZoneInfo(community.timezone or "UTC"))
    except Exception:
        local = now_utc.astimezone(ZoneInfo("UTC"))
    run_key = f"{community.id}:{local.date().isoformat()}:{automation.local_time}"
    if local.weekday() not in (automation.days or []): return False, run_key
    try:
        hour, minute = [int(x) for x in automation.local_time.split(":", 1)]
        scheduled = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (ValueError, AttributeError):
        return False, run_key
    delta_seconds = (local - scheduled).total_seconds()
    last_keys = automation.last_run_keys or {}
    return 0 <= delta_seconds < 180 and last_keys.get(str(community.id)) != run_key, run_key

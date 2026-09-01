from __future__ import annotations
import html, re, requests
from .extensions import db
from .models import Community, ConversationEvent, Escalation, Integration, ModerationRule, UnrecognisedChat, utcnow
from .security import decrypt_secret
from .ai import answer, generate

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def tg_call(token: str, method: str, **payload):
    try:
        r = requests.post(TELEGRAM_API.format(token=token, method=method), json=payload, timeout=35)
    except requests.RequestException:
        raise RuntimeError(f"Could not reach Telegram for {method}: network error.") from None
    try:
        data = r.json()
    except ValueError:
        data = {}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram rejected {method}: {data.get('description') or f'HTTP {r.status_code}'}")
    return data.get("result")


def send_message(token: str, chat_id: str, text: str, reply_to: int | None = None):
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_to:
        payload["reply_parameters"] = {"message_id": reply_to}
    return tg_call(token, "sendMessage", **payload)


def delete_message(token: str, chat_id: str, message_id: int):
    return tg_call(token, "deleteMessage", chat_id=chat_id, message_id=message_id)


def _enabled_rules(project_id: int):
    return ModerationRule.query.filter_by(project_id=project_id, enabled=True).all()


def detect_violation(project_id: int, text: str) -> tuple[ModerationRule | None, str | None]:
    lower = text.lower()
    for rule in _enabled_rules(project_id):
        cfg = rule.config or {}
        if rule.rule_type == "banned_words":
            words = [w.lower().strip() for w in cfg.get("words", []) if w.strip()]
            if any(w in lower for w in words): return rule, "banned_words"
        if rule.rule_type == "private_keys":
            patterns = ["seed phrase", "private key", "recovery phrase", "mnemonic"]
            if any(p in lower for p in patterns): return rule, "security_sensitive"
        if rule.rule_type == "phishing":
            patterns = ["connect wallet", "verify wallet", "claim airdrop", "wallet validation", "support dm me"]
            if any(p in lower for p in patterns): return rule, "possible_phishing"
        if rule.rule_type == "suspicious_links":
            urls = re.findall(r"https?://[^\s]+", text)
            allow = [d.lower() for d in cfg.get("allow_domains", [])]
            if urls and allow and any(not any(domain in u.lower() for domain in allow) for u in urls):
                return rule, "suspicious_link"
    return None, None


def deliver_integration(integ: Integration, payload: dict) -> tuple[bool, str | None]:
    secret = decrypt_secret(integ.secret_enc)
    if not secret:
        integ.last_status, integ.last_error, integ.last_attempted_at = "failed", "No secret configured for this integration.", utcnow()
        db.session.commit()
        return False, integ.last_error
    try:
        if integ.integration_type == "slack_webhook":
            requests.post(secret, json={"text": payload.get("text", "Lookout alert")}, timeout=15).raise_for_status()
        else:
            requests.post(secret, json=payload, timeout=15).raise_for_status()
        integ.last_status, integ.last_error, integ.last_attempted_at = "sent", None, utcnow()
        db.session.commit()
        return True, None
    except Exception as exc:
        integ.last_status, integ.last_error, integ.last_attempted_at = "failed", str(exc), utcnow()
        db.session.commit()
        return False, str(exc)


def _alert_integrations(project_id: int, payload: dict):
    for integ in Integration.query.filter_by(project_id=project_id, enabled=True).all():
        if integ.integration_type not in {"slack_webhook", "webhook"}: continue
        ok, err = deliver_integration(integ, payload)
        if not ok:
            print(f"integration project={project_id} integration={integ.id} name={integ.name!r} error={err}", flush=True)


def escalate(project_id: int, community_id: int | None, username: str, category: str, message: str):
    e = Escalation(project_id=project_id, community_id=community_id, source_user=username, category=category, message=message, destination="configured integrations")
    db.session.add(e)
    db.session.add(ConversationEvent(project_id=project_id, community_id=community_id, telegram_user_id=None, username=username, event_type="escalation", category=category, question=message))
    db.session.commit()
    _alert_integrations(project_id, {"text": f"Lookout escalation\nUser: {username}\nCategory: {category}\nMessage: {message}", "category": category, "message": message})


def process_update(project, token: str, update: dict):
    msg = update.get("message") or update.get("edited_message")
    if not msg: return
    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    is_private = chat.get("type") == "private"
    community = None if is_private else Community.query.filter_by(project_id=project.id, group_chat_id=chat_id).first()
    if not is_private and not community:
        title = chat.get("title") or chat.get("username") or ""
        print(f"telegram project={project.id} unmatched_chat_id={chat_id} title={title!r}", flush=True)
        row = UnrecognisedChat.query.filter_by(project_id=project.id, chat_id=chat_id).first()
        if row:
            row.chat_title, row.last_seen_at = title or row.chat_title, utcnow()
        else:
            db.session.add(UnrecognisedChat(project_id=project.id, chat_id=chat_id, chat_title=title))
        db.session.commit()
        return
    if msg.get("is_automatic_forward"): return
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if not text: return
    user = msg.get("from", {})
    username = user.get("username") or user.get("first_name") or str(user.get("id", "unknown"))

    community_id = community.id if community else None
    db.session.add(ConversationEvent(project_id=project.id, community_id=community_id, telegram_user_id=str(user.get("id","")), username=username, event_type="message", question=text))
    db.session.commit()

    if community and community.moderation_enabled:
        rule, category = detect_violation(project.id, text)
        if rule:
            action = rule.action
            db.session.add(ConversationEvent(project_id=project.id, community_id=community_id, telegram_user_id=str(user.get("id","")), username=username, event_type="moderation", category=category, question=text, metadata_json={"rule": rule.label, "action": action}))
            db.session.commit()
            if action in {"delete", "delete_alert", "warn_delete"}:
                try: delete_message(token, chat_id, msg["message_id"])
                except Exception: pass
            if action in {"warn", "warn_delete"}:
                send_message(token, chat_id, f"@{username}, that message was flagged by the community moderation rules.")
            if action in {"alert", "delete_alert"}:
                _alert_integrations(project.id, {"text": f"Lookout moderation alert\nCommunity: {community.name}\nUser: {username}\nRule: {rule.label}\nMessage: {text}"})
            if action != "alert": return

    if community and not community.ai_enabled: return
    bot_username = (project.telegram_bot_username or "").lower().lstrip("@")
    mentioned = bool(bot_username and f"@{bot_username}" in text.lower())
    if not (is_private or mentioned): return
    clean = re.sub(rf"@{re.escape(bot_username)}", "", text, flags=re.I).strip() if bot_username else text
    try:
        reply = answer(project, community, clean)
    except Exception as exc:
        reply = "I can't answer that reliably right now. Please use the official support route configured by this community."
        db.session.add(ConversationEvent(project_id=project.id, community_id=community_id, telegram_user_id=str(user.get("id","")), username=username, event_type="ai_error", question=clean, response=str(exc)))
        db.session.commit()
    db.session.add(ConversationEvent(project_id=project.id, community_id=community_id, telegram_user_id=str(user.get("id","")), username=username, event_type="ai_response", question=clean, response=reply))
    db.session.commit()
    send_message(token, chat_id, reply, msg.get("message_id"))

import os, re
from .extensions import db
from .models import ContentTemplate, ContentAutomation, User, Organisation, Membership, Project, AgentConfig, ModerationRule
from .security import hash_password

SYSTEM_TEMPLATES = [
    ("crypto_trends", "Crypto Trends", "Create a concise post explaining 3 meaningful crypto or Web3 trends worth watching today. Focus on why each trend matters to a community member. Do not manufacture news.", ["news"], "Explains 3 notable Web3/crypto trends from general knowledge. Good 1-3x per week; uses no external data."),
    ("term_of_day", "Term of the Day", "Choose one useful Web3 or crypto term and explain it in plain language with a short practical example. Avoid repeating overly basic terms too often.", [], "Explains one Web3/crypto term in plain language. Safe daily filler post; uses no external data."),
    ("market_poll", "Market Poll", "Write one engaging, non-leading community poll question about current crypto market sentiment with 3 to 4 concise answer options. Return plain text with the question and options.", ["market_data"], "Asks a neutral sentiment poll question with answer options. Good for engagement — it's an opinion poll, not real market data."),
    ("feedback_poll", "Community Feedback", "Write one useful community feedback question that helps the team learn what members want more of. Include 3 to 4 concise answer choices.", [], "Asks members what they want more of. Good for gathering direct community feedback, run weekly or as needed."),
]

# Removed because nothing fetches market_data/news: Daily Market Analysis, Market Spotlight, Evening Recap.
# They asked the model for real market movement it has no source for, so it invented numbers.
REMOVED_SYSTEM_TEMPLATE_KEYS = ["market_analysis", "market_spotlight", "evening_recap"]

def seed_system_templates():
    for key, name, prompt, sources, description in SYSTEM_TEMPLATES:
        t = ContentTemplate.query.filter_by(project_id=None, key=key).first()
        if not t:
            t = ContentTemplate(project_id=None, key=key, system_template=True)
            db.session.add(t)
        t.name, t.prompt, t.data_sources, t.description = name, prompt, sources, description
    db.session.commit()
    stale = ContentTemplate.query.filter(ContentTemplate.project_id.is_(None), ContentTemplate.key.in_(REMOVED_SYSTEM_TEMPLATE_KEYS)).all()
    for t in stale:
        if not ContentAutomation.query.filter_by(template_id=t.id).first():
            db.session.delete(t)
    db.session.commit()


def seed_default_rules(project_id):
    defaults = [
        ("phishing", "Scam & phishing language", "delete_alert", {}),
        ("private_keys", "Private key / seed phrase safety", "warn", {}),
        ("suspicious_links", "Suspicious links", "alert", {"allow_domains": []}),
        ("banned_words", "Custom banned words", "delete_alert", {"words": []}),
    ]
    for rt, label, action, cfg in defaults:
        if not ModerationRule.query.filter_by(project_id=project_id, rule_type=rt).first():
            db.session.add(ModerationRule(project_id=project_id, rule_type=rt, label=label, action=action, config=cfg))
    db.session.commit()


def bootstrap_owner():
    email = os.getenv("BOOTSTRAP_OWNER_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_OWNER_PASSWORD", "").strip()
    if not email or not password or User.query.first(): return
    user = User(email=email, display_name=email.split("@")[0], password_hash=hash_password(password))
    org = Organisation(name="My Organisation", slug="my-organisation")
    db.session.add_all([user, org]); db.session.flush()
    db.session.add(Membership(user_id=user.id, organisation_id=org.id, role="owner"))
    project = Project(organisation_id=org.id, name="My Web3 Project")
    db.session.add(project); db.session.flush()
    db.session.add(AgentConfig(project_id=project.id))
    db.session.commit(); seed_default_rules(project.id)

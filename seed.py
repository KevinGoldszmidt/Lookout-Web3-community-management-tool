import os, re
from .extensions import db
from .models import ContentTemplate, User, Organisation, Membership, Project, AgentConfig, ModerationRule
from .security import hash_password

SYSTEM_TEMPLATES = [
    ("market_analysis", "Daily Market Analysis", "Create a concise daily crypto market analysis. Cover broad market direction, notable BTC/ETH movement, major catalysts, and one risk to watch. Clearly distinguish facts from interpretation. Do not give financial advice.", ["market_data"]),
    ("crypto_trends", "Crypto Trends", "Create a concise post explaining 3 meaningful crypto or Web3 trends worth watching today. Focus on why each trend matters to a community member. Do not manufacture news.", ["news"]),
    ("term_of_day", "Term of the Day", "Choose one useful Web3 or crypto term and explain it in plain language with a short practical example. Avoid repeating overly basic terms too often.", []),
    ("market_spotlight", "Market Spotlight", "Create an educational spotlight on one established crypto asset. Explain what it is, what its network/product does, current discussion themes, and neutral risks. Do not recommend buying or selling.", ["market_data", "news"]),
    ("evening_recap", "Evening Recap", "Write a short evening crypto market recap: what moved, what likely mattered, and what the community may want to watch next. Keep it neutral and factual.", ["market_data", "news"]),
    ("market_poll", "Market Poll", "Write one engaging, non-leading community poll question about current crypto market sentiment with 3 to 4 concise answer options. Return plain text with the question and options.", ["market_data"]),
    ("feedback_poll", "Community Feedback", "Write one useful community feedback question that helps the team learn what members want more of. Include 3 to 4 concise answer choices.", []),
]

def seed_system_templates():
    for key, name, prompt, sources in SYSTEM_TEMPLATES:
        if not ContentTemplate.query.filter_by(project_id=None, key=key).first():
            db.session.add(ContentTemplate(project_id=None, key=key, name=name, prompt=prompt, system_template=True, data_sources=sources))
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

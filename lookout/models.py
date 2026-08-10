from __future__ import annotations
from datetime import datetime, timezone
from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class Organisation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    logo_url = db.Column(db.String(500))
    accent = db.Column(db.String(32), default="#111827")


class Membership(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=False, index=True)
    role = db.Column(db.String(32), nullable=False, default="viewer")
    community_scope = db.Column(db.JSON, default=list, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "organisation_id", name="uq_membership"),)


class Project(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    company_description = db.Column(db.Text, default="")
    support_url = db.Column(db.String(500))
    telegram_bot_token_enc = db.Column(db.Text)
    telegram_bot_username = db.Column(db.String(160))
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class Community(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    platform = db.Column(db.String(32), default="telegram", nullable=False)
    primary_language = db.Column(db.String(80), default="English", nullable=False)
    timezone = db.Column(db.String(80), default="UTC", nullable=False)
    group_chat_id = db.Column(db.String(80), index=True)
    announcement_chat_id = db.Column(db.String(80))
    ai_enabled = db.Column(db.Boolean, default=True, nullable=False)
    moderation_enabled = db.Column(db.Boolean, default=True, nullable=False)
    scheduled_content_enabled = db.Column(db.Boolean, default=True, nullable=False)


class AIProvider(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    provider = db.Column(db.String(32), nullable=False)
    model = db.Column(db.String(120), nullable=False)
    api_key_enc = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=True, nullable=False)


class AgentConfig(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), default="Lookout")
    tone = db.Column(db.String(120), default="Friendly, direct, knowledgeable, concise")
    custom_instructions = db.Column(db.Text, default="")
    preferred_terms = db.Column(db.Text, default="")
    forbidden_terms = db.Column(db.Text, default="")
    fallback_mode = db.Column(db.String(40), default="escalate")


class KnowledgeDocument(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    source_type = db.Column(db.String(40), default="upload")
    filename = db.Column(db.String(255))
    full_text = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class KnowledgeChunk(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("knowledge_document.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)


class ModerationRule(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    rule_type = db.Column(db.String(80), nullable=False)
    label = db.Column(db.String(160), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    action = db.Column(db.String(32), default="alert")
    config = db.Column(db.JSON, default=dict, nullable=False)


class Integration(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    integration_type = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    secret_enc = db.Column(db.Text)
    config = db.Column(db.JSON, default=dict, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)


class ContentTemplate(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True, index=True)
    key = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    system_template = db.Column(db.Boolean, default=False, nullable=False)
    data_sources = db.Column(db.JSON, default=list, nullable=False)


class ContentAutomation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("content_template.id"), nullable=True)
    name = db.Column(db.String(160), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    local_time = db.Column(db.String(5), default="09:00")
    days = db.Column(db.JSON, default=lambda: [0,1,2,3,4,5,6], nullable=False)
    community_ids = db.Column(db.JSON, default=list, nullable=False)
    translate = db.Column(db.Boolean, default=True, nullable=False)
    last_run_keys = db.Column(db.JSON, default=dict, nullable=False)


class PostHistory(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=True, index=True)
    automation_id = db.Column(db.Integer, db.ForeignKey("content_automation.id"), nullable=True)
    status = db.Column(db.String(40), nullable=False)
    content = db.Column(db.Text, default="")
    telegram_message_id = db.Column(db.String(80))
    error = db.Column(db.Text)


class ConversationEvent(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=True, index=True)
    telegram_user_id = db.Column(db.String(80), index=True)
    username = db.Column(db.String(160))
    event_type = db.Column(db.String(80), nullable=False, index=True)
    category = db.Column(db.String(120))
    question = db.Column(db.Text)
    response = db.Column(db.Text)
    metadata_json = db.Column(db.JSON, default=dict, nullable=False)


class Escalation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=True)
    source_user = db.Column(db.String(160))
    category = db.Column(db.String(120))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), default="open", nullable=False)
    destination = db.Column(db.String(80))

from __future__ import annotations
import os, re, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from sqlalchemy import func
from werkzeug.utils import secure_filename
from .extensions import db
from .models import *
from .security import hash_password, verify_password, encrypt_secret, decrypt_secret
from .knowledge import ingest, ALLOWED
from .seed import seed_default_rules
from .telegram import tg_call, send_message
from .content import fire

bp = Blueprint("web", __name__)
ROLES = ["owner", "admin", "community_manager", "moderator", "viewer"]
ROLE_RANK = {"viewer":0,"moderator":1,"community_manager":2,"admin":3,"owner":4}


def slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "organisation"
    base, n = value, 2
    while Organisation.query.filter_by(slug=value).first():
        value = f"{base}-{n}"; n += 1
    return value


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("user_id"): return redirect(url_for("web.login"))
        return fn(*a, **kw)
    return wrapper


def current_user(): return db.session.get(User, session.get("user_id")) if session.get("user_id") else None

def current_membership():
    if not session.get("user_id") or not session.get("org_id"): return None
    return Membership.query.filter_by(user_id=session["user_id"], organisation_id=session["org_id"]).first()

def active_project():
    pid = session.get("project_id")
    if pid:
        p = db.session.get(Project, pid)
        if p and p.organisation_id == session.get("org_id"): return p
    p = Project.query.filter_by(organisation_id=session.get("org_id")).order_by(Project.id).first()
    if p: session["project_id"] = p.id
    return p

def require_role(min_role):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            m = current_membership()
            if not m or ROLE_RANK.get(m.role, -1) < ROLE_RANK[min_role]:
                flash("You do not have permission for that action.", "error"); return redirect(url_for("web.dashboard"))
            return fn(*a, **kw)
        return wrapper
    return deco

@bp.app_context_processor
def inject_globals():
    return {"me": current_user(), "membership": current_membership(), "project": active_project() if session.get("org_id") else None, "powered_by": os.getenv("LOOKOUT_POWERED_BY", "Goldszmidt Media")}

@bp.route("/setup", methods=["GET","POST"])
def setup():
    if User.query.first(): return redirect(url_for("web.login"))
    if request.method == "POST":
        name = request.form["name"].strip(); email=request.form["email"].strip().lower(); password=request.form["password"]
        org_name=request.form["organisation"].strip(); project_name=request.form["project"].strip()
        if len(password) < 10: flash("Use a password of at least 10 characters.", "error"); return render_template("setup.html")
        user=User(email=email,display_name=name,password_hash=hash_password(password)); org=Organisation(name=org_name,slug=slugify(org_name))
        db.session.add_all([user,org]); db.session.flush(); db.session.add(Membership(user_id=user.id,organisation_id=org.id,role="owner"))
        p=Project(organisation_id=org.id,name=project_name); db.session.add(p); db.session.flush(); db.session.add(AgentConfig(project_id=p.id)); db.session.commit(); seed_default_rules(p.id)
        session.update(user_id=user.id,org_id=org.id,project_id=p.id); return redirect(url_for("web.onboarding"))
    return render_template("setup.html")

@bp.route("/login", methods=["GET","POST"])
def login():
    if not User.query.first(): return redirect(url_for("web.setup"))
    if request.method == "POST":
        user=User.query.filter(func.lower(User.email)==request.form["email"].strip().lower()).first()
        if not user or not verify_password(user.password_hash,request.form["password"]): flash("Incorrect email or password.","error"); return render_template("login.html")
        membership=Membership.query.filter_by(user_id=user.id).order_by(Membership.id).first()
        session.clear(); session["user_id"]=user.id; session["org_id"]=membership.organisation_id
        p=Project.query.filter_by(organisation_id=membership.organisation_id).first(); session["project_id"]=p.id if p else None
        return redirect(url_for("web.dashboard"))
    return render_template("login.html")

@bp.route("/logout")
def logout(): session.clear(); return redirect(url_for("web.login"))

@bp.route("/onboarding")
@login_required
def onboarding(): return render_template("onboarding.html")

@bp.route("/")
@login_required
def dashboard():
    p=active_project(); since=datetime.now(timezone.utc)-timedelta(days=7)
    counts={}
    if p:
        counts["communities"]=Community.query.filter_by(project_id=p.id).count()
        counts["messages"]=ConversationEvent.query.filter(ConversationEvent.project_id==p.id,ConversationEvent.event_type=="message",ConversationEvent.created_at>=since).count()
        counts["ai"]=ConversationEvent.query.filter(ConversationEvent.project_id==p.id,ConversationEvent.event_type=="ai_response",ConversationEvent.created_at>=since).count()
        counts["moderation"]=ConversationEvent.query.filter(ConversationEvent.project_id==p.id,ConversationEvent.event_type=="moderation",ConversationEvent.created_at>=since).count()
        counts["escalations"]=Escalation.query.filter(Escalation.project_id==p.id,Escalation.created_at>=since).count()
        counts["knowledge"]=KnowledgeDocument.query.filter_by(project_id=p.id,is_active=True).count()
        recent=ConversationEvent.query.filter_by(project_id=p.id).order_by(ConversationEvent.created_at.desc()).limit(10).all()
    else: recent=[]
    return render_template("dashboard.html", counts=counts, recent=recent)

@bp.route("/projects", methods=["GET","POST"])
@login_required
@require_role("admin")
def projects():
    if request.method=="POST":
        p=Project(organisation_id=session["org_id"],name=request.form["name"].strip()); db.session.add(p); db.session.flush(); db.session.add(AgentConfig(project_id=p.id)); db.session.commit(); seed_default_rules(p.id); session["project_id"]=p.id; return redirect(url_for("web.onboarding"))
    return render_template("projects.html", projects=Project.query.filter_by(organisation_id=session["org_id"]).all())

@bp.post("/projects/<int:pid>/switch")
@login_required
def switch_project(pid):
    p=db.session.get(Project,pid)
    if p and p.organisation_id==session["org_id"]: session["project_id"]=p.id
    return redirect(request.referrer or url_for("web.dashboard"))

@bp.route("/telegram", methods=["GET","POST"])
@login_required
@require_role("admin")
def telegram_settings():
    p=active_project()
    if request.method=="POST":
        token=request.form["token"].strip()
        try:
            me=tg_call(token,"getMe"); p.telegram_bot_token_enc=encrypt_secret(token); p.telegram_bot_username=me.get("username"); db.session.commit(); flash(f"Connected @{p.telegram_bot_username}.","success")
        except Exception as exc: flash(f"Telegram connection failed: {exc}","error")
        return redirect(url_for("web.telegram_settings"))
    return render_template("telegram.html")

@bp.route("/communities", methods=["GET","POST"])
@login_required
@require_role("community_manager")
def communities():
    p=active_project()
    if request.method=="POST":
        c=Community(project_id=p.id,name=request.form["name"].strip(),primary_language=request.form["language"].strip(),timezone=request.form["timezone"].strip() or "UTC",group_chat_id=request.form["group_chat_id"].strip(),announcement_chat_id=request.form.get("announcement_chat_id","").strip() or None)
        db.session.add(c); db.session.commit(); flash("Community added.","success"); return redirect(url_for("web.communities"))
    return render_template("communities.html", communities=Community.query.filter_by(project_id=p.id).order_by(Community.name).all())

@bp.post("/communities/<int:cid>/toggle/<field>")
@login_required
@require_role("community_manager")
def community_toggle(cid,field):
    c=db.session.get(Community,cid); allowed={"ai_enabled","moderation_enabled","scheduled_content_enabled"}
    if c and c.project_id==active_project().id and field in allowed:
        setattr(c,field,not getattr(c,field)); db.session.commit()
    return redirect(url_for("web.communities"))

@bp.route("/ai", methods=["GET","POST"])
@login_required
@require_role("admin")
def ai_settings():
    p=active_project(); provider=AIProvider.query.filter_by(project_id=p.id,is_default=True).first(); agent=AgentConfig.query.filter_by(project_id=p.id).first()
    if request.method=="POST":
        mode=request.form.get("mode")
        if mode=="provider":
            key=request.form["api_key"].strip(); prov=request.form["provider"]; model=request.form["model"].strip()
            if provider: provider.provider=prov; provider.model=model; provider.api_key_enc=encrypt_secret(key) if key else provider.api_key_enc
            else: db.session.add(AIProvider(project_id=p.id,provider=prov,model=model,api_key_enc=encrypt_secret(key),is_default=True))
        else:
            agent.name=request.form["name"].strip(); agent.tone=request.form["tone"].strip(); agent.custom_instructions=request.form.get("custom_instructions","").strip(); agent.preferred_terms=request.form.get("preferred_terms","").strip(); agent.forbidden_terms=request.form.get("forbidden_terms","").strip(); agent.fallback_mode=request.form.get("fallback_mode","escalate")
        db.session.commit(); flash("AI settings saved.","success"); return redirect(url_for("web.ai_settings"))
    return render_template("ai.html", provider=provider, agent=agent)

@bp.route("/knowledge", methods=["GET","POST"])
@login_required
@require_role("community_manager")
def knowledge():
    p=active_project()
    if request.method=="POST":
        f=request.files.get("file")
        if not f or Path(f.filename).suffix.lower() not in ALLOWED: flash("Upload PDF, DOCX, TXT, or Markdown.","error"); return redirect(url_for("web.knowledge"))
        safe=secure_filename(f.filename); path=Path("uploads")/f"{p.id}_{uuid.uuid4().hex}_{safe}"; path.parent.mkdir(exist_ok=True); f.save(path)
        try: ingest(p.id,request.form.get("title") or safe,safe,path); flash("Knowledge uploaded and indexed.","success")
        except Exception as exc: flash(f"Could not index file: {exc}","error")
        return redirect(url_for("web.knowledge"))
    return render_template("knowledge.html", documents=KnowledgeDocument.query.filter_by(project_id=p.id).order_by(KnowledgeDocument.created_at.desc()).all())

@bp.post("/knowledge/<int:did>/delete")
@login_required
@require_role("community_manager")
def knowledge_delete(did):
    d=db.session.get(KnowledgeDocument,did)
    if d and d.project_id==active_project().id:
        KnowledgeChunk.query.filter_by(document_id=d.id).delete(); db.session.delete(d); db.session.commit()
    return redirect(url_for("web.knowledge"))

@bp.route("/moderation", methods=["GET","POST"])
@login_required
@require_role("moderator")
def moderation():
    p=active_project()
    if request.method=="POST":
        rid=int(request.form["rule_id"]); r=db.session.get(ModerationRule,rid)
        if r and r.project_id==p.id:
            r.enabled=request.form.get("enabled")=="on"; r.action=request.form.get("action","alert"); cfg=r.config or {}
            if r.rule_type=="banned_words": cfg["words"]=[x.strip() for x in request.form.get("words","").split(",") if x.strip()]
            if r.rule_type=="suspicious_links": cfg["allow_domains"]=[x.strip() for x in request.form.get("allow_domains","").split(",") if x.strip()]
            r.config=cfg; db.session.commit(); flash("Moderation rule updated.","success")
        return redirect(url_for("web.moderation"))
    return render_template("moderation.html", rules=ModerationRule.query.filter_by(project_id=p.id).all())

@bp.route("/integrations", methods=["GET","POST"])
@login_required
@require_role("admin")
def integrations():
    p=active_project()
    if request.method=="POST":
        typ=request.form["integration_type"]; name=request.form["name"].strip(); secret=request.form["secret"].strip()
        db.session.add(Integration(project_id=p.id,integration_type=typ,name=name,secret_enc=encrypt_secret(secret),config={},enabled=True)); db.session.commit(); flash("Integration added.","success"); return redirect(url_for("web.integrations"))
    return render_template("integrations.html", integrations=Integration.query.filter_by(project_id=p.id).all())

@bp.route("/content", methods=["GET","POST"])
@login_required
@require_role("community_manager")
def content():
    p=active_project(); templates=ContentTemplate.query.filter((ContentTemplate.project_id==None)|(ContentTemplate.project_id==p.id)).order_by(ContentTemplate.system_template.desc(),ContentTemplate.name).all(); comms=Community.query.filter_by(project_id=p.id).all()
    if request.method=="POST":
        tid=request.form.get("template_id"); t=db.session.get(ContentTemplate,int(tid)) if tid else None; prompt=request.form.get("prompt","").strip() or (t.prompt if t else "")
        days=[int(x) for x in request.form.getlist("days")]; cids=[int(x) for x in request.form.getlist("community_ids")]
        a=ContentAutomation(project_id=p.id,template_id=t.id if t else None,name=request.form["name"].strip(),prompt=prompt,local_time=request.form.get("local_time","09:00"),days=days or [0,1,2,3,4,5,6],community_ids=cids,translate=request.form.get("translate")=="on")
        db.session.add(a); db.session.commit(); flash("Content automation created.","success"); return redirect(url_for("web.content"))
    autos=ContentAutomation.query.filter_by(project_id=p.id).order_by(ContentAutomation.created_at.desc()).all()
    return render_template("content.html", templates=templates, communities=comms, automations=autos)

@bp.post("/content/<int:aid>/fire")
@login_required
@require_role("community_manager")
def content_fire(aid):
    a=db.session.get(ContentAutomation,aid)
    if a and a.project_id==active_project().id: fire(a,force=True); flash("Test post fired. Check Post History for delivery results.","success")
    return redirect(url_for("web.content"))

@bp.post("/content/<int:aid>/toggle")
@login_required
@require_role("community_manager")
def content_toggle(aid):
    a=db.session.get(ContentAutomation,aid)
    if a and a.project_id==active_project().id: a.enabled=not a.enabled; db.session.commit()
    return redirect(url_for("web.content"))

@bp.route("/history")
@login_required
def history(): return render_template("history.html", posts=PostHistory.query.filter_by(project_id=active_project().id).order_by(PostHistory.created_at.desc()).limit(200).all())

@bp.route("/analytics")
@login_required
def analytics():
    p=active_project(); since=datetime.now(timezone.utc)-timedelta(days=30)
    event_counts=dict(db.session.query(ConversationEvent.event_type,func.count(ConversationEvent.id)).filter(ConversationEvent.project_id==p.id,ConversationEvent.created_at>=since).group_by(ConversationEvent.event_type).all())
    top_topics=db.session.query(ConversationEvent.category,func.count(ConversationEvent.id)).filter(ConversationEvent.project_id==p.id,ConversationEvent.category!=None,ConversationEvent.created_at>=since).group_by(ConversationEvent.category).order_by(func.count(ConversationEvent.id).desc()).limit(10).all()
    unanswered=ConversationEvent.query.filter(ConversationEvent.project_id==p.id,ConversationEvent.event_type=="ai_error",ConversationEvent.created_at>=since).order_by(ConversationEvent.created_at.desc()).limit(20).all()
    return render_template("analytics.html", event_counts=event_counts, top_topics=top_topics, unanswered=unanswered)

@bp.route("/team", methods=["GET","POST"])
@login_required
@require_role("owner")
def team():
    if request.method=="POST":
        email=request.form["email"].strip().lower(); user=User.query.filter_by(email=email).first()
        if not user:
            temp=uuid.uuid4().hex[:14]; user=User(email=email,display_name=request.form.get("name") or email.split("@")[0],password_hash=hash_password(temp)); db.session.add(user); db.session.flush(); flash(f"User created. Temporary password: {temp}","success")
        if not Membership.query.filter_by(user_id=user.id,organisation_id=session["org_id"]).first(): db.session.add(Membership(user_id=user.id,organisation_id=session["org_id"],role=request.form["role"])); db.session.commit()
        return redirect(url_for("web.team"))
    rows=db.session.query(Membership,User).join(User,User.id==Membership.user_id).filter(Membership.organisation_id==session["org_id"]).all()
    return render_template("team.html", rows=rows, roles=ROLES)

@bp.get("/health")
def health(): return jsonify(ok=True, service="lookout-web")

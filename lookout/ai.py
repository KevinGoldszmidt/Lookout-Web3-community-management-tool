from __future__ import annotations
import requests
from .models import AIProvider, AgentConfig, KnowledgeChunk
from .security import decrypt_secret

MODEL_CATALOG = {
    "openai": [
        {"id": "gpt-4.1-mini", "label": "GPT-4.1 mini", "description": "Fast and inexpensive. Good default for frequent posts and replies."},
        {"id": "gpt-4.1", "label": "GPT-4.1", "description": "Stronger reasoning and quality, higher cost per token."},
        {"id": "gpt-4o-mini", "label": "GPT-4o mini", "description": "Balanced cost and quality, slightly older model."},
        {"id": "gpt-4o", "label": "GPT-4o", "description": "Balanced flagship, multimodal, higher cost."},
    ],
    "anthropic": [
        {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5", "description": "Fastest and cheapest. Good for simple replies and moderation."},
        {"id": "claude-sonnet-5", "label": "Claude Sonnet 5", "description": "Balanced default: strong quality at moderate cost. Recommended for most communities."},
        {"id": "claude-opus-5", "label": "Claude Opus 5", "description": "Highest quality and reasoning, higher cost. Use for complex or high-stakes content."},
        {"id": "claude-fable-5", "label": "Claude Fable 5", "description": "Tuned for creative and narrative writing."},
    ],
    "gemini": [
        {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash", "description": "Fast and inexpensive. Good default for most tasks."},
        {"id": "gemini-1.5-pro", "label": "Gemini 1.5 Pro", "description": "Higher quality and larger context, higher cost."},
    ],
}
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = {"openai": "gpt-4.1-mini", "anthropic": "claude-sonnet-5", "gemini": "gemini-2.0-flash"}


def _provider(project_id: int) -> AIProvider | None:
    return AIProvider.query.filter_by(project_id=project_id, is_default=True).order_by(AIProvider.id.desc()).first()


def _check(r, provider: str):
    if r.ok: return
    try: body = r.json()
    except ValueError: body = {}
    message = ((body.get("error") or {}).get("message")) if isinstance(body.get("error"), dict) else None
    raise RuntimeError(f"{provider} API error ({r.status_code}): {message or r.text[:300] or 'no details returned'}")


def generate(project_id: int, system: str, prompt: str, max_tokens: int = 700) -> str:
    p = _provider(project_id)
    if not p:
        raise RuntimeError("No AI provider configured")
    key = decrypt_secret(p.api_key_enc)
    provider = p.provider.lower()
    if not p.model.strip():
        raise RuntimeError(f"No model set for the {provider} provider")
    if provider == "openai":
        r = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json={"model": p.model, "messages": [{"role":"system","content":system},{"role":"user","content":prompt}], "max_tokens": max_tokens}, timeout=60)
        _check(r, "openai"); return r.json()["choices"][0]["message"]["content"].strip()
    if provider == "anthropic":
        r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key, "anthropic-version":"2023-06-01", "content-type":"application/json"}, json={"model": p.model, "system": system, "messages":[{"role":"user","content":prompt}], "max_tokens": max_tokens}, timeout=60)
        _check(r, "anthropic"); return "\n".join(x.get("text","") for x in r.json().get("content",[]) if x.get("type")=="text").strip()
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{p.model}:generateContent?key={key}"
        body = {"system_instruction":{"parts":[{"text":system}]},"contents":[{"role":"user","parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":max_tokens}}
        r = requests.post(url, json=body, timeout=60)
        _check(r, "gemini"); return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    raise RuntimeError(f"Unsupported AI provider: {p.provider}")


def retrieve(project_id: int, query: str, limit: int = 6) -> list[str]:
    terms = {t.lower().strip(".,!?()[]{}:;\"'") for t in query.split() if len(t) >= 3}
    chunks = KnowledgeChunk.query.filter_by(project_id=project_id).all()
    ranked = []
    for chunk in chunks:
        text = chunk.content.lower()
        score = sum(1 for t in terms if t in text)
        if score:
            ranked.append((score, chunk.content))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in ranked[:limit]]


def answer(project, community, message: str) -> str:
    agent = AgentConfig.query.filter_by(project_id=project.id).first() or AgentConfig(project_id=project.id)
    context = retrieve(project.id, message)
    context_text = "\n\n---\n\n".join(context) if context else "No relevant knowledge was retrieved."
    system = f"""You are {agent.name}, the official community assistant for {project.name}.
Tone: {agent.tone}.
Community primary language: {community.primary_language if community else 'unknown'}.
Reply in the language used by the member unless the message is ambiguous, then use the community primary language.
Never invent fees, promotions, dates, token details, product capabilities, regulatory claims, numbers, or support outcomes.
Use supplied company knowledge as the source of truth. If the knowledge does not support a concrete answer, say you do not know and direct the member to the configured support route.
Company description: {project.company_description or 'Not provided'}
Preferred terminology: {agent.preferred_terms or 'None'}
Forbidden terminology: {agent.forbidden_terms or 'None'}
Additional instructions: {agent.custom_instructions or 'None'}
"""
    prompt = f"COMPANY KNOWLEDGE:\n{context_text}\n\nMEMBER MESSAGE:\n{message}"
    return generate(project.id, system, prompt)

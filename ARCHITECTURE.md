# Lookout Architecture

## Product boundary

Lookout is multi-tenant at the application layer:

`Installation -> Organisation -> Project/Brand -> Community`

A self-hosted company may only use one organisation and one project. Agencies can use one installation for multiple client projects. The schema does not assume one deployment equals one brand.

## Runtime services

### Web
Flask admin application. Owns setup, login, roles, configuration, knowledge ingestion, analytics views, content automation configuration, and test actions.

### Telegram worker
Polls every active project's Telegram bot independently. Incoming updates are resolved to a Lookout community by project + Telegram chat ID. The worker performs moderation and only invokes the AI agent for DMs or explicit bot mentions.

### Scheduler
Checks enabled content automations and evaluates the configured local time independently for each community timezone. Delivery is recorded in Post History.

### PostgreSQL
The source of truth for users, organisations, roles, projects, communities, encrypted provider settings, knowledge, moderation, integrations, automations, events, escalations, and history.

## Provider boundaries

Lookout deliberately keeps external providers behind small modules:

- Community platform: Telegram now, Discord later
- AI: OpenAI / Anthropic / Gemini
- Escalation: Slack webhook / generic webhook
- Knowledge retrieval: local text ranking now, vector retrieval later
- Data providers: schema/templates are ready for market/news integrations; provider fetchers are a next implementation milestone

## Security model

Secrets are encrypted at rest with a deployment-owned Fernet key (`LOOKOUT_ENCRYPTION_KEY`). The encryption key itself must never be committed. A public repository contains only `.env.example`.

Role order:

Owner > Admin > Community Manager > Moderator > Viewer

Community-specific role scopes are represented in the schema (`Membership.community_scope`) but enforcement is deferred to the next permission milestone.

## Knowledge flow

1. Admin uploads PDF, DOCX, TXT, or Markdown.
2. Lookout extracts text and stores document metadata.
3. Content is chunked into retrievable passages.
4. On a member question, Lookout ranks project passages against the question.
5. The retrieved passages are placed in the AI prompt with strict no-invention rules.
6. The response is logged as an analytics event.

The retrieval API is intentionally isolated so embeddings/pgvector can replace text ranking without changing the upload workflow.

## Telegram token constraint

Each bot token must have only one active `getUpdates` poller. Lookout's Telegram worker owns polling for tokens configured inside that installation. Do not run the same project token simultaneously in Compass, another Lookout installation, or a second bot worker.

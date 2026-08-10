# Lookout

**AI-powered community management for Web3 teams. Telegram first.**

Lookout is a self-hostable, multi-organisation community operations platform built from the lessons of a production Telegram community system. Teams can connect their own Telegram bots, create unlimited language communities, upload company knowledge, choose their own AI provider, configure moderation, schedule multilingual content, escalate support issues, and review community analytics from one dashboard.

Lookout carries a small **"Lookout by Goldszmidt Media"** attribution in the UI.

## V1 capabilities

- Multi-organisation and multi-project architecture
- Owner, Admin, Community Manager, Moderator, Viewer roles
- First-run setup wizard
- Telegram bot connection per project
- Unlimited Telegram groups/channels with language + timezone settings
- OpenAI, Anthropic, and Gemini API-key support
- Uploaded knowledge base: PDF, DOCX, TXT, Markdown
- Retrieval-grounded AI community assistant
- Configurable agent name, tone, instructions, terminology, and fallback behaviour
- Multilingual detection/replies and community-language content
- Toggle-based moderation rules with configurable actions
- Slack webhook escalation and generic webhook support
- Prebuilt Web3 content templates + custom AI content automations
- Per-community schedules and manual test posts
- Post history and analytics event tracking
- Docker Compose deployment with PostgreSQL

## Quick start

1. Copy `.env.example` to `.env`.
2. Generate a Fernet key:

   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

3. Put that value in `LOOKOUT_ENCRYPTION_KEY` and set a long `FLASK_SECRET_KEY`.
4. Run `docker compose up --build`.
5. Open `http://localhost:8080` and complete the first-run setup.
6. Create a Telegram bot with BotFather, add it to the desired group/channel, give it the permissions required for moderation/posting, then connect its token in Lookout.

## Public-repository safety

Never commit real Telegram tokens, AI keys, Slack webhooks, group IDs, production databases, uploaded knowledge, or runtime logs. Lookout stores provider credentials encrypted at rest using `LOOKOUT_ENCRYPTION_KEY`.

## Architecture

Three services share PostgreSQL:

- `web`: Flask admin application
- `telegram-worker`: polls all active project bot tokens and processes messages
- `scheduler`: executes enabled content automations

The integration boundaries are intentionally provider-based so Discord and additional data/AI providers can be added later.

## Current limitations

This is the V1 foundation, not a finished enterprise SaaS. Telegram is the only community platform. Trivia competitions are intentionally deferred. Knowledge retrieval uses local text ranking rather than vector embeddings, but the retrieval interface is isolated so vector search can be introduced later.

## License

Choose a license before public release. If you want attribution preserved in forks, review an appropriate source-available or open-source licensing strategy with counsel rather than relying on UI text alone.

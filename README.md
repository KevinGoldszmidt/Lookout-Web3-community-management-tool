# Lookout

Lookout is a self-hosted tool for running a Telegram community. You connect your own Telegram bot and your own AI provider key, and Lookout runs a community assistant that answers member questions from knowledge you upload, moderates chat automatically, posts scheduled content, and gives you analytics — all from one web dashboard.

"Self-hosted" means you run it yourself with Docker Compose, on your own server. Nobody else hosts your data or sees your keys.

It's built for Web3 communities specifically today, but nothing about the core is Web3-only, so other spaces may follow.

Lookout carries a small "Lookout by Goldszmidt" attribution in the UI.

## V1.2 capabilities

- Multi-organisation and multi-project, with five roles from Owner to Viewer
- One Telegram bot per project, unlimited groups and channels, each with its own language and timezone. Channels are posting destinations only — moderation and the assistant run in the linked group
- Bring your own AI key — OpenAI, Anthropic, or Gemini — picked from a curated model list per provider, or entered as a custom model ID
- A community assistant grounded in knowledge you upload as PDF, DOCX, TXT, or Markdown
- Full control of the agent's name, tone, terminology, instructions, and what it does when it doesn't know
- Replies in the member's language, scheduled content in the community's
- Moderation rules you toggle on and off, each with its own action, checked in a fixed and documented order
- Escalation and moderation alerts to Slack or any webhook, with a "send test message" button and a live delivery status per integration
- A live setup checklist that gates the dashboard and flags exactly what's still missing, plus delete support throughout (communities, automations, integrations, team members, projects), each behind a confirmation
- Prebuilt content templates plus your own automations, with post history and analytics filterable by date range, community, and event type
- An in-app FAQ/guide and a rendered copy of this README, so day-to-day questions don't require leaving the app
- Docker Compose and PostgreSQL, with Alembic migrations and a first-run setup wizard

## Before you start

You need three things ready.

**Docker.** Docker Engine or Docker Desktop with Compose v2, so that `docker compose version` works. Port 8080 must be free.

**An AI provider key.** One of OpenAI, Anthropic, or Google Gemini. Lookout does not ship a key. You pick the model from a dropdown once you're in the app (for example `gpt-4.1-mini`, `claude-sonnet-5`, or `gemini-2.0-flash`), or enter a custom model ID if yours isn't listed.

**A Telegram bot, configured correctly.** This is the step most people get wrong, so it is spelled out below.

### Creating the Telegram bot

1. Message `@BotFather` and send `/newbot`. Save the token it gives you.
2. Send `/setprivacy`, choose your bot, and select **Disable**.
3. Add the bot to your group, then promote it to admin with permission to delete messages and to post.

Step 2 is not optional. Telegram bots default to privacy mode on, which means they only receive messages that mention them, reply to them, or start with a command. Lookout logs every message and runs moderation on every message, so with privacy mode left on, moderation and analytics will silently do nothing while the rest of the app appears healthy. If you already added the bot before changing this setting, remove it from the group and add it again, because the privacy setting only takes effect from the moment the bot joins.

### Finding your group chat ID

Lookout asks for a numeric chat ID when you add a community, and there is no in-app lookup. Get it before you start the stack, because once the `telegram-worker` container is running it consumes pending updates and this call will come back empty.

Send any message in the group, then run:

```
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
```

Read `result[].message.chat.id`. Supergroup IDs are negative and begin with `-100`. Keep the minus sign.

## Quick start

1. Clone and enter the repository.

   ```
   git clone https://github.com/KevinGoldszmidt/Lookout-Web3-community-management-tool.git
   cd Lookout-Web3-community-management-tool
   ```

2. Copy `.env.example` to `.env`.

   ```
   cp .env.example .env
   ```

3. Generate an encryption key. This uses only the Python standard library, so nothing needs installing first.

   ```
   python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
   ```

   Put the result in `LOOKOUT_ENCRYPTION_KEY`.

4. Generate a session secret and put it in `FLASK_SECRET_KEY`.

   ```
   python3 -c "import secrets;print(secrets.token_hex(32))"
   ```

   Those two values are the only ones you must change. Everything else in `.env` works as shipped for local use.

5. Start the stack.

   ```
   docker compose up --build
   ```

   A one-shot `init` service applies the database migrations before the app, worker, and scheduler start. You do not need to run a migration command yourself.

6. Open `http://localhost:8080` and complete the first-run wizard. It creates your owner account, organisation, and first project. The password must be at least 10 characters. You'll land on a **Setup checklist** — it tracks the three steps below against your actual project state and won't let you forget one.

7. Go to **Telegram** and paste your bot token. Lookout verifies it against Telegram and stores it encrypted. A failure here usually means `LOOKOUT_ENCRYPTION_KEY` is not a valid Fernet key, since that value is not checked at startup.

8. Go to **AI Agent**, choose your provider and model from the dropdown (or enter a custom model ID), add your API key, and save. The assistant will not answer at all until this is done.

9. Go to **Communities** and add your group using the chat ID from above, along with its language and timezone (both are searchable dropdowns, so typos can't silently break a community).

10. Test it. In the group, send a message that mentions the bot by its username. In groups the assistant only replies when mentioned. In a direct message to the bot it always replies.

To skip the wizard on a fresh database, set `BOOTSTRAP_OWNER_EMAIL` and `BOOTSTRAP_OWNER_PASSWORD` in `.env` before first boot and an owner, organisation, and project will be created for you.

## Where secrets live

Two places, and the split matters.

`.env` holds only `FLASK_SECRET_KEY` and `LOOKOUT_ENCRYPTION_KEY`. You generate both yourself. Neither is a third-party credential.

Everything else is entered through the web UI and stored encrypted in the database, scoped to a project rather than to the server. The Telegram bot token goes on the Telegram page, the AI provider key on the AI Agent page, and Slack or generic webhook URLs on the Integrations page. Each project needs its own AI provider key. There is no organisation-level fallback.

`LOOKOUT_ENCRYPTION_KEY` decrypts all of it, so back it up separately from the database.

## Running it day to day

```
docker compose logs -f telegram-worker    # see incoming messages and errors
docker compose logs -f web                # admin app
docker compose down                       # stop, data is preserved
docker compose up --build -d              # restart in the background
```

Your data lives in the `lookout_db` Docker volume and in `./uploads` on the host. Back up both. Back up `LOOKOUT_ENCRYPTION_KEY` separately, because losing it makes every stored bot token and API key unrecoverable.

## Troubleshooting

**The bot ignores everything in the group.** Privacy mode is still on, or the chat ID is wrong. Check `docker compose logs -f telegram-worker` while sending a message. Silence means Telegram is not delivering the update to the bot at all.

**Telegram returns 409 Conflict.** Something else is polling the same token, or a webhook is registered on it. Only one consumer can use `getUpdates` at a time. Stop the other process, or clear the webhook with `deleteWebhook`.

**The assistant replies that it cannot answer reliably.** The AI provider call is failing. The exact error is stored as an `ai_error` event and appears in the worker logs. Usually a bad key or an invalid model name.

**Moderation never fires.** Confirm moderation is toggled on for that specific community, not just configured at project level.

## Architecture

Four services share PostgreSQL.

- `init`: one-shot service that applies database migrations, then exits. The other three wait for it to succeed before starting, so schema changes only ever run once
- `web`: Flask admin application served by gunicorn
- `telegram-worker`: polls all active project bot tokens and processes messages
- `scheduler`: executes enabled content automations

The integration boundaries are intentionally provider-based so Discord and additional data/AI providers can be added later.

## Running this beyond localhost

The shipped configuration is for local use. Before putting it on a server:

- Change the Postgres password in `docker-compose.yml`, which is currently `lookout` for both user and password
- Put it behind a reverse proxy with TLS, since gunicorn serves plain HTTP
- Set `LOOKOUT_COOKIE_SECURE=1` and update `LOOKOUT_BASE_URL`
- Do not publish the database port

## Current limitations

This is a foundation, not a finished enterprise SaaS. Telegram is the only community platform. Knowledge retrieval uses local text ranking rather than vector embeddings, but the retrieval interface is isolated so vector search can be introduced later.

The three prebuilt templates that depended on live market data (Daily Market Analysis, Market Spotlight, Evening Recap) were removed, since nothing fetched that data and the model would invent numbers. The remaining templates (Crypto Trends, Term of the Day, Market Poll, Community Feedback) do not depend on live data.

## Coming next

**Competitions.** A Competitions tab where you'll be able to build campaigns out of trivia quests and challenges, with a leaderboard your community can watch update in real time.

**Feature requests.** If there's something you need that isn't here, open an issue on this repository or reach out directly. Real requests from self-hosters are the fastest way to shape what gets built next.

## Never commit

Real Telegram tokens, AI keys, Slack webhooks, group IDs, production databases, uploaded knowledge, or runtime logs. Run a secret scanner such as Gitleaks against the full git history before making this repository public. Rotating a credential is safer than assuming a deleted commit removed it.

## License

Copyright (C) 2026 Kevin Goldszmidt.

Licensed under the [GNU Affero General Public License v3.0](https://github.com/KevinGoldszmidt/Lookout-Web3-community-management-tool/blob/main/LICENSE) (AGPL-3.0). In short: you're free to self-host, use, and modify Lookout, including commercially. If you run a modified version as a network service for others, you must make that modified source available to those users under the same license. This is what makes AGPL different from MIT/Apache-style licenses — it closes the loophole where someone could take the code, host it, and never share their changes back.

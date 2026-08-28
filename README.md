# Lookout

Lookout by Goldszmidt is a self-hostable, multi-organisation community management platform built to work with Telegram.

Teams can connect their own Telegram bots, create language communities, upload company knowledge, choose their own AI provider, configure moderation, schedule multilingual content, escalate support issues, and review community analytics from one dashboard.

At the moment this is built for Web3 specifically, but I'm looking into other spaces to broaden the usage.

Lookout carries a small "Lookout by Goldszmidt" attribution in the UI.

## V1.2 capabilities

- Multi-organisation and multi-project, with five roles from Owner to Viewer
- One Telegram bot per project, unlimited groups and channels, each with its own language and timezone
- Bring your own AI key. OpenAI, Anthropic, or Gemini
- A community assistant grounded in knowledge you upload as PDF, DOCX, TXT, or Markdown
- Full control of the agent's name, tone, terminology, instructions, and what it does when it doesn't know
- Replies in the member's language, scheduled content in the community's
- Moderation rules you toggle on and off, each with its own action
- Escalation to Slack or any webhook
- Prebuilt content templates plus your own automations, with post history and analytics
- Docker Compose and PostgreSQL, with a first-run setup wizard

## Before you start

You need three things ready.

**Docker.** Docker Engine or Docker Desktop with Compose v2, so that `docker compose version` works. Port 8080 must be free.

**An AI provider key.** One of OpenAI, Anthropic, or Google Gemini. Lookout does not ship a key. Have the key and the model name you intend to use, for example `gpt-4.1-mini`, `claude-sonnet-4-5`, or `gemini-2.0-flash`.

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

   The database schema is created automatically on first boot. There is no migration command to run.

6. Open `http://localhost:8080` and complete the first-run wizard. It creates your owner account, organisation, and first project. The password must be at least 10 characters.

7. Go to **Telegram** and paste your bot token. Lookout verifies it against Telegram and stores it encrypted. A failure here usually means `LOOKOUT_ENCRYPTION_KEY` is not a valid Fernet key, since that value is not checked at startup.

8. Go to **AI Agent**, choose your provider, enter the model name and API key, and save. The assistant will not answer at all until this is done.

9. Go to **Communities** and add your group using the chat ID from above, along with its language and timezone.

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

Three services share PostgreSQL.

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

This is a foundation, not a finished enterprise SaaS. Telegram is the only community platform. Trivia competitions are intentionally deferred. Knowledge retrieval uses local text ranking rather than vector embeddings, but the retrieval interface is isolated so vector search can be introduced later.

The prebuilt market-related content templates carry `data_sources` tags such as `market_data` and `news`, but no live data is fetched yet. Those templates ask the model for market movement and catalysts it has no source for, so the output can be confidently wrong. Treat Daily Market Analysis, Market Spotlight, and Evening Recap as unsuitable for live communities until a data source is wired in.

## Never commit

Real Telegram tokens, AI keys, Slack webhooks, group IDs, production databases, uploaded knowledge, or runtime logs. Run a secret scanner such as Gitleaks against the full git history before making this repository public. Rotating a credential is safer than assuming a deleted commit removed it.

## License

Not yet licensed. Without a license file, no one has permission to use, copy, or modify this code, and the attribution line in the UI carries no legal weight on its own.

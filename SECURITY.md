# Security Notes

## Never commit

- `.env`
- Telegram bot tokens
- AI provider keys
- Slack webhook URLs
- Telegram group/channel IDs from real communities
- production database dumps
- uploaded customer documents
- production logs

## Before migrating from Compass

The source Compass server/archive contains live credentials and IDs. Do not copy its `.env`, `communities.json`, runtime SQLite database, logs, drafts, or generated content into this repository.

Create fresh credentials for Lookout testing. If a production Telegram token is later moved from Compass to Lookout, stop the old poller before starting Lookout with that token.

## Encryption

Provider secrets are encrypted with Fernet using `LOOKOUT_ENCRYPTION_KEY`. Back up the key securely. Losing it makes stored integration credentials unrecoverable.

## Public release checklist

Run a secret scanner such as Gitleaks against the full git history before making the repository public. Also inspect generated archives manually. Rotating credentials is safer than assuming deletion from a commit removes exposure.

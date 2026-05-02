# Toxic Analyzer Discord Bot

`bots/discord` is a standalone TypeScript Discord bot. It listens to configured Discord channels, sends message text to the public backend API, and posts alerts when the backend returns `label === 1`.

The bot is a backend client only:

- it calls `POST /api/v1/toxicity/analyze`
- it does not call `model/` directly
- it keeps all bot-specific settings inside `bots/discord`
- it does not require backend changes for MVP

## Requirements

- Node.js `24.x`
- npm `11.x`
- a running backend instance with `POST /api/v1/toxicity/analyze`
- a Discord application with a bot token

## Install

```powershell
cd bots/discord
npm install
```

## Discord Setup

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application.
3. Add a bot user on the `Bot` page.
4. Copy the bot token into `.env`.
5. Enable `MESSAGE CONTENT INTENT`.
6. Invite the bot with permissions needed for:
   - viewing channels in `scanChannelIds`
   - reading messages in `scanChannelIds`
   - sending messages in `alertChannelId`
   - embedding links in `alertChannelId`

Required intents in code:

- `Guilds`
- `GuildMessages`
- `MessageContent`

## Configuration

Runtime configuration is split into:

- `.env` for secrets and process-level settings
- `config.json` for bot behavior

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Create `config.json` from `config.example.json`:

```powershell
Copy-Item config.example.json config.json
```

### `.env`

- `DISCORD_TOKEN` - bot token from Discord Developer Portal
- `BOT_CONFIG_PATH` - optional path to config JSON, defaults to `./config.json`
- `BACKEND_AUTH_TOKEN` - optional pre-issued backend bearer token
- `BACKEND_SERVICE_CLIENT_ID` - optional backend service client id
- `BACKEND_SERVICE_CLIENT_SECRET` - optional backend service client secret
- `LOG_LEVEL` - optional pino log level, defaults to `info`

### `config.json`

- `backendBaseUrl` - backend public base URL, for example `http://localhost:5068`
- `backendTimeoutMs` - timeout for analyze requests
- `scanChannelIds` - channel IDs the bot scans
- `alertChannelId` - channel ID where alerts are posted
- `analyzeConcurrency` - max concurrent message analyses
- `alertTemplate` - Discord message payload template with placeholders

Example:

```json
{
  "backendBaseUrl": "http://localhost:5068",
  "backendTimeoutMs": 10000,
  "scanChannelIds": ["123456789012345678"],
  "alertChannelId": "987654321098765432",
  "analyzeConcurrency": 4,
  "alertTemplate": {
    "content": "Toxic message detected in {channelMention} by {authorMention}",
    "embeds": [
      {
        "title": "Toxicity Alert",
        "description": "Message: {messageText}\nProbability: {toxicProbability}\nFeatures:\n{features}",
        "color": 15158332,
        "author": {
          "name": "{authorTag}"
        }
      }
    ],
    "attachments": []
  }
}
```

## Run

Development:

```powershell
npm run dev
```

Production build:

```powershell
npm run build
npm run start
```

Checks:

```powershell
npm run check
```

## Backend URL

Set `backendBaseUrl` in `config.json`. Example local value:

- `http://localhost:5068`

The bot sends:

```json
{
  "text": "<discord message content>",
  "reportLevel": "full"
}
```

to:

- `POST {backendBaseUrl}/api/v1/toxicity/analyze`

## Optional Backend Service Auth

The bot still works against the public anonymous analyze endpoint. If you want it to act as an identified backend service client, configure `BACKEND_SERVICE_CLIENT_ID` and `BACKEND_SERVICE_CLIENT_SECRET` in `.env`.

At runtime the bot will:

1. call `POST {backendBaseUrl}/api/v1/auth/service-token`
2. cache the short-lived bearer token
3. reuse it for analyze requests until it nears expiration

`BACKEND_AUTH_TOKEN` is still supported for pre-issued bearer tokens, but backend-issued client credentials are the preferred flow.

## Supported Placeholders

- `{messageText}`
- `{messageUrl}`
- `{messageId}`
- `{channelId}`
- `{channelMention}`
- `{guildId}`
- `{authorId}`
- `{authorUsername}`
- `{authorTag}`
- `{authorMention}`
- `{label}`
- `{toxicProbability}`
- `{analysisId}`
- `{modelKey}`
- `{modelVersion}`
- `{reportLevel}`
- `{createdAt}`
- `{calibratedProbability}`
- `{adjustedProbability}`
- `{threshold}`
- `{features}`
- `{featuresJson}`

Placeholders are replaced only from this whitelist. Unknown placeholders are left unchanged. The renderer does not execute code.

## Template Notes

- Placeholders work in `content` and embed string fields.
- `allowed_mentions` defaults to `{ "parse": [] }` when omitted.
- Non-empty `attachments` are unsupported in MVP and rejected by config validation.
- `features` is rendered as a readable multi-line list.
- `featuresJson` is rendered as JSON.

## MVP Limitations

- scans only `messageCreate`; `messageUpdate` is ignored
- ignores bot messages, including its own
- ignores messages outside `scanChannelIds`
- ignores blank or whitespace-only messages
- decides only from `label === 1`
- no threshold logic in the bot
- no moderation actions beyond posting an alert
- no backend-provided settings
- no multi-guild config model yet
- no slash commands
- no storage/history
- backend auth is optional; service-token flow is supported
- no support for non-empty outbound attachments

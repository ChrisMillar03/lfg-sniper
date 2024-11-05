# lfg-sniper
Discord self bot to forward R6 Discord lfg messages to a webhook.

This project is currently configured to work with the R6 Discord but can be adapted to similar servers.

## Example channels.json
```json
{
    "channel_id": "webhook"
}
```

## .env keys
```
TOKEN=
WEBHOOKS=
```

channels.json is I/O channels for running commands where the webhook should target the channel ID provided as the key
and WEBHOOKS is the actual output webhooks for the bot. (if using multiple webhooks seperate them with whitespace)

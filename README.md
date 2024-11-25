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
OWNER_ID=
```

Make sure the user has read message history permissions for any command channels specified in channels.json

# crypto-invest-bot

Automated scheduled crypto investing on Kraken with Telegram notifications.

## Features

- **Scheduled Orders**: Buy/sell crypto on cron schedules (daily, weekly, etc.)
- **Scheduled Staking**: Automatically stake assets to earn yield
- **Telegram Alerts**: Get notified on successful actions and errors
- **Docker Deployment**: Easy server deployment via SSH

## Project Structure

```
crypto-invest-bot/
├── app.py                 # Entry point
├── settings.yaml          # Bot configuration (actions, schedules)
├── .env                   # Secrets (not committed)
├── .env.example           # Template for secrets
├── requirements.txt
├── Dockerfile
├── deploy.sh              # Deploy to remote server
│
└── src/
    ├── bot.py             # Main bot orchestrator
    ├── schemas.py         # Pydantic models
    ├── scheduler.py       # Cron job scheduler
    ├── kraken/
    │   ├── client.py      # Base HTTP client with auth
    │   ├── trading.py     # Buy/sell operations
    │   └── earn.py        # Staking operations
    ├── notifications/
    │   └── telegram.py    # Telegram notifications
    └── utils/
        ├── logging.py     # Logging setup
        └── settings.py    # Settings loader
```

## Setup

### 1. Clone and configure

```bash
git clone git@github.com:sukiboo/crypto-invest-bot.git
cd crypto-invest-bot

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys
```

### 2. Configure actions in `settings.yaml`

Use exact Kraken trading pairs and asset names (see [Kraken Asset Pairs](https://support.kraken.com/hc/en-us/articles/360001185506)):

```yaml
bot_name: crypto-invest-bot

actions:
  # Order action (buy/sell)
  - name: "Buy ETH"
    type: order
    pair: XETHZUSD  # use Kraken pair name
    side: buy  # buy | sell
    amount: 10.00  # amount in corresponding currency (USD)
    schedule: "0 0 * * *"  # every day at 00:00 UTC

  # Earn action (stake all available)
  - name: "Stake all ETH"
    type: earn
    asset: XETH  # use Kraken asset name
    strategy: restaking  # instant | flex | bonded | restaking
    amount: null  # null = stake all available
    schedule: "0 1 * * *"  # every day at 01:00 UTC
```

**Note:** All schedules are in **UTC**.

**Action types:**

| Type | Required fields | Optional |
|------|-----------------|----------|
| `order` | `pair`, `side`, `amount` | `order_type` (default: market) |
| `earn` | `asset`, `strategy` | `amount` (default: null = all) |

**Earn strategies:**
- `flex` - Flexible, withdraw anytime
- `bonded` - Bonded staking (~11 days lock)
- `restaking` - Bonded restaking (~19 days lock, highest rewards)
- `instant` - Instant rewards

### 3. Get API Keys

**Kraken API:**
1. Go to [Kraken Security Settings](https://www.kraken.com/u/security/api)
2. Create a new API key with permissions: Query Funds, Create & Modify Orders, Earn Funds
3. Copy the key and secret to `.env`

**Telegram Bot:**
1. Message [@BotFather](https://t.me/BotFather) and create a new bot
2. Copy the bot token to `.env`
3. Message your bot, then get your user ID from [@userinfobot](https://t.me/userinfobot)
4. Add your user ID to `.env`

## Running

### Local Development

```bash
pip install -r requirements.txt
python app.py
```

### Docker (Local)

```bash
docker build -t crypto-invest-bot .
docker run -d --name crypto-invest-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  crypto-invest-bot
```

### Deploy to Server

```bash
# Ensure .env has SERVER_USER, SERVER_HOST, SERVER_PATH set
./deploy.sh
```

## Cron Schedule Examples (UTC)

| Schedule | Cron Expression |
|----------|-----------------|
| Every day at 9:00 | `0 9 * * *` |
| Every Sunday at 10:00 | `0 10 * * 0` |
| Every Monday and Friday at 8:30 | `30 8 * * 1,5` |
| First day of month at 12:00 | `0 12 1 * *` |
| Every 6 hours | `0 */6 * * *` |

## License

MIT

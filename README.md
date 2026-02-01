# crypto-invest-bot 🗓️🐙📨

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
├── settings.yaml          # Schedule configuration (not committed)
├── settings.example.yaml  # Template for schedule configuration
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

**Prerequisites:** pyenv and pyenv-virtualenv (install via `brew install pyenv pyenv-virtualenv` on macOS)

```bash
# 1. Clone repository
git clone git@github.com:sukiboo/crypto-invest-bot.git
cd crypto-invest-bot

# 2. Install Python and create virtual environment
pyenv install 3.12.11
pyenv virtualenv 3.12.11 crypto-invest-bot
pyenv local crypto-invest-bot

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment and settings
cp .env.example .env
cp settings.example.yaml settings.yaml
# Edit .env with your API keys and settings.yaml with your actions
```

**Get API Keys:**

- **Kraken:** [Create API key](https://www.kraken.com/u/security/api) with permissions: `Query Funds`, `Create & Modify Orders`, `Earn Funds`
- **Telegram:** Message [@BotFather](https://t.me/BotFather) to create a bot, get your user ID from [@userinfobot](https://t.me/userinfobot)

## Configure

Copy and edit `settings.example.yaml`:

```bash
cp settings.example.yaml settings.yaml
```

Example configuration:

```yaml
bot_name: crypto-invest-bot

actions:
  # Daily DCA - buy every day at noon UTC
  - name: "Daily BTC"
    type: order
    pair: BTCUSD
    side: buy
    amount: 20.00
    schedule: "0 12 * * *"

  # Weekly buy - every Monday
  - name: "Weekly SOL"
    type: order
    pair: SOLUSD
    side: buy
    amount: 50.00
    schedule: "0 9 * * 1"

  # Auto-stake after purchase
  - name: "Stake ETH"
    type: earn
    asset: ETH
    strategy: restaked
    amount: null  # null = stake all available
    schedule: "1 12 * * *"
```

**Note:** All schedules are in **UTC**. Both `ETHUSD` and `XETHZUSD` formats work for pairs.

**Action types:**

| Type | Required fields | Optional |
|------|-----------------|----------|
| `order` | `pair`, `side`, `amount` | `order_type` (default: `market`) |
| `earn` | `asset`, `strategy` | `amount` (default: `null` = all) |

**Earn strategies:**

Available strategies depend on the asset and are determined by querying Kraken's API.
The bot maps strategy names to Kraken's lock types:

- `flexible` -- **Flexible staking**: Maps directly to Kraken's "flexible" staking strategy. No lock period, withdraw anytime. Lower rewards but maximum liquidity. Also known as "Auto Earn" or "Flexible Opt-In Rewards" in Kraken's UI.
- `bonded` -- **Bonded staking**: Maps to Kraken's "bonded" staking strategy with the shortest unbonding period. For most coins, this is the only bonded option available. Assets are locked during the bonding period, then have an unbonding period before funds become available. Higher rewards than `flexible`.
- `restaked` -- **Bonded restaking**: Maps to Kraken's "bonded" staking strategy with the longest unbonding period. For most coins, this will be the same strategy as `bonded` (since they only have one bonded option). For assets like ETH that support restaking, this selects the restaking option with the longest lock period. Highest rewards available, but longest commitment with extended unbonding periods.

**Note:** Lock periods and unbonding periods vary by asset. Most coins only offer `flexible` and `bonded` options. Only certain assets like ETH offer a separate restaking option. Check Kraken's [Earn documentation](https://support.kraken.com/hc/articles/360044886311-overview-of-opt-in-rewards-on-kraken) for specific details per asset. For most assets `restaked` will map to `bonded`.

## Running

### Local Development

Make sure you're in the project directory (pyenv will auto-activate the virtual environment):

```bash
cd crypto-invest-bot
python app.py
```

If the virtual environment isn't active, you can manually activate it:
```bash
pyenv activate crypto-invest-bot
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

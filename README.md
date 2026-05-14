# crypto-invest-bot 🗓️🐙📨

Automated scheduled crypto investing on Kraken with Telegram notifications.

## Features

- **Scheduled Orders**: Buy/sell crypto on cron schedules (daily, weekly, etc.)
- **Scheduled Staking**: Automatically stake assets to earn yield
- **Cash Runway Check**: Proactive Telegram warning when quote balances won't cover upcoming buys
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
    ├── actions/
    │   ├── base.py            # Action ABC + ActionContext
    │   ├── order.py           # Buy/sell market orders
    │   ├── earn.py            # Stake actions
    │   ├── check_runway.py    # Quote-balance forecast
    │   ├── maintain_reserve.py
    │   └── utils.py           # Shared helpers (upcoming-buy forecast)
    ├── kraken/
    │   ├── client.py      # Base HTTP client with auth
    │   ├── trading.py     # Order placement + ledger reconciliation
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
  # Daily DCA in USDC - buy every day at noon UTC
  - name: "Daily ETH"
    type: order
    pair: ETHUSDC
    side: buy
    amount: 20.00
    schedule: "0 12 * * *"

  # Weekly buy in USD - every Monday
  - name: "Weekly BTC"
    type: order
    pair: BTCUSD
    side: buy
    amount: 50.00
    schedule: "0 9 * * 1"

  # Auto-stake after purchase
  - name: "Stake ETH"
    type: earn
    asset: XETH
    strategy: restaked
    amount: null  # null = stake all available
    schedule: "1 12 * * *"

  # Daily check that each quote balance covers the next 7 days of buys
  - name: "Check cash runway"
    type: check_runway
    days: 7
    schedule: "0 12 * * *"
```

**Note:** All schedules are in **UTC**. Both `ETHUSD` and `XETHZUSD` formats work for pairs.

**Action types:**

| Type | Required fields | Optional |
|------|-----------------|----------|
| `order` | `pair`, `side` | `amount` (null/omit = full balance of the relevant side), `order_type` (default: `market`) |
| `earn` | `asset`, `strategy` | `amount` (null/omit = stake all available) |
| `check_runway` | `days` | — |

**Order notifications (buys vs. sells):**

All filled-order values come from Kraken's `/0/private/Ledgers` endpoint — the bot reads the precise gross and fee for each side of the trade (no approximations) and formats accordingly.

Buy orders use `oflags=viqc,fcib` (volume in quote currency, fee deducted from the bought base asset):

```
✔️ Buy SOL: buy 0.25819917 SOL for 25.00 USDC @ 96.85 USDC/SOL
                ^^^^^^^^^^^^^^      ^^^^^^^^^      ^^^^^^^^^^^^^
                net base credited   gross quote    effective price
                (gross - fee_base)  paid           (gross_quote / net_base)
```

Sell orders use the default oflags (fee deducted from the quote proceeds):

```
✔️ Sell SOL: sell 0.27421301 SOL for 24.90 USD @ 90.80 USD/SOL
                  ^^^^^^^^^^^^^^      ^^^^^^^      ^^^^^^^^^^^^
                  gross base sold     net quote    effective price
                                      received     (net_quote / gross_base)
```

The receiving side is always reported **net of its fee** (matching the credit/debit on the ledger), and the effective price uses the same net side, so `price × volume` reconciles to the gross paid/received.

**Earn strategies:**

Available strategies depend on the asset and are determined by querying Kraken's API.
The bot maps strategy names to Kraken's lock types:

- `flexible` -- **Flexible staking**: Maps directly to Kraken's "flexible" staking strategy. No lock period, withdraw anytime. Lower rewards but maximum liquidity. Also known as "Auto Earn" or "Flexible Opt-In Rewards" in Kraken's UI.
- `bonded` -- **Bonded staking**: Maps to Kraken's "bonded" staking strategy with the shortest unbonding period. For most coins, this is the only bonded option available. Assets are locked during the bonding period, then have an unbonding period before funds become available. Higher rewards than `flexible`.
- `restaked` -- **Bonded restaking**: Maps to Kraken's "bonded" staking strategy with the longest unbonding period. For most coins, this will be the same strategy as `bonded` (since they only have one bonded option). For assets like ETH that support restaking, this selects the restaking option with the longest lock period. Highest rewards available, but longest commitment with extended unbonding periods.

**Note:** Lock periods and unbonding periods vary by asset. Most coins only offer `flexible` and `bonded` options. Only certain assets like ETH offer a separate restaking option. Check Kraken's [Earn documentation](https://support.kraken.com/hc/articles/360044886311-overview-of-opt-in-rewards-on-kraken) for specific details per asset. For most assets `restaked` will map to `bonded`.

**Cash runway check:**

Kraken doesn't expose a clean way to auto-replenish quote balances, so the bot can warn you when the account is about to run dry. A `check_runway` action groups upcoming `buy` orders by their **quote currency** (USD, USDC, …), sums the required spend over the next `days`, and compares each quote's `spot + earn-allocated` balance against that requirement. `earn` comes from `/Earn/Allocations` so funds you've staked still count toward your runway (you can deallocate them before the buy hits).

- **Sufficient balance** -- the result is logged only and sent silently to Telegram (no phone notification).
- **Insufficient balance** -- a Telegram alert (with phone notification) shows total balance vs. liability per quote, then the upcoming buys that drain each:
  ```
  ❌ 7d runway low
  Balance
      100.00 USDC < 140.00 USDC
      100.00 USD > 50.00 USD
  Actions
      Daily ETH: 7 x 20.00 USDC = 140.00 USDC
      Weekly BTC: 1 x 50.00 USD = 50.00 USD
  ```
  Balances are quote-by-quote — there's no cross-currency netting, so a USD shortfall is flagged even if you have excess USDC.

You can run multiple `check_runway` actions with different horizons -- e.g., a frequent short-window check for urgency and a weekly long-window check for planning.

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

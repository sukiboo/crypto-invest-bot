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
    strategy: bonded
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

Available strategies depend on the asset and are determined by querying Kraken's API. Only
strategies Kraken reports as `can_allocate` are eligible. `strategy` takes one of two forms:

- `bonded` -- **Bonded staking**: funds are locked, with an unbonding period (3-14 days depending on the asset) before they return to spot. Roughly 2× the unlocked rate. Resolves to the asset's single allocatable bonded strategy.
- `ESPB45U-RZV2F-T6UO3H` -- an **explicit strategy id**, which reaches any allocatable strategy regardless of lock type. Use it to pin a specific pool, or when `bonded` is ambiguous. Validated at startup against the asset's allocatable strategies.

**Note:** not every asset offers bonded staking -- of the 33 assets with earn strategies, 24
do; ADA, MINA and TAO are instant-only, and 7 (USDC, USDG, RLUSD, SN*) are flex-only. Invalid
combinations are rejected at startup with the asset's actual options listed.

Kraken's other two lock types are deliberately not keywords:

- `flex` is never allocatable (all 33 report `can_allocate: false`). Kraken auto-allocates idle spot into it and still reports the balance as spendable, so those assets already earn with no action at all. Scheduling one fails at startup telling you to remove it.
- `instant` pays **exactly the flex rate on all 24 assets that offer it** — so allocating to it earns what the coin already earns sitting idle, while making the balance unspendable until deallocated. It is strictly worse than doing nothing, so it gets no keyword. It remains reachable by explicit id if you want it anyway (e.g. with account-level auto-earn switched off).

If two allocatable strategies ever share a lock type, the bot refuses to guess and asks you to
name the id. This is what would have caught the ETH restaking deprecation: `restaked` (a former
value meaning "the bonded strategy with the longest unbonding period") silently resolved to
Kraken's EigenLayer pool, which was closed to new allocations on 2026-07-30 while remaining
visible in the API.

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

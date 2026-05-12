Here's the proper API workflow, with the likely cause of your failure flagged at the end.

**Endpoints:**
- Allocate: `POST /0/private/Earn/Allocate`
- Deallocate: `POST /0/private/Earn/Deallocate`
- Status polling: `POST /0/private/Earn/AllocateStatus` and `/Earn/DeallocateStatus`
- List strategies: `POST /0/private/Earn/Strategies`
- List your allocations: `POST /0/private/Earn/Allocations`

**Body parameters** (POST body, `application/x-www-form-urlencoded`):
```
nonce=<unix_ms>
amount=<string, e.g. "100.0">
strategy_id=<string, e.g. "ESXQXU5-WDDR5-GWA7VY">
```

**Auth headers:**
- `API-Key: <your key>`
- `API-Sign: base64(HMAC-SHA512(URI_PATH + SHA256(nonce + post_body), base64_decode(secret)))`

**API key permissions required:** `Earn Funds` (specifically — *not* `Query Funds`, which only lets you read). This is the most common reason API earn calls fail when the UI works. The UI uses your full session; the API key is scoped.

**Async behavior:** Allocate returns `200` (or `202`) immediately, but the operation isn't done. Poll `/Earn/AllocateStatus` with `{nonce, strategy_id}` until `pending: false` to confirm.

**Common failure modes:**
| Error                                              | Cause                                                                       |
| -------------------------------------------------- | --------------------------------------------------------------------------- |
| `EGeneral:Permission denied` or `EAPI:Invalid key` | API key lacks `Earn Funds` scope                                            |
| `EGeneral:Invalid arguments:Invalid strategy ID`   | Wrong/non-existent strategy_id                                              |
| `EEarnings:Below min`                              | Amount below strategy minimum                                               |
| `EEarnings:Busy`                                   | Another (de)allocation already in flight for that strategy — wait and retry |
| `EEarnings:Permission denied:tier...`              | Account verification tier too low for this strategy                         |

**Your USDC strategy_id specifically** (from your cached `kraken_earn_apys.csv`):
- **`ESXQXU5-WDDR5-GWA7VY`** — hybrid, 5.92% APY, 1-day unbond → **this is the one to use** (it's the highest, matches what the Kraken UI offers, and `can_allocate=True`).
- ❌ Don't use `ESL5PBZ-W3ETU-EKPHYT` (the flex/base_rewards one) — it has `can_allocate=False`, so the API will reject any attempt to allocate to it. That's likely a passive Auto Earn-tier strategy you can only enable in account settings, not via API allocation.

**Most likely cause of your failure:** API key missing `Earn Funds` permission, or you targeted the `can_allocate=False` strategy. If you can paste the exact error code/message you got, I can confirm in one round.

Sources:
- [Kraken API — Allocate Earn Funds](https://docs.kraken.com/api/docs/rest-api/allocate-strategy/)
- [Kraken API — Deallocate Earn Funds](https://docs.kraken.com/api/docs/rest-api/deallocate-strategy/)
- [Kraken API — Spot REST Earn guide](https://docs.kraken.com/api/docs/guides/spot-rest-earn/)
- [Kraken Support — Staking via the API](https://support.kraken.com/hc/en-us/articles/4404197751444-Staking-via-the-API)

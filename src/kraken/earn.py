import logging
from typing import Any

from src.kraken.client import KrakenClient
from src.schemas import EarnLockType

logger = logging.getLogger(__name__)


class KrakenEarn:
    def __init__(self, client: KrakenClient) -> None:
        self.client = client

    @staticmethod
    def _find_balance_key(asset: str, balance: dict[str, str]) -> str | None:
        for variant in (asset, f"X{asset}", f"XX{asset}"):
            if variant in balance:
                return variant
        return None

    async def get_strategies(self, asset: str | None = None) -> list[dict[str, Any]]:
        data = {"asset": asset} if asset else {}
        result = await self.client._request("/0/private/Earn/Strategies", data)
        return result.get("items", [])

    async def find_strategy(
        self, asset: str, strategy_type: EarnLockType | None = None
    ) -> dict[str, Any] | None:
        strategies = await self.get_strategies(asset)
        if not strategies:
            logger.warning("No earn strategies found for %s", asset)
            return None
        if strategy_type is None:
            return strategies[0]

        def lock(s: dict[str, Any]) -> str:
            return s.get("lock_type", {}).get("type", "")

        def unbonding(s: dict[str, Any]) -> float:
            return s.get("lock_type", {}).get("unbonding_period", 0)

        # "bonded" = shortest unbonding; "restaked" = longest (ETH's restaking option).
        # For most assets only one bonded strategy exists, so min == max.
        if strategy_type in ("bonded", "restaked"):
            bonded = [s for s in strategies if lock(s) == "bonded"]
            if not bonded:
                logger.warning("No bonded strategies found for %s", asset)
                return None
            pick = max if strategy_type == "restaked" else min
            return pick(bonded, key=unbonding)

        # "flexible" (user-facing) maps to Kraken's "flex" lock type.
        flex = next((s for s in strategies if lock(s) == "flex"), None)
        if flex is None:
            logger.warning("No flexible strategies found for %s", asset)
        return flex

    async def allocate(self, strategy_id: str, amount: float, asset: str) -> dict[str, Any]:
        logger.info("Allocating %s %s to strategy %s", amount, asset, strategy_id)
        return await self.client._request(
            "/0/private/Earn/Allocate",
            data={"strategy_id": strategy_id, "amount": str(amount)},
        )

    async def deallocate(self, strategy_id: str, amount: float) -> dict[str, Any]:
        return await self.client._request(
            "/0/private/Earn/Deallocate",
            data={"strategy_id": strategy_id, "amount": str(amount)},
        )

    async def get_allocations(self) -> dict[str, Any]:
        return await self.client._request("/0/private/Earn/Allocations")

    async def get_allocations_by_asset(self) -> dict[str, float]:
        # Flexible (auto-flex) allocations are skipped because Kraken already reports
        # their balance as spendable in /Balance, so counting them again double-counts.
        strategies = await self.get_strategies()
        flexible_ids = {s["id"] for s in strategies if s.get("lock_type", {}).get("type") == "flex"}

        by_asset: dict[str, float] = {}
        for item in (await self.get_allocations()).get("items", []):
            asset = item.get("native_asset")
            if not asset or item.get("strategy_id") in flexible_ids:
                continue
            total = float(item.get("amount_allocated", {}).get("total", {}).get("native") or 0)
            if total > 0:
                by_asset[asset] = by_asset.get(asset, 0.0) + total
        return by_asset

    async def get_strategy_holdings(self, strategy_id: str) -> dict[str, float]:
        # bonded = total amount allocated; pending_unstake = amount in unbonding window.
        for item in (await self.get_allocations()).get("items", []):
            if item.get("strategy_id") != strategy_id:
                continue
            allocated = item.get("amount_allocated", {})
            return {
                "bonded": float(allocated.get("total", {}).get("native") or 0),
                "pending_unstake": float(allocated.get("unbonding", {}).get("native") or 0),
            }
        return {"bonded": 0.0, "pending_unstake": 0.0}

    async def get_allocation_status(self, strategy_id: str) -> dict[str, Any]:
        return await self.client._request(
            "/0/private/Earn/AllocateStatus",
            data={"strategy_id": strategy_id},
        )

    async def stake_asset(
        self,
        asset: str,
        amount: float | None = None,
        strategy_type: EarnLockType | None = None,
    ) -> dict[str, Any] | None:
        strategy = await self.find_strategy(asset, strategy_type)
        if not strategy:
            logger.warning("Cannot stake %s: no matching strategy found", asset)
            return None

        if amount is None:
            amount = await self.client.get_asset_balance(asset)
            if amount <= 0:
                logger.warning("No %s balance available to stake", asset)
                return None
            logger.info("Staking all available %s: %s", asset, amount)

        await self.allocate(strategy["id"], amount, asset)
        return {"amount": amount}

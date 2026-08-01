import logging
from typing import Any, get_args

from src.kraken.client import KrakenClient
from src.schemas import EarnLockType

logger = logging.getLogger(__name__)

LOCK_TYPES = frozenset(get_args(EarnLockType))


def _lock_type(strategy: dict[str, Any]) -> str:
    return strategy.get("lock_type", {}).get("type", "")


def _describe(strategies: list[dict[str, Any]]) -> str:
    def one(strategy: dict[str, Any]) -> str:
        unbonding = strategy.get("lock_type", {}).get("unbonding_period", 0)
        window = f" {unbonding / 86400:g}d" if unbonding else ""
        return f"{_lock_type(strategy)}{window} ({strategy['id']})"

    return ", ".join(one(s) for s in strategies)


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

    async def find_strategy(self, asset: str, strategy: str) -> dict[str, Any]:
        strategies = await self.get_strategies(asset)
        if not strategies:
            raise ValueError(f"no earn strategies exist for {asset}")

        allocatable = [s for s in strategies if s.get("can_allocate")]
        if not allocatable:
            offered = ", ".join(sorted({_lock_type(s) for s in strategies}))
            raise ValueError(
                f"{asset} has no allocatable strategy (offers only: {offered}) -- Kraken "
                "auto-allocates idle spot to flex, so remove this action"
            )

        if strategy not in LOCK_TYPES:
            match = next((s for s in allocatable if s["id"] == strategy), None)
            if match:
                return match
            if any(s["id"] == strategy for s in strategies):
                raise ValueError(f"strategy {strategy} is closed to new allocations for {asset}")
            raise ValueError(
                f"unknown strategy '{strategy}' for {asset} "
                f"-- allocatable: {_describe(allocatable)}"
            )

        matches = [s for s in allocatable if _lock_type(s) == strategy]
        if not matches:
            raise ValueError(
                f"no allocatable '{strategy}' strategy for {asset} "
                f"-- available: {_describe(allocatable)}"
            )
        if len(matches) > 1:
            raise ValueError(
                f"{asset} has {len(matches)} allocatable '{strategy}' strategies "
                f"-- set one explicitly: {_describe(matches)}"
            )
        return matches[0]

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
        # flex allocations already reported as spendable in /Balance
        strategies = await self.get_strategies()
        flex_ids = {s["id"] for s in strategies if s.get("lock_type", {}).get("type") == "flex"}

        by_asset: dict[str, float] = {}
        for item in (await self.get_allocations()).get("items", []):
            asset = item.get("native_asset")
            if not asset or item.get("strategy_id") in flex_ids:
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
        strategy: str,
        amount: float | None = None,
    ) -> dict[str, Any] | None:
        matched = await self.find_strategy(asset, strategy)

        if amount is None:
            amount = await self.client.get_asset_balance(asset)
            if amount <= 0:
                logger.warning("No %s balance available to stake", asset)
                return None
            logger.info("Staking all available %s: %s", asset, amount)

        await self.allocate(matched["id"], amount, asset)
        return {"amount": amount}

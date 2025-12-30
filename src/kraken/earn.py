import logging
from typing import Any

from src.kraken.client import KrakenClient

logger = logging.getLogger(__name__)


class KrakenEarn:
    def __init__(self, client: KrakenClient) -> None:
        self.client = client

    async def get_strategies(self, asset: str | None = None) -> list[dict[str, Any]]:
        """
        Get available earn strategies.

        Args:
            asset: Exact Kraken asset name (e.g., "ETH", "XBT")

        Returns:
            List of available strategies
        """
        data = {}
        if asset:
            data["asset"] = asset

        result = await self.client._request("POST", "/0/private/Earn/Strategies", data)
        return result.get("items", [])

    async def find_strategy(
        self, asset: str, strategy_type: str | None = None
    ) -> dict[str, Any] | None:
        """
        Find a matching earn strategy for an asset.

        Args:
            asset: Exact Kraken asset name (e.g., "ETH", "XBT")
            strategy_type: Optional type filter (e.g., "bonded", "flexible")

        Returns:
            The matching strategy or None
        """
        strategies = await self.get_strategies(asset)

        if not strategies:
            logger.warning("No earn strategies found for %s", asset)
            return None

        # If a specific type is requested, try to find it
        if strategy_type:
            strategy_type_lower = strategy_type.lower()
            for strategy in strategies:
                lock_type = strategy.get("lock_type", {}).get("type", "").lower()
                if strategy_type_lower in lock_type or lock_type in strategy_type_lower:
                    return strategy

            logger.warning(
                "Strategy type '%s' not found for %s, available: %s",
                strategy_type,
                asset,
                [s.get("lock_type", {}).get("type") for s in strategies],
            )
            return None

        # Return the first available strategy
        return strategies[0] if strategies else None

    async def allocate(self, strategy_id: str, amount: float, asset: str) -> dict[str, Any]:
        """
        Allocate funds to an earn strategy (stake).

        Args:
            strategy_id: The strategy ID to allocate to
            amount: Amount to allocate (in the asset's units)
            asset: The asset name for logging purposes

        Returns:
            Allocation result
        """
        data = {
            "strategy_id": strategy_id,
            "amount": str(amount),
        }

        logger.info("Allocating %s %s to strategy %s", amount, asset, strategy_id)

        result = await self.client._request("POST", "/0/private/Earn/Allocate", data)

        logger.info("Allocation successful: %s", result)
        return result

    async def deallocate(self, strategy_id: str, amount: float) -> dict[str, Any]:
        """
        Deallocate funds from an earn strategy (unstake).

        Args:
            strategy_id: The strategy ID to deallocate from
            amount: Amount to deallocate

        Returns:
            Deallocation result
        """
        data = {
            "strategy_id": strategy_id,
            "amount": str(amount),
        }

        return await self.client._request("POST", "/0/private/Earn/Deallocate", data)

    async def get_allocations(self) -> dict[str, Any]:
        """Get current earn allocations."""
        return await self.client._request("POST", "/0/private/Earn/Allocations")

    async def get_allocation_status(self, strategy_id: str) -> dict[str, Any]:
        """Get the status of a pending allocation."""
        return await self.client._request(
            "POST",
            "/0/private/Earn/AllocateStatus",
            data={"strategy_id": strategy_id},
        )

    async def stake_after_purchase(
        self, asset: str, amount: float | None = None, strategy_type: str | None = None
    ) -> dict[str, Any] | None:
        """
        Stake an asset to earn yield.

        Args:
            asset: Exact Kraken asset name (e.g., "ETH", "XBT")
            amount: Amount to stake (None = stake all available balance)
            strategy_type: Strategy type preference (e.g., "bonded")

        Returns:
            Allocation result or None if no strategy found
        """
        strategy = await self.find_strategy(asset, strategy_type)

        if not strategy:
            logger.warning("Cannot stake %s: no matching strategy found", asset)
            return None

        strategy_id = strategy["id"]
        logger.info(
            "Found strategy for %s: %s (%s)",
            asset,
            strategy_id,
            strategy.get("lock_type", {}).get("type", "unknown"),
        )

        # If no amount specified, get available balance
        if amount is None:
            balance = await self.client.get_balance()
            amount = float(balance.get(asset, 0))
            if amount <= 0:
                logger.warning("No %s balance available to stake", asset)
                return None
            logger.info("Staking all available %s: %s", asset, amount)

        return await self.allocate(strategy_id, amount, asset)

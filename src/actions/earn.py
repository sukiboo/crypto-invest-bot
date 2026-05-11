from src.actions.base import Action, ActionContext
from src.schemas import ActionConfig


class EarnAction(Action):
    async def execute(self, config: ActionConfig, ctx: ActionContext) -> str:
        assert config.asset is not None
        data = await ctx.earn.stake_asset(
            asset=config.asset,
            amount=config.amount,
            strategy_type=config.strategy,
        )
        amount = data.get("amount") if data else None
        return f"{config.strategy} {amount or '??'} {config.asset}"

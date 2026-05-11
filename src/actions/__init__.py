from src.actions.base import Action, ActionContext
from src.actions.check_runway import CheckRunwayAction
from src.actions.earn import EarnAction
from src.actions.maintain_reserve import MaintainReserveAction
from src.actions.order import OrderAction

ACTIONS: dict[str, Action] = {
    "order": OrderAction(),
    "earn": EarnAction(),
    "check_runway": CheckRunwayAction(),
    "maintain_reserve": MaintainReserveAction(),
}

__all__ = ["ACTIONS", "Action", "ActionContext"]

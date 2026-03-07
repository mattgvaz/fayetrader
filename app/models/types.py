from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class DecisionAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class MarketTick:
    symbol: str
    price: float
    ts: datetime


@dataclass
class Order:
    symbol: str
    side: Side
    qty: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None


@dataclass
class Fill:
    symbol: str
    side: Side
    qty: int
    price: float
    ts: datetime


@dataclass
class AgentDecision:
    symbol: str
    action: DecisionAction
    qty: int
    confidence: float
    reason: str

from __future__ import annotations

from app.models.types import AgentDecision, DecisionAction


class TradingAgent:
    def decide(self, symbol: str, mark_price: float) -> AgentDecision:
        # Placeholder policy for POC; replace with model/research pipeline.
        if int(mark_price) % 2 == 0:
            return AgentDecision(
                symbol=symbol,
                action=DecisionAction.HOLD,
                qty=0,
                confidence=0.5,
                reason="No clear edge from placeholder policy.",
            )
        return AgentDecision(
            symbol=symbol,
            action=DecisionAction.BUY,
            qty=1,
            confidence=0.51,
            reason="Placeholder signal selected small long entry.",
        )

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.catalyst import CatalystEvent, CatalystImpact, CatalystImpactDirection, CatalystTheme


class CatalystFeedAdapter:
    def latest_events(self) -> list[CatalystEvent]:
        now = datetime.utcnow()
        return [
            CatalystEvent(
                event_id="evt-ai-model-launch-001",
                ts=now - timedelta(minutes=8),
                source="MockNewsWire",
                headline="Major frontier-model launch drives AI software repricing chatter",
                summary=(
                    "Market participants are debating immediate winners/losers across SaaS and AI infrastructure. "
                    "Near-term volatility risk is elevated."
                ),
                theme=CatalystTheme.AI_DISRUPTION,
                urgency=5,
                confidence=0.82,
                impacts=[
                    CatalystImpact(
                        symbol="MSFT",
                        direction=CatalystImpactDirection.BULLISH,
                        opportunity_score=0.83,
                        rationale="Cloud distribution channel and enterprise AI upsell exposure.",
                        setup_hint="Watch for first pullback above VWAP before chasing momentum.",
                    ),
                    CatalystImpact(
                        symbol="AAPL",
                        direction=CatalystImpactDirection.MIXED,
                        opportunity_score=0.61,
                        rationale="Platform stickiness supports demand, but direct model economics are less clear.",
                        setup_hint="Treat as sympathy move; require stronger confirmation before entry.",
                    ),
                    CatalystImpact(
                        symbol="SPY",
                        direction=CatalystImpactDirection.BULLISH,
                        opportunity_score=0.57,
                        rationale="Large-cap tech weighting can amplify index reaction to AI headlines.",
                        setup_hint="Use index exposure for lower single-name volatility while theme is uncertain.",
                    ),
                ],
            ),
            CatalystEvent(
                event_id="evt-ai-regulatory-brief-002",
                ts=now - timedelta(minutes=26),
                source="MockPolicyFeed",
                headline="Draft policy commentary suggests closer AI model oversight",
                summary="Regulatory uncertainty can rotate flows between high-beta AI names and defensives.",
                theme=CatalystTheme.REGULATORY,
                urgency=3,
                confidence=0.66,
                impacts=[
                    CatalystImpact(
                        symbol="MSFT",
                        direction=CatalystImpactDirection.MIXED,
                        opportunity_score=0.55,
                        rationale="Scale helps compliance, but headline risk can still create intraday drawdowns.",
                        setup_hint="Prioritize risk-defined entries and avoid oversized first reaction trades.",
                    ),
                ],
            ),
        ]

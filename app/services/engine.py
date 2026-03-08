from __future__ import annotations

import re
from collections import OrderedDict
from datetime import date, datetime
from typing import Any

from app.agents.trading_agent import TradingAgent
from app.brokers.paper import PaperBroker
from app.core.config import settings
from app.data.catalyst import CatalystFeedAdapter
from app.data.market import MarketDataAdapter
from app.models.catalyst import CatalystEvent
from app.models.events import EngineEvent, EngineEventType
from app.models.types import DecisionAction, Order, OrderType, Side
from app.services.event_store import EventStore
from app.services.notification_center import NotificationCenter
from app.services.portfolio import Portfolio
from app.services.risk import RiskEngine


class TradingEngine:
    def __init__(self) -> None:
        self.market = MarketDataAdapter()
        self.catalysts = CatalystFeedAdapter()
        self.agent = TradingAgent()
        self.risk = RiskEngine()
        self.broker = PaperBroker()
        self._baseline_marks = self.market.snapshot(settings.symbol_universe)
        self.portfolio = Portfolio(starting_cash=settings.starting_cash, cash=settings.starting_cash)
        self.decision_log: list[dict[str, str | float | int]] = []
        self.performance_log: list[dict[str, str | float | int]] = []
        self.event_log: list[EngineEvent] = []
        self.event_store = EventStore()
        self.notification_center = NotificationCenter()
        self.manual_research_targets: list[str] = []
        self.chat_sessions: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._chat_session_seq = 0
        self._stream_symbol_idx = 0
        self.hot_opportunity_threshold = 1.25
        self._last_hot_alert_by_symbol: dict[str, datetime] = {}
        self._record_performance(datetime.utcnow())
        self.create_chat_session(title="Session 1")

    def run_once(self, symbol: str) -> dict[str, str | float | int]:
        now = datetime.utcnow()
        tick = self.market.latest(symbol)
        decision = self.agent.decide(symbol=symbol, mark_price=tick.price)

        record: dict[str, str | float | int] = {
            "symbol": symbol,
            "action": decision.action.value,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "price": tick.price,
            "ts": now.isoformat(),
        }

        if decision.action == DecisionAction.HOLD:
            record["status"] = "skipped"
            self.decision_log.append(record)
            self._record_performance(now)
            return record

        allowed, gate_reason = self.risk.allow(decision, self.portfolio, tick.price, now)
        if not allowed:
            record["status"] = "blocked"
            record["risk_reason"] = gate_reason
            self.decision_log.append(record)
            self._record_performance(now)
            return record

        order = Order(
            symbol=symbol,
            side=Side.BUY if decision.action == DecisionAction.BUY else Side.SELL,
            qty=decision.qty,
            order_type=OrderType.MARKET,
        )
        fill = self.broker.submit_order(order, tick.price, now)
        self.portfolio.apply_fill(fill)

        record["status"] = "filled"
        record["fill_price"] = fill.price
        record["qty"] = fill.qty
        self.decision_log.append(record)
        self._record_performance(now)
        return record

    def metrics(self) -> dict[str, float | int]:
        marks = self.market.snapshot(settings.symbol_universe)
        equity = self.portfolio.total_equity(marks)
        return {
            "cash": self.portfolio.cash,
            "market_value": self.portfolio.market_value(marks),
            "equity": equity,
            "realized_pnl": self.portfolio.realized_pnl,
            "drawdown_pct": self.portfolio.drawdown_pct(marks),
            "positions": sum(1 for p in self.portfolio.positions.values() if p.qty > 0),
            "decisions": len(self.decision_log),
        }

    def state(self, decision_limit: int = 25) -> dict[str, object]:
        marks = self.market.snapshot(settings.symbol_universe)
        catalyst_events = self.catalyst_events()
        open_positions: list[dict[str, float | int | str]] = []
        for symbol, pos in self.portfolio.positions.items():
            if pos.qty <= 0:
                continue
            mark = marks.get(symbol, pos.avg_cost)
            open_positions.append(
                {
                    "symbol": symbol,
                    "qty": pos.qty,
                    "avg_cost": pos.avg_cost,
                    "mark": mark,
                    "unrealized_pnl": (mark - pos.avg_cost) * pos.qty,
                }
            )
        return {
            "mode": settings.mode,
            "metrics": self.metrics(),
            "controls": self.risk.controls(),
            "hot_opportunity_threshold": self.hot_opportunity_threshold,
            "hot_opportunity": self.hot_opportunity(),
            "notifications": self.notification_center.list_notifications(limit=12, include_acknowledged=False),
            "positions": open_positions,
            "recent_decisions": self.decision_log[-decision_limit:],
            "research_targets": self.research_targets(marks),
            "research_updated_at": datetime.utcnow().isoformat(),
            "manual_research_targets": self.manual_research_targets,
            "catalyst_events": [event.model_dump(mode="json") for event in catalyst_events],
            "catalyst_impacts": self.catalyst_impacts(catalyst_events),
        }

    def controls(self) -> dict[str, float | int]:
        return self.risk.controls()

    def update_controls(
        self,
        *,
        daily_budget: float,
        max_daily_loss_pct: float,
        max_position_pct: float,
        max_orders_per_minute: int,
    ) -> dict[str, float | int]:
        return self.risk.update_controls(
            daily_budget=daily_budget,
            max_daily_loss_pct=max_daily_loss_pct,
            max_position_pct=max_position_pct,
            max_orders_per_minute=max_orders_per_minute,
        )

    def update_hot_opportunity_threshold(self, threshold: float) -> dict[str, float]:
        self.hot_opportunity_threshold = max(0.1, min(10.0, float(threshold)))
        return {"hot_opportunity_threshold": self.hot_opportunity_threshold}

    def notification_channels(self) -> dict[str, Any]:
        return self.notification_center.channels()

    def update_notification_channels(
        self,
        *,
        in_app_enabled: bool,
        webhook_enabled: bool,
        webhook_url: str,
        email_enabled: bool,
        email_to: str,
    ) -> dict[str, Any]:
        return self.notification_center.update_channels(
            in_app_enabled=in_app_enabled,
            webhook_enabled=webhook_enabled,
            webhook_url=webhook_url,
            email_enabled=email_enabled,
            email_to=email_to,
        )

    def notifications(self, limit: int = 50, include_acknowledged: bool = False) -> list[dict[str, Any]]:
        return self.notification_center.list_notifications(limit=limit, include_acknowledged=include_acknowledged)

    def acknowledge_notification(self, notification_id: str) -> dict[str, Any] | None:
        return self.notification_center.acknowledge(notification_id)

    def snooze_notification(self, notification_id: str, minutes: int) -> dict[str, Any] | None:
        return self.notification_center.snooze(notification_id, minutes)

    def notification_dispatches(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.notification_center.recent_dispatches(limit=limit)

    def snapshot_event(self, decision_limit: int = 25) -> EngineEvent:
        return EngineEvent(
            event_type=EngineEventType.STATE_SNAPSHOT,
            ts=datetime.utcnow(),
            data=self.state(decision_limit=decision_limit),
        )

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.event_store.recent(limit=limit)

    def generate_live_events(self, decision_limit: int = 25) -> list[EngineEvent]:
        symbol = settings.symbol_universe[self._stream_symbol_idx % len(settings.symbol_universe)]
        self._stream_symbol_idx += 1
        record = self.run_once(symbol)
        now = datetime.utcnow()
        events: list[EngineEvent] = []
        events.append(self._append_event(EngineEventType.DECISION, dict(record), ts=now))
        if str(record.get("status")) == "blocked":
            events.append(
                self._append_event(
                    EngineEventType.RISK,
                    {
                        "symbol": record.get("symbol"),
                        "reason": record.get("risk_reason", "unknown"),
                        "status": record.get("status"),
                        "action": record.get("action"),
                    },
                    ts=now,
                )
            )
        if str(record.get("status")) == "filled":
            events.append(
                self._append_event(
                    EngineEventType.ORDER,
                    {
                        "symbol": record.get("symbol"),
                        "side": record.get("action"),
                        "qty": record.get("qty"),
                        "price": record.get("price"),
                    },
                    ts=now,
                )
            )
            events.append(
                self._append_event(
                    EngineEventType.FILL,
                    {
                        "symbol": record.get("symbol"),
                        "qty": record.get("qty"),
                        "fill_price": record.get("fill_price", record.get("price")),
                    },
                    ts=now,
                )
            )
        events.append(self._append_event(EngineEventType.METRICS, self.metrics(), ts=now))
        hot = self.hot_opportunity()
        if hot and float(hot["score"]) >= self.hot_opportunity_threshold:
            symbol = str(hot["symbol"])
            last_sent = self._last_hot_alert_by_symbol.get(symbol)
            if last_sent and (now - last_sent).total_seconds() < 90:
                pass
            else:
                notification = self.notification_center.create_hot_opportunity(
                    symbol=symbol,
                    score=float(hot["score"]),
                    threshold=self.hot_opportunity_threshold,
                    thesis=str(hot["thesis"]),
                    ts=now,
                )
                self._last_hot_alert_by_symbol[symbol] = now
                events.append(
                    self._append_event(
                        EngineEventType.ALERT,
                        {
                            "kind": "hot_opportunity",
                            "symbol": hot["symbol"],
                            "score": hot["score"],
                            "threshold": self.hot_opportunity_threshold,
                            "thesis": hot["thesis"],
                            "notification_id": notification.get("notification_id", ""),
                        },
                        ts=now,
                    )
                )
        events.append(self._append_event(EngineEventType.STATE_SNAPSHOT, self.state(decision_limit=decision_limit), ts=now))
        return events

    def research_targets(self, marks: dict[str, float], limit: int = 5) -> list[dict[str, str | float]]:
        targets: list[dict[str, str | float]] = []
        for symbol in settings.symbol_universe:
            mark = marks.get(symbol)
            baseline = self._baseline_marks.get(symbol, mark)
            if mark is None or baseline in (None, 0):
                continue
            move_pct = ((mark - baseline) / baseline) * 100
            magnitude = abs(move_pct)
            regime = "breakout_watch" if magnitude >= 0.8 else "range_scan"
            confidence = min(0.95, 0.45 + magnitude / 3)
            targets.append(
                {
                    "symbol": symbol,
                    "mark": mark,
                    "move_pct": move_pct,
                    "regime_tag": regime,
                    "confidence": confidence,
                    "thesis": "Momentum expansion candidate" if move_pct > 0 else "Mean-reversion candidate",
                    "source": "auto",
                }
            )

        for symbol in self.manual_research_targets:
            mark = marks.get(symbol, self.market.latest(symbol).price)
            baseline = self._baseline_marks.get(symbol, mark)
            move_pct = ((mark - baseline) / baseline) * 100 if baseline else 0.0
            targets.append(
                {
                    "symbol": symbol,
                    "mark": mark,
                    "move_pct": move_pct,
                    "regime_tag": "manual_watch",
                    "confidence": 0.74,
                    "thesis": "User-requested target for active monitoring.",
                    "source": "manual",
                }
            )

        deduped: list[dict[str, str | float]] = []
        seen: set[str] = set()
        for target in sorted(targets, key=lambda item: abs(float(item["move_pct"])), reverse=True):
            symbol = str(target["symbol"])
            if symbol in seen:
                continue
            seen.add(symbol)
            deduped.append(target)
        return deduped[:limit]

    def hot_opportunity(self) -> dict[str, str | float] | None:
        marks = self.market.snapshot(settings.symbol_universe)
        targets = self.research_targets(marks, limit=8)
        if not targets:
            return None
        ranked = sorted(
            targets,
            key=lambda t: abs(float(t.get("move_pct", 0))) * float(t.get("confidence", 0)),
            reverse=True,
        )
        top = ranked[0]
        score = abs(float(top.get("move_pct", 0))) * float(top.get("confidence", 0))
        return {
            "symbol": str(top.get("symbol", "")),
            "score": score,
            "thesis": str(top.get("thesis", "")),
            "confidence": float(top.get("confidence", 0)),
            "move_pct": float(top.get("move_pct", 0)),
        }

    def add_manual_target(self, symbol: str) -> bool:
        ticker = symbol.upper().strip()
        if not ticker:
            return False
        if ticker not in self.manual_research_targets:
            self.manual_research_targets.append(ticker)
            self._baseline_marks.setdefault(ticker, self.market.latest(ticker).price)
            return True
        return False

    def catalyst_events(self, limit: int = 5) -> list[CatalystEvent]:
        events = self.catalysts.latest_events()
        events.sort(key=lambda event: event.ts, reverse=True)
        return events[:limit]

    def catalyst_impacts(self, events: list[CatalystEvent], limit: int = 8) -> list[dict[str, str | float]]:
        impacts: list[dict[str, str | float]] = []
        for event in events:
            for impact in event.impacts:
                impacts.append(
                    {
                        "event_id": event.event_id,
                        "headline": event.headline,
                        "symbol": impact.symbol,
                        "direction": impact.direction.value,
                        "opportunity_score": impact.opportunity_score,
                        "rationale": impact.rationale,
                        "setup_hint": impact.setup_hint,
                        "theme": event.theme.value,
                        "urgency": event.urgency,
                    }
                )
        impacts.sort(key=lambda item: float(item["opportunity_score"]), reverse=True)
        return impacts[:limit]

    def day_summary(self) -> str:
        metrics = self.metrics()
        decisions = self.decision_log
        filled = sum(1 for d in decisions if d.get("status") == "filled")
        blocked = sum(1 for d in decisions if d.get("status") == "blocked")
        skipped = sum(1 for d in decisions if d.get("status") == "skipped")
        top_catalyst = self.catalyst_events(limit=1)
        catalyst_line = top_catalyst[0].headline if top_catalyst else "No major catalyst headlines detected."
        return (
            f"Today so far: equity {metrics['equity']:.2f}, realized PnL {metrics['realized_pnl']:.2f}, "
            f"decisions {len(decisions)} (filled {filled}, blocked {blocked}, skipped {skipped}). "
            f"Top catalyst: {catalyst_line}"
        )

    def _chat_reply(self, message: str) -> tuple[str, list[str]]:
        text = message.strip()
        lower = text.lower()
        actions: list[str] = []

        if not text:
            return (
                "I'm here with you. You can ask me to summarize the day, explain risk blocks, or add a research target.",
                actions,
            )

        if "summarize" in lower and "day" in lower:
            return (self.day_summary(), actions)

        if "anthropic" in lower:
            for ticker in ["MSFT", "AAPL", "SPY"]:
                added = self.add_manual_target(ticker)
                if added:
                    actions.append(f"added_target:{ticker}")
            return (
                "I added MSFT, AAPL, and SPY to our manual research targets for the Anthropic-driven AI volatility scenario. "
                "If you want, I can narrow this to just one or two symbols so we stay focused.",
                actions,
            )

        if "add target" in lower or "add research target" in lower:
            tickers = re.findall(r"\b[A-Za-z]{1,5}\b", text)
            added_symbols: list[str] = []
            for token in tickers:
                ticker = token.upper()
                if ticker in {"ADD", "TARGET", "RESEARCH", "PLEASE", "FOR", "AND", "THE"}:
                    continue
                if self.add_manual_target(ticker):
                    added_symbols.append(ticker)
                    actions.append(f"added_target:{ticker}")
            if added_symbols:
                return (f"Done. I added these manual research targets: {', '.join(added_symbols)}.", actions)
            return ("I couldn't find a new ticker to add. Try: 'add target NVDA'.", actions)

        return (
            "I can help with: 1) 'summarize day', 2) 'add target <TICKER>', or 3) mention a catalyst like 'anthropic' to queue likely impacted symbols.",
            actions,
        )

    def create_chat_session(self, title: str | None = None) -> dict[str, object]:
        self._chat_session_seq += 1
        session_id = f"chat-{self._chat_session_seq:04d}"
        now = datetime.utcnow().isoformat()
        session = {
            "session_id": session_id,
            "title": title or f"Session {self._chat_session_seq}",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self.chat_sessions[session_id] = session
        return session

    def list_chat_sessions(self, query: str = "", limit: int = 50) -> list[dict[str, object]]:
        q = query.strip().lower()
        sessions = list(self.chat_sessions.values())[::-1]
        if q:
            sessions = [s for s in sessions if q in str(s.get("title", "")).lower()]
        return [
            {
                "session_id": s["session_id"],
                "title": s["title"],
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
                "message_count": len(s["messages"]),
            }
            for s in sessions[:limit]
        ]

    def get_chat_session(self, session_id: str) -> dict[str, object] | None:
        session = self.chat_sessions.get(session_id)
        if not session:
            return None
        return {
            "session_id": session["session_id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "messages": list(session["messages"]),
        }

    def chat(self, message: str, session_id: str | None = None) -> tuple[str, list[str], dict[str, object]]:
        session: dict[str, object] | None = None
        if session_id:
            session = self.chat_sessions.get(session_id)
        if session is None:
            if self.chat_sessions:
                session = list(self.chat_sessions.values())[-1]
            else:
                session = self.create_chat_session()

        now = datetime.utcnow().isoformat()
        user_msg = {"role": "user", "content": message, "ts": now}
        cast_messages = session["messages"]
        if isinstance(cast_messages, list):
            cast_messages.append(user_msg)

        reply, actions = self._chat_reply(message)
        assistant_msg = {"role": "assistant", "content": reply, "ts": datetime.utcnow().isoformat()}
        if isinstance(cast_messages, list):
            cast_messages.append(assistant_msg)
        session["updated_at"] = assistant_msg["ts"]
        if len(cast_messages) >= 2 and str(session.get("title", "")).startswith("Session "):
            snippet = message.strip()[:48]
            if snippet:
                session["title"] = snippet

        return reply, actions, self.get_chat_session(str(session["session_id"])) or {}

    def _record_performance(self, now: datetime) -> None:
        metrics = self.metrics()
        decisions = self.decision_log
        filled = sum(1 for d in decisions if d.get("status") == "filled")
        blocked = sum(1 for d in decisions if d.get("status") == "blocked")
        skipped = sum(1 for d in decisions if d.get("status") == "skipped")
        self.performance_log.append(
            {
                "ts": now.isoformat(),
                "equity": float(metrics["equity"]),
                "realized_pnl": float(metrics["realized_pnl"]),
                "decisions": len(decisions),
                "filled": filled,
                "blocked": blocked,
                "skipped": skipped,
            }
        )

    def _append_event(self, event_type: EngineEventType, data: dict[str, Any], ts: datetime | None = None) -> EngineEvent:
        event = EngineEvent(event_type=event_type, ts=ts or datetime.utcnow(), data=data)
        self.event_log.append(event)
        if len(self.event_log) > 500:
            self.event_log = self.event_log[-500:]
        self.event_store.append(event)
        return event

    def performance(self, start_date: date, end_date: date) -> dict[str, object]:
        points: list[dict[str, str | float | int]] = []
        for point in self.performance_log:
            point_ts = datetime.fromisoformat(str(point["ts"]))
            if start_date <= point_ts.date() <= end_date:
                points.append(point)

        if not points:
            return {
                "range_start": start_date.isoformat(),
                "range_end": end_date.isoformat(),
                "points": [],
                "insights": {
                    "return_pct": 0.0,
                    "realized_pnl_change": 0.0,
                    "max_drawdown_pct": 0.0,
                    "decisions": 0,
                    "filled": 0,
                    "blocked": 0,
                    "skipped": 0,
                },
            }

        start_equity = float(points[0]["equity"])
        end_equity = float(points[-1]["equity"])
        start_realized = float(points[0]["realized_pnl"])
        end_realized = float(points[-1]["realized_pnl"])
        peak = start_equity
        max_drawdown_pct = 0.0
        for point in points:
            equity = float(point["equity"])
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, (peak - equity) / peak)

        return {
            "range_start": start_date.isoformat(),
            "range_end": end_date.isoformat(),
            "points": points,
            "insights": {
                "return_pct": ((end_equity - start_equity) / start_equity * 100) if start_equity > 0 else 0.0,
                "realized_pnl_change": end_realized - start_realized,
                "max_drawdown_pct": max_drawdown_pct * 100,
                "decisions": int(points[-1]["decisions"]) - int(points[0]["decisions"]),
                "filled": int(points[-1]["filled"]) - int(points[0]["filled"]),
                "blocked": int(points[-1]["blocked"]) - int(points[0]["blocked"]),
                "skipped": int(points[-1]["skipped"]) - int(points[0]["skipped"]),
            },
        }

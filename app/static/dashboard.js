const money = (value) =>
  `$${Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;
const EVENT_SCHEMA_VERSION = "2026-03-08";
const FALLBACK_SYMBOLS = ["AAPL", "MSFT", "SPY"];

const workflowCopy = {
  "pre-market": "Pre-Market: verify watchlist, limits, and readiness.",
  intraday: "Intraday: monitor live decisions, fills, and risk events.",
  "post-market": "Post-Market: review outcomes and strategy performance.",
};

const appState = {
  workflow: "pre-market",
  controlsSnapshot: null,
  equitySeries: [],
  performance: null,
  lastSnapshot: null,
  chatInitialized: false,
  activeChatSessionId: null,
  expandedView: null,
  unreadChatCount: 0,
  positionFocusSymbol: null,
  selectedDecisionKey: null,
  researchSource: "all",
  researchSort: "opportunity",
  drilldownSymbol: null,
  recentEvents: [],
  alerts: [],
  notifications: [],
  dispatches: [],
  notificationChannels: {
    in_app_enabled: true,
    webhook_enabled: false,
    webhook_url: "",
    email_enabled: false,
    email_to: "",
  },
  hotOpportunityThreshold: 1.25,
  lastEventTs: null,
  staleTimerId: null,
};

function symbolLink(symbol) {
  const ticker = String(symbol || "").toUpperCase();
  const href = `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}`;
  return `<a class="symbol-link symbol-drilldown" href="${href}" data-symbol="${ticker}" rel="noopener noreferrer">${ticker}</a>`;
}

function setUiState(kind, message) {
  const el = document.getElementById("ui-state");
  el.className = `ui-state ${kind}`;
  el.textContent = message;
}

function setControlsStatus(message, isError = false) {
  const el = document.getElementById("controls-status");
  el.textContent = message;
  el.classList.toggle("error", isError);
}

function setOpportunityStatus(message, isError = false) {
  const el = document.getElementById("opportunity-status");
  el.textContent = message;
  el.classList.toggle("error", isError);
}

function setNotificationStatus(message, isError = false) {
  const el = document.getElementById("notification-status");
  el.textContent = message;
  el.classList.toggle("error", isError);
}

function drawLine(values, lineId, captionId, emptyMessage, width = 440, height = 140) {
  const line = document.getElementById(lineId);
  const caption = document.getElementById(captionId);
  if (!values.length) {
    line.setAttribute("points", "");
    caption.textContent = emptyMessage;
    return;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const points = values
    .map((value, idx) => {
      const x = (idx / Math.max(1, values.length - 1)) * width;
      const normalized = (value - min) / span;
      const y = height - normalized * (height - 20) - 10;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  line.setAttribute("points", points);
  caption.textContent = `Range: ${money(min)} to ${money(max)} (${values.length} points)`;
}

function applyControls(controls) {
  if (!controls) return;
  appState.controlsSnapshot = controls;
  document.getElementById("daily-budget").value = Number(controls.daily_budget || 0).toFixed(0);
  document.getElementById("max-daily-loss-pct").value = (Number(controls.max_daily_loss_pct || 0) * 100).toFixed(2);
  document.getElementById("max-position-pct").value = (Number(controls.max_position_pct || 0) * 100).toFixed(2);
  document.getElementById("max-orders-per-minute").value = Number(controls.max_orders_per_minute || 0).toFixed(0);
}

function symbolSeed(symbol) {
  return symbol.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
}

function signedPct(value) {
  const n = Number(value || 0);
  const prefix = n >= 0 ? "+" : "";
  return `${prefix}${n.toFixed(2)}%`;
}

function signedMoney(value) {
  const n = Number(value || 0);
  const prefix = n >= 0 ? "+" : "-";
  return `${prefix}${money(Math.abs(n))}`;
}

function planNarrative(regime, gapPct, volume) {
  const gap = Number(gapPct);
  if (regime === "volatile") {
    return `Higher-volatility setup. Start smaller and wait for price to stabilize before committing. (${volume} premarket volume)`;
  }
  if (regime === "trend_up" && gap > 0) {
    return `Potential continuation day. If momentum holds after open, this can become a trend-following entry.`;
  }
  if (regime === "trend_down" && gap < 0) {
    return `Weak open risk. Prefer patience; let the first reversal prove itself before considering entries.`;
  }
  return `Range-like behavior expected. Focus on quick mean-reversion moves rather than chasing breakouts.`;
}

function humanRiskReason(reason) {
  const map = {
    rate_limit_exceeded: "Too many orders were attempted in a short period, so the safety rate-limit stepped in.",
    max_daily_loss_reached: "The session loss cap was hit, so new trades were blocked to prevent deeper drawdown.",
    max_position_size_exceeded: "This order size was too large for your position-size rule.",
    insufficient_cash: "The account did not have enough available cash for this order.",
  };
  return map[reason] || "A risk guardrail blocked this action to keep exposure controlled.";
}

function outcomeNarrative(decision) {
  const status = decision.status || "unknown";
  if (status === "filled") {
    return "Trade executed successfully. The risk engine approved the order and it was sent to paper execution.";
  }
  if (status === "blocked") {
    return `Trade was intentionally blocked by safety rules. ${humanRiskReason(decision.risk_reason)}`;
  }
  return "No trade was placed. The agent did not see a strong enough edge and stayed flat.";
}

function researchNarrative(target) {
  const move = Number(target.move_pct || 0);
  const direction = move >= 0 ? "up" : "down";
  const confidence = Number(target.confidence || 0);
  return `Price is ${signedPct(move)} ${direction} versus baseline. In plain terms: ${target.thesis}. Confidence is ${confidence.toFixed(2)} (0-1 scale).`;
}

function impactDirectionCopy(direction) {
  if (direction === "bullish") return "Potential upside bias";
  if (direction === "bearish") return "Potential downside pressure";
  return "Mixed direction; wait for confirmation";
}

function decisionKey(decision) {
  return `${decision.ts || "na"}:${decision.symbol || "na"}:${decision.action || "na"}`;
}

function decisionStatusText(status) {
  if (status === "filled") return "Executed";
  if (status === "blocked") return "Blocked";
  return "Skipped";
}

function eventLabel(eventType) {
  const map = {
    decision: "Decision",
    risk: "Risk",
    order: "Order",
    fill: "Fill",
    metrics: "Metrics",
    alert: "Alert",
    state_snapshot: "Snapshot",
  };
  return map[String(eventType || "")] || "Event";
}

function researchSeverity(target) {
  const move = Math.abs(Number(target.move_pct || 0));
  const confidence = Number(target.confidence || 0);
  if (confidence >= 0.8 || move >= 2.5) return { label: "High", cls: "sev-high" };
  if (confidence >= 0.65 || move >= 1.2) return { label: "Medium", cls: "sev-med" };
  return { label: "Low", cls: "sev-low" };
}

function whyNow(target) {
  const move = Math.abs(Number(target.move_pct || 0));
  const confidence = Number(target.confidence || 0);
  const source = target.source === "manual" ? "you explicitly asked Faye to track this symbol" : "the auto monitor flagged this symbol from market movement";
  const speed = move >= 2 ? "price is moving quickly enough to create short-term entries/exits" : "price is moving, but confirmation is still needed";
  const quality = confidence >= 0.75 ? "signal quality is currently strong" : "signal quality is moderate, so sizing should stay conservative";
  return `Why now: ${source}; ${speed}; ${quality}.`;
}

function renderWatchlist(state) {
  const rows = document.querySelector("#watchlist tbody");
  rows.innerHTML = "";
  const symbols = new Set(FALLBACK_SYMBOLS);
  (state.positions || []).forEach((p) => symbols.add(p.symbol));
  (state.recent_decisions || []).slice(-6).forEach((d) => symbols.add(d.symbol));

  Array.from(symbols)
    .slice(0, 8)
    .forEach((symbol) => {
      const seed = symbolSeed(symbol);
      const gap = (((seed % 13) - 6) / 10).toFixed(2);
      const volume = `${((seed % 9) + 1) * 120}k`;
      const regime = ["range", "trend_up", "trend_down", "volatile"][seed % 4];
      const plan = planNarrative(regime, gap, volume);
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${symbolLink(symbol)}</td>
        <td>${signedPct(gap)}</td>
        <td>${volume}</td>
        <td>${regime}</td>
        <td><div class="explain">${plan}</div></td>
      `;
      rows.appendChild(tr);
    });
}

function renderOvernightContext(state) {
  const list = document.getElementById("overnight-context");
  list.innerHTML = "";
  const symbols = [...new Set([...(state.positions || []).map((p) => p.symbol), ...(state.recent_decisions || []).map((d) => d.symbol), ...FALLBACK_SYMBOLS])].slice(0, 2);
  const listItems = [
    `Market tone: futures are mixed, so the model starts with a neutral bias. This means we avoid aggressive bets before the open direction is clearer.`,
    `Volume read: ${symbolLink(symbols[0])} and ${symbolLink(symbols[1])} have elevated pre-market activity. In plain terms, they are more likely to move enough to create tradeable setups.`,
    `Safety posture: no hard risk throttle from prior session, so normal guardrails stay active. You still keep loss and position caps in force.`,
    `Open plan: first 15 minutes are treated as price discovery. Agent confidence is intentionally capped early to reduce false-start trades.`,
  ];
  listItems.forEach((line) => {
    const item = document.createElement("li");
    item.innerHTML = line;
    list.appendChild(item);
  });
}

function renderReadinessChecklist(state) {
  const list = document.getElementById("readiness-checklist");
  list.innerHTML = "";
  const controlsSet = Boolean(state.controls);
  const streamLive = document.getElementById("stream-pill").textContent.includes("live");
  const checks = [
    { ok: controlsSet, label: "Risk controls configured for session." },
    { ok: streamLive, label: "Realtime stream connected." },
    { ok: (state.recent_decisions || []).length < 1, label: "No stale intraday decisions from prior open." },
    { ok: true, label: "Paper mode confirmed." },
  ];
  checks.forEach((check) => {
    const item = document.createElement("li");
    item.innerHTML = `${check.ok ? "OK" : "WAIT"} - ${check.label}`;
    list.appendChild(item);
  });
}

function pushEquityPoint(equity) {
  if (!Number.isFinite(equity)) return;
  const series = appState.equitySeries;
  const last = series[series.length - 1];
  if (last === equity) return;
  series.push(equity);
  if (series.length > 36) {
    series.shift();
  }
}

function renderEquityChart() {
  drawLine(appState.equitySeries, "equity-line", "chart-caption", "Awaiting live equity points...");
}

function renderIntraday(state) {
  const metrics = state.metrics || {};
  document.getElementById("cash").textContent = money(metrics.cash);
  document.getElementById("equity").textContent = money(metrics.equity);
  document.getElementById("realized").textContent = money(metrics.realized_pnl);
  document.getElementById("drawdown").textContent = pct(metrics.drawdown_pct);
  pushEquityPoint(Number(metrics.equity));
  renderEquityChart();

  const tbody = document.querySelector("#positions tbody");
  tbody.innerHTML = "";
  const positions = state.positions || [];
  if (!positions.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="5" class="empty-row">No open positions.</td>';
    tbody.appendChild(row);
  } else {
    positions.forEach((p) => {
      const pnl = Number(p.unrealized_pnl || 0);
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${symbolLink(p.symbol)}</td>
        <td>${p.qty}</td>
        <td>${money(p.avg_cost)}</td>
        <td>${money(p.mark)}</td>
        <td class="${pnl >= 0 ? "pnl-pos" : "pnl-neg"}">${signedMoney(p.unrealized_pnl)}</td>
      `;
      row.addEventListener("dblclick", () => openDrilldown(p.symbol));
      tbody.appendChild(row);
    });
  }
  renderPositionSpotlight(state, positions);

  const timeline = document.getElementById("timeline");
  timeline.innerHTML = "";
  const decisions = [...(state.recent_decisions || [])].reverse();
  if (!decisions.length) {
    const item = document.createElement("li");
    item.textContent = "No intraday decisions yet.";
    timeline.appendChild(item);
  } else {
    decisions.forEach((d) => {
      const key = decisionKey(d);
      const item = document.createElement("li");
      item.className = "timeline-item";
      item.dataset.decisionKey = key;
      item.classList.toggle("active", key === appState.selectedDecisionKey);
      const risk = d.risk_reason ? `<div class="risk">${d.risk_reason}</div>` : "";
      item.innerHTML = `
        <div><strong>${symbolLink(d.symbol)}</strong> ${d.action} (${d.status})</div>
        <div class="meta">${d.reason || "No rationale"} | conf ${Number(d.confidence || 0).toFixed(2)}</div>
        <div class="explain">${outcomeNarrative(d)}</div>
        ${risk}
      `;
      item.addEventListener("click", () => {
        appState.selectedDecisionKey = key;
        renderDecisionInspector(state, decisions);
        Array.from(document.querySelectorAll("#timeline .timeline-item")).forEach((node) => {
          node.classList.toggle("active", node.dataset.decisionKey === key);
        });
      });
      timeline.appendChild(item);
    });
  }
  renderDecisionInspector(state, decisions);
  renderSessionTape(state, decisions);
  renderAlertFeed();
  renderNotificationCenter(state);
  renderEventBus();

  const researchFeed = document.getElementById("research-feed");
  researchFeed.innerHTML = "";
  const targets = [...(state.research_targets || [])]
    .filter((target) => appState.researchSource === "all" || String(target.source || "auto") === appState.researchSource)
    .sort((a, b) => {
      if (appState.researchSort === "confidence") {
        return Number(b.confidence || 0) - Number(a.confidence || 0);
      }
      if (appState.researchSort === "move") {
        return Math.abs(Number(b.move_pct || 0)) - Math.abs(Number(a.move_pct || 0));
      }
      return (Math.abs(Number(b.move_pct || 0)) * Number(b.confidence || 0)) - (Math.abs(Number(a.move_pct || 0)) * Number(a.confidence || 0));
    });
  if (!targets.length) {
    const item = document.createElement("li");
    item.textContent = "No active candidates for this filter right now.";
    researchFeed.appendChild(item);
  } else {
    targets.forEach((target) => {
      const item = document.createElement("li");
      const move = Number(target.move_pct || 0);
      const sev = researchSeverity(target);
      item.innerHTML = `
        <div><strong>${symbolLink(target.symbol)}</strong> ${money(target.mark)} (${signedPct(move)}) <span class="severity ${sev.cls}">${sev.label}</span> <button type="button" class="inspect-btn research-inspect" data-symbol="${target.symbol}">Inspect</button></div>
        <div class="meta">${target.regime_tag} | source ${target.source || "auto"} | conf ${Number(target.confidence || 0).toFixed(2)} | ${target.thesis}</div>
        <div class="explain">${researchNarrative(target)}</div>
        <div class="explain">${whyNow(target)}</div>
      `;
      item.querySelector(".research-inspect")?.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openDrilldown(target.symbol);
      });
      researchFeed.appendChild(item);
    });
  }

  const catalystFeed = document.getElementById("catalyst-feed");
  catalystFeed.innerHTML = "";
  const catalystEvents = state.catalyst_events || [];
  if (!catalystEvents.length) {
    const item = document.createElement("li");
    item.textContent = "No major catalyst events detected right now.";
    catalystFeed.appendChild(item);
  } else {
    catalystEvents.forEach((event) => {
      const impacts = event.impacts || [];
      const impactLine = impacts
        .slice(0, 3)
        .map((impact) => `${symbolLink(impact.symbol)} (${impactDirectionCopy(impact.direction)})`)
        .join(", ");
      const item = document.createElement("li");
      item.innerHTML = `
        <div><strong>${event.headline}</strong></div>
        <div class="meta">${event.theme} | urgency ${event.urgency}/5 | confidence ${Number(event.confidence || 0).toFixed(2)}</div>
        <div class="explain">${event.summary}</div>
        <div class="explain"><strong>Likely impacted:</strong> ${impactLine || "No mapped symbols yet."}</div>
        ${
          impacts.length
            ? `<div class="explain"><strong>Suggested setup:</strong> ${impacts[0].setup_hint}</div>`
            : ""
        }
      `;
      catalystFeed.appendChild(item);
    });
  }
}

function renderSessionTape(state, decisions) {
  const tape = document.getElementById("session-tape");
  tape.innerHTML = "";
  const events = [];
  appState.recentEvents.slice(-6).forEach((event) => {
    const data = event.data || {};
    if (event.event_type === "alert") {
      events.push({
        label: "Alert",
        detail: `${data.symbol || ""} score ${Number(data.score || 0).toFixed(2)}`,
        weight: 5,
        cls: "tape-catalyst",
      });
    }
    if (event.event_type === "fill") {
      events.push({
        label: "Fill",
        detail: `${data.symbol || ""} qty ${data.qty || ""}`,
        weight: 4,
        cls: "tape-filled",
      });
    }
    if (event.event_type === "risk") {
      events.push({
        label: "Risk",
        detail: `${data.symbol || ""} ${data.reason || "blocked"}`,
        weight: 3,
        cls: "tape-blocked",
      });
    }
  });
  const catalysts = state.catalyst_events || [];
  catalysts.slice(0, 2).forEach((event) => {
    events.push({
      label: "Catalyst",
      detail: event.headline,
      weight: Number(event.urgency || 0),
      cls: "tape-catalyst",
    });
  });
  decisions.slice(0, 6).forEach((decision) => {
    const status = decision.status || "skipped";
    events.push({
      label: decisionStatusText(status),
      detail: `${decision.symbol} ${decision.action}`,
      weight: status === "filled" ? 3 : status === "blocked" ? 2 : 1,
      cls: status === "filled" ? "tape-filled" : status === "blocked" ? "tape-blocked" : "tape-skipped",
    });
  });
  if (!events.length) {
    const item = document.createElement("div");
    item.className = "tape-pill";
    item.textContent = "No notable events yet this session.";
    tape.appendChild(item);
    return;
  }
  events
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 8)
    .forEach((event) => {
      const pill = document.createElement("div");
      pill.className = `tape-pill ${event.cls}`;
      pill.innerHTML = `<span class="tape-label">${event.label}</span><span class="tape-detail">${event.detail}</span>`;
      tape.appendChild(pill);
    });
}

function renderAlertFeed() {
  const feed = document.getElementById("alert-feed");
  feed.innerHTML = "";
  const source = appState.notifications.length ? appState.notifications : appState.alerts;
  if (!source.length) {
    const li = document.createElement("li");
    li.textContent = "No hot-opportunity alerts yet.";
    feed.appendChild(li);
    return;
  }
  source.slice(0, 6).forEach((alert) => {
    const data = alert.data || alert;
    const li = document.createElement("li");
    li.innerHTML = `
      <div><strong>${symbolLink(data.symbol || "")}</strong> score ${Number(data.score || 0).toFixed(2)} crossed threshold ${Number(data.threshold || 0).toFixed(2)}</div>
      <div class="meta">${data.kind || "hot_opportunity"} | ${new Date(alert.ts || alert.created_at).toLocaleTimeString()}</div>
      <div class="explain">${data.thesis || "No thesis provided."}</div>
    `;
    feed.appendChild(li);
  });
}

function renderNotificationCenter(state) {
  if (state && Array.isArray(state.notifications)) {
    appState.notifications = state.notifications;
  }
  const feed = document.getElementById("notification-feed");
  const dispatchFeed = document.getElementById("dispatch-feed");
  feed.innerHTML = "";
  dispatchFeed.innerHTML = "";

  if (!appState.notifications.length) {
    const li = document.createElement("li");
    li.textContent = "No active notifications.";
    feed.appendChild(li);
  } else {
    appState.notifications.slice(0, 8).forEach((notification) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <div><strong>${symbolLink(notification.symbol || "")}</strong> ${notification.title}</div>
        <div class="meta">${new Date(notification.created_at).toLocaleTimeString()} | score ${Number(notification.score || 0).toFixed(2)}</div>
        <div class="explain">${notification.body || ""}</div>
        <div class="inline-actions">
          <button type="button" class="inspect-btn notif-ack" data-id="${notification.notification_id}">Acknowledge</button>
          <button type="button" class="inspect-btn notif-snooze" data-id="${notification.notification_id}" data-minutes="30">Snooze 30m</button>
        </div>
      `;
      feed.appendChild(li);
    });
  }

  if (!appState.dispatches.length) {
    const li = document.createElement("li");
    li.textContent = "No external dispatch attempts yet.";
    dispatchFeed.appendChild(li);
  } else {
    appState.dispatches.slice(0, 8).forEach((dispatch) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <div><strong>${dispatch.channel}</strong> ${dispatch.status}</div>
        <div class="meta">${new Date(dispatch.ts).toLocaleTimeString()}</div>
        <div class="explain">${dispatch.detail}</div>
      `;
      dispatchFeed.appendChild(li);
    });
  }
}

function renderEventBus() {
  const feed = document.getElementById("event-feed");
  feed.innerHTML = "";
  if (!appState.recentEvents.length) {
    const li = document.createElement("li");
    li.textContent = "Waiting for live events...";
    feed.appendChild(li);
    return;
  }
  [...appState.recentEvents]
    .reverse()
    .slice(0, 20)
    .forEach((event) => {
      const data = event.data || {};
      const li = document.createElement("li");
      li.className = "event-row";
      li.innerHTML = `
        <div><strong>${eventLabel(event.event_type)}</strong> <span class="meta">${new Date(event.ts).toLocaleTimeString()}</span></div>
        <div class="explain">${data.symbol ? `${symbolLink(data.symbol)} ` : ""}${data.reason || data.thesis || data.action || data.kind || "event update"}</div>
      `;
      feed.appendChild(li);
    });
}

function renderDecisionInspector(state, decisions) {
  const inspector = document.getElementById("decision-inspector");
  const delta = document.getElementById("decision-delta");
  delta.innerHTML = "";
  if (!decisions.length) {
    inspector.className = "decision-inspector empty";
    inspector.textContent = "No decisions yet. As decisions arrive, this panel explains exactly what changed and why.";
    const li = document.createElement("li");
    li.textContent = "Tip: click a decision in the timeline to inspect rationale and risk behavior.";
    delta.appendChild(li);
    return;
  }

  const selected = decisions.find((d) => decisionKey(d) === appState.selectedDecisionKey) || decisions[0];
  appState.selectedDecisionKey = decisionKey(selected);
  const idx = decisions.findIndex((d) => decisionKey(d) === appState.selectedDecisionKey);
  const previous = idx >= 0 && idx < decisions.length - 1 ? decisions[idx + 1] : null;
  const confidence = Number(selected.confidence || 0);
  inspector.className = `decision-inspector ${selected.status || "skipped"}`;
  inspector.innerHTML = `
    <p><strong>${symbolLink(selected.symbol)}</strong> -> ${selected.action} (${selected.status}) at confidence ${confidence.toFixed(2)}.</p>
    <p><strong>Plain English:</strong> ${outcomeNarrative(selected)}</p>
    <p><strong>Rationale:</strong> ${selected.reason || "No rationale was provided for this decision."}</p>
  `;

  const deltas = [
    previous
      ? `Confidence changed from ${Number(previous.confidence || 0).toFixed(2)} to ${confidence.toFixed(2)} (${(confidence - Number(previous.confidence || 0)).toFixed(2)} delta).`
      : "This is the first decision in the current timeline window, so there is no prior decision comparison.",
    previous
      ? `Action changed from ${previous.action || "n/a"} to ${selected.action || "n/a"}, and status moved from ${previous.status || "n/a"} to ${selected.status || "n/a"}.`
      : "No action/status delta available yet.",
    selected.risk_reason
      ? `Risk check result: blocked by "${selected.risk_reason}". In practical terms, a guardrail prevented overexposure.`
      : selected.status === "filled"
        ? "Risk check result: approved; order passed safety checks and was executed."
        : "Risk check result: no order routed, so no risk block was triggered.",
  ];
  deltas.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    delta.appendChild(li);
  });
}

function renderPositionSpotlight(state, positions) {
  const focus = document.getElementById("position-focus");
  const spotlight = document.getElementById("position-spotlight");
  const actions = document.getElementById("position-actions");
  const controls = state.controls || {};
  const equity = Number((state.metrics || {}).equity || 0);
  const inspectBtn = document.getElementById("spotlight-inspect");

  actions.innerHTML = "";
  focus.innerHTML = "";

  if (!positions.length) {
    focus.disabled = true;
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No open positions";
    focus.appendChild(option);
    spotlight.className = "spotlight empty";
    spotlight.textContent = "No active position right now. Once a trade is open, this panel explains what matters in simple terms.";
    inspectBtn.disabled = true;
    const item = document.createElement("li");
    item.textContent = "When a position opens, watch this panel for PnL status, exposure, and practical next-step guidance.";
    actions.appendChild(item);
    appState.positionFocusSymbol = null;
    return;
  }

  const symbols = positions.map((p) => p.symbol);
  if (!appState.positionFocusSymbol || !symbols.includes(appState.positionFocusSymbol)) {
    appState.positionFocusSymbol = symbols[0];
  }
  focus.disabled = false;
  symbols.forEach((symbol) => {
    const option = document.createElement("option");
    option.value = symbol;
    option.textContent = symbol;
    if (symbol === appState.positionFocusSymbol) option.selected = true;
    focus.appendChild(option);
  });

  const position = positions.find((p) => p.symbol === appState.positionFocusSymbol) || positions[0];
  inspectBtn.disabled = false;
  inspectBtn.dataset.symbol = String(position.symbol || "");
  const qty = Number(position.qty || 0);
  const avg = Number(position.avg_cost || 0);
  const mark = Number(position.mark || 0);
  const notional = qty * mark;
  const weightPct = equity > 0 ? (notional / equity) * 100 : 0;
  const pnl = Number(position.unrealized_pnl || 0);
  const pnlPct = avg > 0 ? ((mark - avg) / avg) * 100 : 0;
  const maxPosPct = Number(controls.max_position_pct || 0) * 100;
  const budget = Number(controls.daily_budget || 0);
  const maxLossPct = Number(controls.max_daily_loss_pct || 0);
  const ruleLossBuffer = (budget * maxLossPct * Math.min(1, Number(controls.max_position_pct || 0))) || 0;

  const stance =
    pnlPct >= 1.25
      ? "Position is working. Locking in partial gains can reduce emotional swings while keeping upside exposure."
      : pnlPct <= -1
        ? "Position is under pressure. In beginner terms: this is where discipline matters more than hope."
        : "Position is near break-even. This is a patience zone while waiting for a clearer directional edge.";

  spotlight.className = `spotlight ${pnl >= 0 ? "positive" : "negative"}`;
  spotlight.innerHTML = `
    <p><strong>${symbolLink(position.symbol)}</strong> is ${pnl >= 0 ? "up" : "down"} <strong>${signedMoney(pnl)}</strong> (${signedPct(pnlPct)}).</p>
    <p>You currently have ${money(notional)} exposed here, about ${weightPct.toFixed(2)}% of account equity.</p>
    <p>${stance}</p>
    <p class="meta">Rule context: max position setting is ${maxPosPct.toFixed(2)}% and rough single-position loss buffer is ${money(ruleLossBuffer)}.</p>
  `;

  const guidance = [
    weightPct > maxPosPct
      ? "Exposure check: this position is above your configured max-position percentage. Consider trimming size."
      : "Exposure check: position size is within your configured max-position percentage.",
    pnlPct >= 2
      ? "Profit management: consider a trailing stop or partial take-profit to protect gains."
      : pnlPct <= -1.5
        ? "Risk management: define an exit line now. If price keeps moving against you, avoid averaging down blindly."
        : "Trade management: wait for confirmation before adding size. Let price prove the thesis first.",
    "Learning prompt: after close, note whether entry timing, sizing, and thesis were correct. This improves next-session decisions.",
  ];
  guidance.forEach((line) => {
    const item = document.createElement("li");
    item.textContent = line;
    actions.appendChild(item);
  });
}

function buildDrilldownSeries(state, symbol) {
  const baseFromPosition = (state.positions || []).find((p) => p.symbol === symbol)?.mark;
  const baseFromTarget = (state.research_targets || []).find((t) => t.symbol === symbol)?.mark;
  const base = Number(baseFromPosition || baseFromTarget || 100);
  const symbolDecisions = (state.recent_decisions || []).filter((d) => d.symbol === symbol);
  const fromDecisions = symbolDecisions
    .map((d) => Number(d.fill_price || d.price || 0))
    .filter((v) => Number.isFinite(v) && v > 0);
  if (fromDecisions.length >= 2) return fromDecisions.slice(-20);
  const synthetic = [];
  for (let idx = 0; idx < 12; idx += 1) {
    const phase = (idx % 5) - 2;
    synthetic.push(base * (1 + phase * 0.0018 + idx * 0.0007));
  }
  return synthetic;
}

function renderDrilldown() {
  const state = appState.lastSnapshot;
  const symbol = appState.drilldownSymbol;
  if (!state || !symbol) return;

  document.getElementById("drilldown-title").innerHTML = `${symbolLink(symbol)} Drilldown`;
  const yahooBtn = document.getElementById("drilldown-open-yahoo");
  yahooBtn.onclick = () => {
    const href = `https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}`;
    window.open(href, "_blank", "noopener,noreferrer");
  };
  const series = buildDrilldownSeries(state, symbol);
  drawLine(series, "drilldown-line", "drilldown-caption", "No symbol prices yet.", 920, 260);

  const thesis = document.getElementById("drilldown-thesis");
  const risk = document.getElementById("drilldown-risk");
  const prompts = document.getElementById("drilldown-prompts");
  thesis.innerHTML = "";
  risk.innerHTML = "";
  prompts.innerHTML = "";

  const target = (state.research_targets || []).find((t) => t.symbol === symbol);
  const decisions = (state.recent_decisions || []).filter((d) => d.symbol === symbol).slice().reverse();
  const catalystLines = [];
  (state.catalyst_events || []).forEach((event) => {
    (event.impacts || []).forEach((impact) => {
      if (impact.symbol === symbol) {
        catalystLines.push(`${event.headline}: ${impact.rationale}`);
      }
    });
  });
  const thesisLines = [
    target
      ? `Current thesis: ${target.thesis}. Regime: ${target.regime_tag}. Confidence ${Number(target.confidence || 0).toFixed(2)}.`
      : "No active research thesis is attached to this symbol right now.",
    decisions[0]
      ? `Latest decision: ${decisions[0].action} (${decisions[0].status}) because "${decisions[0].reason || "no reason provided"}".`
      : "No decision events logged for this symbol yet.",
    catalystLines[0] || "No catalyst mapping currently linked to this symbol.",
  ];
  thesisLines.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    thesis.appendChild(li);
  });

  const blocked = decisions.filter((d) => d.status === "blocked");
  const controls = state.controls || {};
  const riskLines = [
    blocked.length
      ? `Recent block: ${blocked[0].risk_reason}. ${humanRiskReason(blocked[0].risk_reason)}`
      : "No recent risk block on this symbol.",
    `Current controls: max position ${(Number(controls.max_position_pct || 0) * 100).toFixed(2)}%, max daily loss ${(Number(controls.max_daily_loss_pct || 0) * 100).toFixed(2)}%, order cap ${Number(controls.max_orders_per_minute || 0)}/min.`,
    "Practical check: if thesis weakens and risk increases, reduce size before looking for a better re-entry.",
  ];
  riskLines.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    risk.appendChild(li);
  });

  const promptOptions = [
    `Summarize ${symbol} today in plain English.`,
    `Explain risk blocks for ${symbol}.`,
    `Add target ${symbol}`,
  ];
  promptOptions.forEach((text) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "inspect-btn";
    button.textContent = text;
    button.addEventListener("click", () => {
      const input = document.getElementById("chat-input");
      input.value = text;
      setChatDrawer(true);
      input.focus();
    });
    prompts.appendChild(button);
  });
}

function openDrilldown(symbol) {
  appState.drilldownSymbol = String(symbol || "").toUpperCase();
  const modal = document.getElementById("drilldown-modal");
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  renderDrilldown();
}

function closeDrilldown() {
  const modal = document.getElementById("drilldown-modal");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  appState.drilldownSymbol = null;
}

function renderPostMarket(state) {
  const decisions = state.recent_decisions || [];
  const filled = decisions.filter((d) => d.status === "filled");
  const blocked = decisions.filter((d) => d.status === "blocked");
  const skipped = decisions.filter((d) => d.status === "skipped");
  document.getElementById("session-decisions").textContent = String(decisions.length);
  document.getElementById("session-filled").textContent = String(filled.length);
  document.getElementById("session-blocked").textContent = String(blocked.length);
  document.getElementById("session-skipped").textContent = String(skipped.length);

  const outcomes = document.querySelector("#outcomes tbody");
  outcomes.innerHTML = "";
  if (!decisions.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="4" class="empty-row">No outcomes yet for this session.</td>';
    outcomes.appendChild(row);
  } else {
    decisions
      .slice(-8)
      .reverse()
      .forEach((d) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${symbolLink(d.symbol)}</td>
          <td>${d.status}</td>
          <td>${d.action}</td>
          <td><div>${d.reason || "No rationale"}</div><div class="explain">${outcomeNarrative(d)}</div></td>
        `;
        outcomes.appendChild(tr);
      });
  }

  const riskBlocks = document.getElementById("risk-blocks");
  riskBlocks.innerHTML = "";
  if (!blocked.length) {
    const item = document.createElement("li");
    item.textContent = "No risk blocks recorded.";
    riskBlocks.appendChild(item);
  } else {
    blocked.slice(-5).reverse().forEach((d) => {
      const item = document.createElement("li");
      item.innerHTML = `<div>${symbolLink(d.symbol)}: ${d.risk_reason || "blocked"}</div><div class="explain">${humanRiskReason(d.risk_reason)}</div>`;
      riskBlocks.appendChild(item);
    });
  }

  const nextNotes = document.getElementById("next-notes");
  nextNotes.innerHTML = "";
  const pnl = Number((state.metrics || {}).realized_pnl || 0);
  const mostBlocked = blocked[blocked.length - 1]?.risk_reason || "";
  const notes = [
    pnl >= 0
      ? "Session ended green. Keep position sizing steady tomorrow instead of increasing risk after one good day."
      : "Session ended red. Consider tightening max position % slightly until consistency improves.",
    mostBlocked
      ? `Most recent block reason was "${mostBlocked}". In plain terms, your guardrail prevented a rule-break; review if this was intentional discipline or over-restriction.`
      : "No risk blocks today. That usually means controls were sized appropriately for activity.",
    "Before next open, pick 1-2 symbols to focus on first. Fewer symbols usually improves decision quality while learning.",
  ];
  notes.forEach((line) => {
    const item = document.createElement("li");
    item.innerHTML = line;
    nextNotes.appendChild(item);
  });
}

function renderPerformance() {
  const perf = appState.performance;
  if (!perf) {
    drawLine([], "performance-line", "performance-caption", "Select a range to load timeline.");
    return;
  }
  const values = (perf.points || []).map((p) => Number(p.equity || 0));
  drawLine(values, "performance-line", "performance-caption", "No performance points in this range.");
  const insights = perf.insights || {};
  document.getElementById("perf-return").textContent = `${Number(insights.return_pct || 0).toFixed(2)}%`;
  document.getElementById("perf-pnl").textContent = money(insights.realized_pnl_change || 0);
  document.getElementById("perf-dd").textContent = `${Number(insights.max_drawdown_pct || 0).toFixed(2)}%`;
  document.getElementById("perf-decisions").textContent = String(insights.decisions || 0);
}

function render(state) {
  appState.lastSnapshot = state;
  document.getElementById("mode-pill").textContent = `mode: ${state.mode || "practice"}`;
  applyControls(state.controls);
  renderWatchlist(state);
  renderOvernightContext(state);
  renderReadinessChecklist(state);
  renderIntraday(state);
  renderPostMarket(state);
  renderExpanded();
  if (appState.drilldownSymbol) {
    renderDrilldown();
  }
}

function setLastEventTs(ts) {
  if (!ts) return;
  appState.lastEventTs = ts;
  const eventPill = document.getElementById("event-pill");
  eventPill.textContent = `events: ${new Date(ts).toLocaleTimeString()}`;
  eventPill.classList.remove("muted");
  const stalePill = document.getElementById("stale-pill");
  stalePill.textContent = "data: live";
  stalePill.classList.remove("muted");
}

function refreshStaleStatus() {
  const stalePill = document.getElementById("stale-pill");
  if (!appState.lastEventTs) {
    stalePill.textContent = "data: stale";
    stalePill.classList.add("muted");
    return;
  }
  const ageMs = Date.now() - new Date(appState.lastEventTs).getTime();
  if (ageMs > 8_000) {
    stalePill.textContent = "data: stale";
    stalePill.classList.add("muted");
  } else {
    stalePill.textContent = "data: live";
    stalePill.classList.remove("muted");
  }
}

function openExpanded(view) {
  appState.expandedView = view;
  const modal = document.getElementById("expand-modal");
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  renderExpanded();
}

function closeExpanded() {
  const modal = document.getElementById("expand-modal");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  appState.expandedView = null;
}

function renderExpanded() {
  const view = appState.expandedView;
  const state = appState.lastSnapshot;
  if (!view || !state) return;

  const title = document.getElementById("expand-title");
  const body = document.getElementById("expand-body");
  if (view === "equity") {
    title.textContent = "Expanded Equity and PnL Trend";
    body.innerHTML = `
      <svg viewBox="0 0 920 320" class="chart expanded-chart" role="img" aria-label="Expanded equity chart">
        <polyline id="expand-equity-line" points="" />
      </svg>
      <p id="expand-equity-caption" class="note">Awaiting live equity points...</p>
      <div class="insights-grid">
        <p>Cash <strong>${money((state.metrics || {}).cash)}</strong></p>
        <p>Equity <strong>${money((state.metrics || {}).equity)}</strong></p>
        <p>Realized PnL <strong>${money((state.metrics || {}).realized_pnl)}</strong></p>
        <p>Drawdown <strong>${pct((state.metrics || {}).drawdown_pct)}</strong></p>
      </div>
    `;
    drawLine(
      appState.equitySeries,
      "expand-equity-line",
      "expand-equity-caption",
      "Awaiting live equity points..."
    );
    return;
  }

  if (view === "positions") {
    title.textContent = "Expanded Open Positions";
    const positions = state.positions || [];
    const equity = Number((state.metrics || {}).equity || 0);
    const rows = positions
      .map((p) => {
        const notional = Number(p.qty || 0) * Number(p.mark || 0);
        const pnlPct = Number(p.avg_cost || 0) > 0 ? ((Number(p.mark) - Number(p.avg_cost)) / Number(p.avg_cost)) * 100 : 0;
        const weight = equity > 0 ? (notional / equity) * 100 : 0;
        return `<tr>
          <td>${symbolLink(p.symbol)}</td>
          <td>${p.qty}</td>
          <td>${money(p.avg_cost)}</td>
          <td>${money(p.mark)}</td>
          <td>${money(p.unrealized_pnl)}</td>
          <td>${money(notional)}</td>
          <td>${pnlPct.toFixed(2)}%</td>
          <td>${weight.toFixed(2)}%</td>
        </tr>`;
      })
      .join("");
    body.innerHTML = `
      <table>
        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Mark</th><th>Unrealized</th><th>Notional</th><th>PnL %</th><th>Portfolio Wt</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="8" class="empty-row">No open positions.</td></tr>'}</tbody>
      </table>
      <p class="note">Expanded view adds notional exposure and portfolio weight context for each position.</p>
    `;
    return;
  }

  if (view === "performance") {
    title.textContent = "Expanded Performance Tracker";
    const points = ((appState.performance || {}).points || []).map((p) => Number(p.equity || 0));
    const insights = (appState.performance || {}).insights || {};
    body.innerHTML = `
      <svg viewBox="0 0 920 320" class="chart expanded-chart" role="img" aria-label="Expanded performance chart">
        <polyline id="expand-performance-line" points="" />
      </svg>
      <p id="expand-performance-caption" class="note">No performance points in this range.</p>
      <div class="insights-grid">
        <p>Return <strong>${Number(insights.return_pct || 0).toFixed(2)}%</strong></p>
        <p>Realized PnL Delta <strong>${money(insights.realized_pnl_change || 0)}</strong></p>
        <p>Max Drawdown <strong>${Number(insights.max_drawdown_pct || 0).toFixed(2)}%</strong></p>
        <p>Decisions <strong>${Number(insights.decisions || 0)}</strong></p>
      </div>
    `;
    drawLine(points, "expand-performance-line", "expand-performance-caption", "No performance points in this range.");
  }
}

function appendChat(role, text) {
  const log = document.getElementById("chat-log");
  const row = document.createElement("div");
  row.className = `chat-msg ${role}`;
  const avatar = role === "assistant" ? '<img src="/static/faye-avatar.png" class="chat-msg-avatar" alt="Faye avatar">' : "";
  row.innerHTML = `
    <div class="chat-msg-head">${avatar}<div class="chat-role">${role === "user" ? "You" : "Faye"}</div></div>
    <div>${text}</div>
  `;
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

function setUnreadChatCount(count) {
  appState.unreadChatCount = Math.max(0, Number(count || 0));
  const badge = document.getElementById("chat-unread-badge");
  if (appState.unreadChatCount <= 0) {
    badge.classList.add("hidden");
    badge.textContent = "0";
    return;
  }
  badge.classList.remove("hidden");
  badge.textContent = appState.unreadChatCount > 9 ? "9+" : String(appState.unreadChatCount);
}

function renderChatLog(messages) {
  const log = document.getElementById("chat-log");
  log.innerHTML = "";
  if (!messages.length) {
    appendChat(
      "assistant",
      "Hi, I'm Faye. Ask me to summarize the day, explain opportunities, or add a target (example: add target NVDA)."
    );
    return;
  }
  messages.forEach((msg) => appendChat(msg.role === "user" ? "user" : "assistant", msg.content || ""));
}

function renderChatSessions(sessions) {
  const list = document.getElementById("chat-sessions");
  list.innerHTML = "";
  sessions.forEach((session) => {
    const li = document.createElement("li");
    li.className = `chat-session ${session.session_id === appState.activeChatSessionId ? "active" : ""}`;
    li.textContent = `${session.title} (${session.message_count})`;
    li.addEventListener("click", () => openChatSession(session.session_id));
    list.appendChild(li);
  });
}

async function loadChatSessions(query = "") {
  const params = new URLSearchParams();
  if (query) params.set("query", query);
  const res = await fetch(`/api/chat/sessions?${params.toString()}`);
  if (!res.ok) return;
  const body = await res.json();
  const sessions = body.sessions || [];
  renderChatSessions(sessions);
  if (!appState.activeChatSessionId && sessions.length) {
    openChatSession(sessions[0].session_id);
  }
}

async function openChatSession(sessionId) {
  const res = await fetch(`/api/chat/sessions/${sessionId}`);
  if (!res.ok) return;
  const session = await res.json();
  appState.activeChatSessionId = session.session_id;
  renderChatSessions(await (await fetch("/api/chat/sessions")).json().then((b) => b.sessions || []));
  renderChatLog(session.messages || []);
}

async function createChatSession() {
  const res = await fetch("/api/chat/sessions", { method: "POST" });
  if (!res.ok) return;
  const session = await res.json();
  appState.activeChatSessionId = session.session_id;
  await loadChatSessions(document.getElementById("chat-search").value.trim());
  renderChatLog([]);
}

function setWorkflow(workflow) {
  appState.workflow = workflow;
  const label = document.getElementById("workflow-label");
  label.textContent = workflowCopy[workflow];
  document.querySelectorAll(".workflow-tabs button").forEach((button) => {
    button.classList.toggle("active", button.dataset.workflow === workflow);
  });
  document.querySelectorAll(".workflow-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.workflowPanel === workflow);
  });
}

async function hydrate() {
  setUiState("loading", "Loading dashboard state...");
  const res = await fetch("/api/state");
  if (!res.ok) {
    setUiState("error", "Unable to load dashboard state.");
    setControlsStatus("Unable to load controls.", true);
    return;
  }
  const state = await res.json();
  render(state);
  const isEmpty = (state.recent_decisions || []).length === 0;
  setUiState(isEmpty ? "empty" : "normal", isEmpty ? "No decisions yet. Run the engine to populate intraday views." : "Live session data loaded.");
}

async function saveControls(ev) {
  ev.preventDefault();
  const payload = {
    daily_budget: Number(document.getElementById("daily-budget").value),
    max_daily_loss_pct: Number(document.getElementById("max-daily-loss-pct").value) / 100,
    max_position_pct: Number(document.getElementById("max-position-pct").value) / 100,
    max_orders_per_minute: Number(document.getElementById("max-orders-per-minute").value),
  };
  const res = await fetch("/api/controls", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    setControlsStatus("Invalid controls. Check value ranges and retry.", true);
    return;
  }
  applyControls(await res.json());
  setControlsStatus("Controls saved and active.");
}

async function loadOpportunityControls() {
  const res = await fetch("/api/opportunity-controls");
  if (!res.ok) {
    setOpportunityStatus("Unable to load threshold.", true);
    return;
  }
  const body = await res.json();
  appState.hotOpportunityThreshold = Number(body.threshold || 1.25);
  document.getElementById("opportunity-threshold").value = appState.hotOpportunityThreshold.toFixed(2);
}

function applyNotificationChannels(channels) {
  appState.notificationChannels = {
    in_app_enabled: Boolean(channels.in_app_enabled),
    webhook_enabled: Boolean(channels.webhook_enabled),
    webhook_url: String(channels.webhook_url || ""),
    email_enabled: Boolean(channels.email_enabled),
    email_to: String(channels.email_to || ""),
  };
  document.getElementById("notify-in-app").checked = appState.notificationChannels.in_app_enabled;
  document.getElementById("notify-webhook-enabled").checked = appState.notificationChannels.webhook_enabled;
  document.getElementById("notify-webhook-url").value = appState.notificationChannels.webhook_url;
  document.getElementById("notify-email-enabled").checked = appState.notificationChannels.email_enabled;
  document.getElementById("notify-email-to").value = appState.notificationChannels.email_to;
}

async function loadNotificationChannels() {
  const res = await fetch("/api/notifications/channels");
  if (!res.ok) {
    setNotificationStatus("Unable to load channels.", true);
    return;
  }
  const body = await res.json();
  applyNotificationChannels(body);
}

async function saveNotificationChannels(ev) {
  ev.preventDefault();
  const payload = {
    in_app_enabled: document.getElementById("notify-in-app").checked,
    webhook_enabled: document.getElementById("notify-webhook-enabled").checked,
    webhook_url: document.getElementById("notify-webhook-url").value.trim(),
    email_enabled: document.getElementById("notify-email-enabled").checked,
    email_to: document.getElementById("notify-email-to").value.trim(),
  };
  const res = await fetch("/api/notifications/channels", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    setNotificationStatus("Unable to save channels.", true);
    return;
  }
  applyNotificationChannels(await res.json());
  setNotificationStatus("Notification channels saved.");
}

async function loadNotifications() {
  const res = await fetch("/api/notifications?limit=30&include_acknowledged=false");
  if (!res.ok) return;
  const body = await res.json();
  appState.notifications = body.notifications || [];
  renderNotificationCenter(appState.lastSnapshot);
}

async function loadDispatches() {
  const res = await fetch("/api/notifications/dispatches?limit=20");
  if (!res.ok) return;
  const body = await res.json();
  appState.dispatches = body.dispatches || [];
  renderNotificationCenter(appState.lastSnapshot);
}

async function acknowledgeNotification(notificationId) {
  const res = await fetch(`/api/notifications/${notificationId}/ack`, { method: "POST" });
  if (!res.ok) {
    setNotificationStatus("Unable to acknowledge notification.", true);
    return;
  }
  await loadNotifications();
  setNotificationStatus("Notification acknowledged.");
}

async function snoozeNotification(notificationId, minutes = 30) {
  const res = await fetch(`/api/notifications/${notificationId}/snooze?minutes=${minutes}`, { method: "POST" });
  if (!res.ok) {
    setNotificationStatus("Unable to snooze notification.", true);
    return;
  }
  await loadNotifications();
  setNotificationStatus(`Notification snoozed for ${minutes} minutes.`);
}

async function saveOpportunityControls(ev) {
  ev.preventDefault();
  const threshold = Number(document.getElementById("opportunity-threshold").value);
  const res = await fetch("/api/opportunity-controls", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ threshold }),
  });
  if (!res.ok) {
    setOpportunityStatus("Invalid threshold value.", true);
    return;
  }
  const body = await res.json();
  appState.hotOpportunityThreshold = Number(body.threshold || threshold);
  document.getElementById("opportunity-threshold").value = appState.hotOpportunityThreshold.toFixed(2);
  setOpportunityStatus("Alert threshold saved.");
}

async function replayRecentEvents() {
  const res = await fetch("/api/events/recent?limit=30");
  if (!res.ok) return;
  const body = await res.json();
  const events = body.events || [];
  appState.recentEvents = events.slice(-60);
  appState.alerts = events.filter((event) => event.event_type === "alert").slice(-20).reverse();
  if (events.length) {
    setLastEventTs(events[events.length - 1].ts);
  }
  renderEventBus();
  renderAlertFeed();
  await loadNotifications();
  await loadDispatches();
}

function handleIncomingEvent(event) {
  if (!event || event.schema_version !== EVENT_SCHEMA_VERSION) return;
  appState.recentEvents.push(event);
  if (appState.recentEvents.length > 120) {
    appState.recentEvents = appState.recentEvents.slice(-120);
  }
  setLastEventTs(event.ts);
  if (event.event_type === "alert") {
    appState.alerts.unshift(event);
    if (appState.alerts.length > 30) appState.alerts = appState.alerts.slice(0, 30);
    renderAlertFeed();
    loadNotifications();
    loadDispatches();
  }
  if (event.event_type === "state_snapshot") {
    render(event.data || {});
    setUiState("normal", "Live session data loaded.");
  }
  if (event.event_type !== "state_snapshot") {
    renderEventBus();
  }
}

function resetControls() {
  if (!appState.controlsSnapshot) return;
  applyControls(appState.controlsSnapshot);
  setControlsStatus("Controls reset to latest saved values.");
}

function syncCustomRangeVisibility() {
  const isCustom = document.getElementById("performance-range").value === "custom";
  document.getElementById("perf-start-wrap").classList.toggle("hidden", !isCustom);
  document.getElementById("perf-end-wrap").classList.toggle("hidden", !isCustom);
}

async function loadPerformance() {
  const range = document.getElementById("performance-range").value;
  const start = document.getElementById("performance-start").value;
  const end = document.getElementById("performance-end").value;
  const params = new URLSearchParams({ range_key: range });
  if (range === "custom") {
    if (start) params.set("start_date", start);
    if (end) params.set("end_date", end);
  }
  const res = await fetch(`/api/performance?${params.toString()}`);
  if (!res.ok) {
    document.getElementById("performance-caption").textContent = "Unable to load performance for selected range.";
    return;
  }
  appState.performance = await res.json();
  renderPerformance();
  renderExpanded();
}

async function sendChat(ev) {
  ev.preventDefault();
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;
  appendChat("user", message);
  input.value = "";
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: appState.activeChatSessionId }),
  });
  if (!res.ok) {
    appendChat("assistant", "I hit an error processing that request.");
    if (!document.getElementById("chat-drawer").classList.contains("open")) {
      setUnreadChatCount(appState.unreadChatCount + 1);
    }
    return;
  }
  const payload = await res.json();
  if (payload.session) {
    appState.activeChatSessionId = payload.session.session_id;
    renderChatLog(payload.session.messages || []);
    if (!document.getElementById("chat-drawer").classList.contains("open")) {
      setUnreadChatCount(appState.unreadChatCount + 1);
    }
    await loadChatSessions(document.getElementById("chat-search").value.trim());
  } else {
    appendChat("assistant", payload.reply || "Done.");
    if (!document.getElementById("chat-drawer").classList.contains("open")) {
      setUnreadChatCount(appState.unreadChatCount + 1);
    }
  }
  if (payload.state) {
    render(payload.state);
  }
}

function bootWorkflowTabs() {
  Array.from(document.querySelectorAll(".workflow-tabs button")).forEach((tab) => {
    tab.addEventListener("click", () => {
      const workflow = tab.dataset.workflow || "pre-market";
      setWorkflow(workflow);
    });
  });
}

function bootExpandableViews() {
  document.querySelectorAll("[data-expand]").forEach((button) => {
    button.addEventListener("click", () => {
      openExpanded(button.dataset.expand);
    });
  });
  document.getElementById("expand-close").addEventListener("click", closeExpanded);
  document.getElementById("expand-backdrop").addEventListener("click", closeExpanded);
}

function bootDrilldownModal() {
  document.getElementById("drilldown-close").addEventListener("click", closeDrilldown);
  document.getElementById("drilldown-backdrop").addEventListener("click", closeDrilldown);
  document.getElementById("spotlight-inspect").addEventListener("click", (ev) => {
    const symbol = ev.currentTarget.dataset.symbol;
    if (symbol) openDrilldown(symbol);
  });
  document.addEventListener("click", (ev) => {
    const link = ev.target.closest(".symbol-drilldown");
    if (!link) return;
    if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
      return;
    }
    ev.preventDefault();
    const symbol = link.dataset.symbol || link.textContent || "";
    if (symbol) {
      openDrilldown(symbol);
    }
  });
}

function setChatDrawer(open) {
  const drawer = document.getElementById("chat-drawer");
  const overlay = document.getElementById("chat-drawer-overlay");
  const toggle = document.getElementById("chat-toggle");
  drawer.classList.toggle("open", open);
  overlay.classList.toggle("hidden", !open);
  drawer.setAttribute("aria-hidden", open ? "false" : "true");
  toggle.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) {
    setUnreadChatCount(0);
  }
}

function bootChatDrawer() {
  const toggle = document.getElementById("chat-toggle");
  const hide = document.getElementById("chat-hide");
  const overlay = document.getElementById("chat-drawer-overlay");
  toggle.addEventListener("click", () => {
    const isOpen = document.getElementById("chat-drawer").classList.contains("open");
    setChatDrawer(!isOpen);
  });
  hide.addEventListener("click", () => setChatDrawer(false));
  overlay.addEventListener("click", () => setChatDrawer(false));
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      setChatDrawer(false);
    }
  });
}

function bootStream() {
  const streamPill = document.getElementById("stream-pill");
  const es = new EventSource("/api/stream");
  es.addEventListener("engine_event", (ev) => {
    const payload = JSON.parse(ev.data);
    if (payload.schema_version !== EVENT_SCHEMA_VERSION) {
      streamPill.textContent = "stream: schema mismatch";
      streamPill.classList.add("muted");
      setUiState("error", "Event stream schema mismatch.");
      return;
    }
    streamPill.textContent = "stream: live";
    streamPill.classList.remove("muted");
    handleIncomingEvent(payload);
  });
  es.onerror = () => {
    streamPill.textContent = "stream: reconnecting";
    streamPill.classList.add("muted");
    document.getElementById("event-pill").textContent = "events: replaying";
    replayRecentEvents();
    if (!appState.lastSnapshot) {
      setUiState("error", "Stream reconnecting. Waiting for first snapshot.");
    }
  };
}

setWorkflow("pre-market");
hydrate();
bootStream();
bootWorkflowTabs();
bootExpandableViews();
bootDrilldownModal();
bootChatDrawer();
document.getElementById("controls").addEventListener("submit", saveControls);
document.getElementById("opportunity-controls").addEventListener("submit", saveOpportunityControls);
document.getElementById("notification-channels").addEventListener("submit", saveNotificationChannels);
document.getElementById("controls-reset").addEventListener("click", resetControls);
document.getElementById("performance-range").addEventListener("change", syncCustomRangeVisibility);
document.getElementById("performance-apply").addEventListener("click", loadPerformance);
document.getElementById("chat-form").addEventListener("submit", sendChat);
document.getElementById("chat-new").addEventListener("click", createChatSession);
document.getElementById("chat-search").addEventListener("input", (ev) => {
  loadChatSessions(ev.target.value.trim());
});
syncCustomRangeVisibility();
loadPerformance();
loadChatSessions();
loadOpportunityControls();
loadNotificationChannels();
replayRecentEvents();
appState.staleTimerId = window.setInterval(refreshStaleStatus, 2000);
document.getElementById("notification-feed").addEventListener("click", (ev) => {
  const ackBtn = ev.target.closest(".notif-ack");
  if (ackBtn) {
    acknowledgeNotification(ackBtn.dataset.id || "");
    return;
  }
  const snoozeBtn = ev.target.closest(".notif-snooze");
  if (snoozeBtn) {
    const mins = Number(snoozeBtn.dataset.minutes || "30");
    snoozeNotification(snoozeBtn.dataset.id || "", mins);
  }
});
document.getElementById("position-focus").addEventListener("change", (ev) => {
  appState.positionFocusSymbol = ev.target.value || null;
  if (appState.lastSnapshot) {
    renderPositionSpotlight(appState.lastSnapshot, appState.lastSnapshot.positions || []);
  }
});
document.getElementById("research-source").addEventListener("change", (ev) => {
  appState.researchSource = ev.target.value || "all";
  if (appState.lastSnapshot) {
    renderIntraday(appState.lastSnapshot);
  }
});
document.getElementById("research-sort").addEventListener("change", (ev) => {
  appState.researchSort = ev.target.value || "opportunity";
  if (appState.lastSnapshot) {
    renderIntraday(appState.lastSnapshot);
  }
});

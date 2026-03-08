const money = (value) => `$${Number(value || 0).toFixed(2)}`;
const pct = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;
const when = (value) => {
  if (!value) return "--";
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? "--" : dt.toLocaleTimeString();
};

function render(state) {
  const metrics = state.metrics || {};
  const controls = state.controls || {};
  document.getElementById("mode-pill").textContent = `mode: ${state.mode || "practice"}`;
  document.getElementById("cash").textContent = money(metrics.cash);
  document.getElementById("equity").textContent = money(metrics.equity);
  document.getElementById("realized").textContent = money(metrics.realized_pnl);
  document.getElementById("drawdown").textContent = pct(metrics.drawdown_pct);
  if (controls.daily_budget) document.getElementById("daily-budget").value = Number(controls.daily_budget).toFixed(2);
  if (controls.max_daily_loss_pct) document.getElementById("max-daily-loss").value = (Number(controls.max_daily_loss_pct) * 100).toFixed(2);
  if (controls.max_position_pct) document.getElementById("max-position").value = (Number(controls.max_position_pct) * 100).toFixed(2);
  if (controls.max_orders_per_minute) document.getElementById("max-orders").value = controls.max_orders_per_minute;

  const tbody = document.querySelector("#positions tbody");
  tbody.innerHTML = "";
  (state.positions || []).forEach((p) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${p.symbol}</td>
      <td>${p.qty}</td>
      <td>${money(p.avg_cost)}</td>
      <td>${money(p.mark)}</td>
      <td>${money(p.unrealized_pnl)}</td>
    `;
    tbody.appendChild(row);
  });

  const timeline = document.getElementById("timeline");
  timeline.innerHTML = "";
  [...(state.recent_decisions || [])].reverse().forEach((d) => {
    const item = document.createElement("li");
    const risk = d.risk_reason ? `<div class="risk">risk: ${d.risk_reason}</div>` : "";
    const fill = d.fill_price ? `fill ${money(d.fill_price)} x ${d.qty || 0}` : `mark ${money(d.price)}`;
    item.innerHTML = `
      <div class="headline">
        <strong>${d.symbol}</strong>
        <span>${d.action}</span>
        <span class="status status-${d.status}">${d.status}</span>
      </div>
      <div class="meta">${when(d.ts)} | ${fill} | conf ${Number(d.confidence || 0).toFixed(2)}</div>
      <div class="meta">${d.reason || "No rationale"}</div>
      ${risk}
    `;
    timeline.appendChild(item);
  });
}

async function hydrate() {
  const res = await fetch("/api/state");
  if (!res.ok) {
    return;
  }
  render(await res.json());
}

async function saveControls(ev) {
  ev.preventDefault();
  const status = document.getElementById("controls-status");
  status.textContent = "Saving...";
  const payload = {
    daily_budget: Number(document.getElementById("daily-budget").value),
    max_daily_loss_pct: Number(document.getElementById("max-daily-loss").value) / 100,
    max_position_pct: Number(document.getElementById("max-position").value) / 100,
    max_orders_per_minute: Number(document.getElementById("max-orders").value),
  };
  const res = await fetch("/api/controls", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    status.textContent = "Save failed. Check control values.";
    return;
  }
  status.textContent = "Controls saved.";
  const next = await fetch("/api/state");
  if (next.ok) render(await next.json());
}

async function runOnce(ev) {
  ev.preventDefault();
  const symbol = document.getElementById("run-symbol").value;
  const status = document.getElementById("run-status");
  status.textContent = `Running ${symbol}...`;
  const res = await fetch(`/api/run/${symbol}`, { method: "POST" });
  if (!res.ok) {
    status.textContent = `Run failed for ${symbol}.`;
    return;
  }
  const body = await res.json();
  status.textContent = `${symbol}: ${body.action} (${body.status})`;
  const next = await fetch("/api/state");
  if (next.ok) render(await next.json());
}

function bootStream() {
  const streamPill = document.getElementById("stream-pill");
  const es = new EventSource("/api/stream");
  es.addEventListener("state", (ev) => {
    streamPill.textContent = "stream: live";
    streamPill.classList.remove("muted");
    const payload = JSON.parse(ev.data);
    render(payload.data || {});
  });
  es.onerror = () => {
    streamPill.textContent = "stream: reconnecting";
    streamPill.classList.add("muted");
  };
}

hydrate();
bootStream();
document.getElementById("controls").addEventListener("submit", saveControls);
document.getElementById("agent-actions").addEventListener("submit", runOnce);

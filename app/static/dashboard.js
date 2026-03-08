const money = (value) => `$${Number(value || 0).toFixed(2)}`;
const pct = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;

function render(state) {
  const metrics = state.metrics || {};
  document.getElementById("mode-pill").textContent = `mode: ${state.mode || "practice"}`;
  document.getElementById("cash").textContent = money(metrics.cash);
  document.getElementById("equity").textContent = money(metrics.equity);
  document.getElementById("realized").textContent = money(metrics.realized_pnl);
  document.getElementById("drawdown").textContent = pct(metrics.drawdown_pct);

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
    const risk = d.risk_reason ? `<div class="risk">${d.risk_reason}</div>` : "";
    item.innerHTML = `
      <div><strong>${d.symbol}</strong> ${d.action} (${d.status})</div>
      <div class="meta">${d.reason || "No rationale"} | conf ${Number(d.confidence || 0).toFixed(2)}</div>
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

function bootStream() {
  const streamPill = document.getElementById("stream-pill");
  const es = new EventSource("/api/stream");
  es.addEventListener("state", (ev) => {
    streamPill.textContent = "stream: live";
    streamPill.classList.remove("muted");
    render(JSON.parse(ev.data));
  });
  es.onerror = () => {
    streamPill.textContent = "stream: reconnecting";
    streamPill.classList.add("muted");
  };
}

hydrate();
bootStream();

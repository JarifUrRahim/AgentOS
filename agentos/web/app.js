const $ = (id) => document.getElementById(id);
const RISK = ["read", "low", "medium", "critical"];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error((await response.json()).detail || response.statusText);
  return response.json();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function addMessage(role, text, outcomes = []) {
  const wrapper = el("div", `msg ${role}`);
  wrapper.appendChild(el("div", "meta", role === "human" ? "You" : "AgentOS"));
  wrapper.appendChild(el("div", "body", text));
  if (outcomes.length) {
    const list = el("ul");
    outcomes.forEach((o) => {
      const item = el("li");
      item.textContent = `${o.action} — ${o.decision} (${RISK[o.risk]} risk)`;
      if (o.rollback_id) item.textContent += ` · rollback ${o.rollback_id}`;
      list.appendChild(item);
    });
    wrapper.appendChild(list);
  }
  $("messages").appendChild(wrapper);
  $("messages").scrollTop = $("messages").scrollHeight;
}

async function refresh() {
  const [status, approvals, snapshots, audit] = await Promise.all([
    api("/api/status"),
    api("/api/approvals"),
    api("/api/snapshots"),
    api("/api/audit?limit=15"),
  ]);

  $("status").textContent =
    `${status.permission_level_name.toLowerCase().replace(/_/g, " ")} · ` +
    `${status.agents.length} agents · ${status.pending_approvals} pending · ` +
    `${status.snapshots} snapshots`;
  $("level").value = String(status.permission_level);

  const approvalsBox = $("approvals");
  approvalsBox.replaceChildren();
  if (!approvals.approvals.length) approvalsBox.appendChild(el("div", "empty", "Nothing waiting."));
  approvals.approvals.forEach((a) => {
    const item = el("div", "item");
    item.appendChild(el("div", null, a.action));
    item.appendChild(el("span", `badge risk-${a.risk}`, RISK[a.risk]));
    item.appendChild(el("div", "muted", a.reason));
    const row = el("div", "row");
    const approve = el("button", null, "Approve");
    approve.onclick = async () => {
      const outcome = await api(`/api/approvals/${a.id}/approve`, { method: "POST" });
      addMessage("agent", outcome.summary, [outcome]);
      refresh();
    };
    const reject = el("button", "secondary", "Reject");
    reject.onclick = async () => {
      await api(`/api/approvals/${a.id}/reject`, { method: "POST" });
      addMessage("agent", `Rejected ${a.action}.`);
      refresh();
    };
    row.append(approve, reject);
    item.appendChild(row);
    approvalsBox.appendChild(item);
  });

  const snapshotsBox = $("snapshots");
  snapshotsBox.replaceChildren();
  if (!snapshots.snapshots.length) snapshotsBox.appendChild(el("div", "empty", "No snapshots yet."));
  snapshots.snapshots.forEach((s) => {
    const item = el("div", "item");
    item.appendChild(el("div", null, s.label || s.id));
    item.appendChild(el("div", "muted", `${s.created_at} · ${s.files.length} files`));
    const button = el("button", "secondary", "Rollback");
    button.onclick = async () => {
      await api(`/api/snapshots/${s.id}/rollback`, { method: "POST" });
      addMessage("agent", `Rolled back to ${s.id}.`);
      refresh();
    };
    item.appendChild(button);
    snapshotsBox.appendChild(item);
  });

  const auditBox = $("audit");
  auditBox.replaceChildren();
  audit.entries.forEach((entry) => {
    const item = el("div", "item");
    item.appendChild(el("div", null, `${entry.action} · ${entry.decision}`));
    item.appendChild(el("div", "muted", `${entry.created_at} — ${entry.result}`));
    auditBox.appendChild(item);
  });
}

$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const instruction = $("instruction").value.trim();
  if (!instruction) return;
  $("instruction").value = "";
  addMessage("human", instruction);
  try {
    const report = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ instruction }),
    });
    addMessage("agent", report.message, report.outcomes);
  } catch (error) {
    addMessage("agent", `Failed: ${error.message}`);
  }
  refresh();
});

$("level").addEventListener("change", async (event) => {
  await api("/api/permission-level", {
    method: "POST",
    body: JSON.stringify({ level: Number(event.target.value) }),
  });
  refresh();
});

$("emergency").addEventListener("click", async () => {
  const result = await api("/api/emergency-stop", { method: "POST" });
  addMessage("agent", `Emergency stop: dropped to read-only. ${result.rollback ? `Restored ${result.rollback.restored}.` : ""}`);
  refresh();
});

refresh();

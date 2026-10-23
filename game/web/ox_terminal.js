/* Live, read-only, developer-scoped telemetry over the existing Canvas wire view.
 *
 * Intentionally does not replace the v0.4 renderer, mutate D, write to Evennia,
 * or manufacture machinery status for equipment not yet migrated.
 */
(function () {
  "use strict";

  if (typeof D === "undefined" || typeof drawSelected !== "function") {
    return;
  }

  document.body.classList.add("ox-live-console");
  const titleBadge = document.querySelector("#panel .badge");
  if (titleBadge) titleBadge.textContent = "TERMINAL / 0.1";

  const knownSpaces = new Map(D.spaces.map(function (space) {
    return [space.id, space];
  }));
  const liveStates = new Map();
  let currentSnapshot = null;
  let working = false;
  let lastReceived = "";
  const intervalMs = 8000;

  const card = document.createElement("aside");
  card.className = "ox-live-card";
  card.setAttribute("aria-label", "World-authoritative Ox telemetry");
  card.innerHTML = [
    '<header>',
      '<div class="ox-live-eyebrow">OX / INDUSTRIAL SYSTEMS MONITOR // OX</div>',
      '<div class="ox-live-row">',
        '<div class="ox-live-heading">VESSEL CONDITION</div>',
        '<button id="ox-refresh" type="button" class="ox-live-link">REFRESH</button>',
      '</div>',
      '<div class="ox-live-row">',
        '<span id="ox-connection" class="ox-live-status" data-mode="installing">CONNECTING</span>',
        '<span id="ox-checked" class="ox-live-fine">NO SAMPLE</span>',
      '</div>',
    '</header>',
    '<div class="ox-live-metrics">',
      '<div class="ox-live-metric"><strong id="ox-count">—</strong><span>COMPARTMENTS<br>IN DATABASE</span></div>',
      '<div class="ox-live-metric"><strong id="ox-exceptions">—</strong><span>NON-NOMINAL<br>CONDITIONS</span></div>',
      '<div class="ox-live-metric"><strong>—</strong><span>LIVE EQUIPMENT<br>NOT CONNECTED</span></div>',
    '</div>',
    '<section class="ox-live-section">',
      '<h2 class="ox-live-label">01 / WORLD STATE</h2>',
      '<div id="ox-coverage" class="ox-live-small">Awaiting a read-only snapshot from Evennia.</div>',
      '<div class="ox-live-fine">Condition is the persisted room state, not a direct atmospheric sensor measurement.</div>',
    '</section>',
    '<section class="ox-live-section">',
      '<h2 class="ox-live-label">02 / EXCEPTIONS</h2>',
      '<div id="ox-anomalies" class="ox-live-alerts"><div class="ox-live-small">Awaiting data.</div></div>',
    '</section>',
    '<section class="ox-live-section">',
      '<h2 class="ox-live-label">03 / INSPECTION</h2>',
      '<div id="ox-current-selection" class="ox-live-selected">NO COMPARTMENT SELECTED</div>',
    '</section>',
    '<div class="ox-live-footer">WORLD DB: AUTHORITATIVE / JSON: GEOMETRY ONLY<br>PROVISIONAL SPATIAL FEED — NO CREW-PRIVATE DATA</div>'
  ].join("");
  document.getElementById("app").appendChild(card);

  const connection = document.getElementById("ox-connection");
  const checked = document.getElementById("ox-checked");
  const count = document.getElementById("ox-count");
  const exceptions = document.getElementById("ox-exceptions");
  const coverage = document.getElementById("ox-coverage");
  const anomalies = document.getElementById("ox-anomalies");
  const selectionBox = document.getElementById("ox-current-selection");

  function severity(condition) {
    const value = String(condition || "unknown").trim().toLowerCase();
    if (["serviceable", "normal", "nominal", "operational"].includes(value)) {
      return "nominal";
    }
    if (["unknown", "unavailable", "not_reported"].includes(value)) {
      return "unknown";
    }
    if (/fire|smoke|breach|critical|fail|damage|fault|leak|loss/.test(value)) {
      return "critical";
    }
    return "caution";
  }

  function labelMode(mode, text) {
    connection.dataset.mode = mode;
    connection.textContent = text;
  }

  function focusSpace(id) {
    const space = knownSpaces.get(id);
    const point = posSpace[id];
    if (!space || !point) return;
    selected = { type: "space", obj: space };
    camera.focus = point.slice();
    camera.zoom = Math.max(2.6, camera.zoom);
    layers.spaces = true;
    const spacesToggle = document.querySelector('[data-layer="spaces"]');
    if (spacesToggle) spacesToggle.checked = true;
    describe(selected);
    invalidate();
  }

  function renderExceptions() {
    anomalies.replaceChildren();
    const abnormal = Array.from(liveStates.entries())
      .map(function (entry) {
        return { id: entry[0], condition: entry[1], grade: severity(entry[1]) };
      })
      .filter(function (item) { return item.grade !== "nominal"; })
      .sort(function (a, b) {
        const weight = { critical: 0, caution: 1, unknown: 2 };
        return weight[a.grade] - weight[b.grade] || a.id.localeCompare(b.id);
      });

    exceptions.textContent = String(abnormal.length);
    exceptions.classList.toggle("alert", abnormal.length > 0);
    if (abnormal.length === 0) {
      const empty = document.createElement("div");
      empty.className = "ox-live-small";
      empty.textContent = "No exceptional spatial conditions reported. Equipment, utility and life-support state are not yet available.";
      anomalies.appendChild(empty);
      return;
    }
    for (const state of abnormal.slice(0, 6)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ox-live-alert" + (state.grade === "critical" ? " critical" : "");
      button.textContent = state.id + " / " + state.condition.toUpperCase();
      button.addEventListener("click", function () { focusSpace(state.id); });
      anomalies.appendChild(button);
    }
    if (abnormal.length > 6) {
      const overflow = document.createElement("div");
      overflow.className = "ox-live-fine";
      overflow.textContent = "+" + (abnormal.length - 6) + " additional conditions.";
      anomalies.appendChild(overflow);
    }
  }

  function updateSelection() {
    selectionBox.replaceChildren();
    if (!selected || selected.type !== "space") {
      selectionBox.textContent = "SELECT A COMPARTMENT IN THE WIRE VIEW";
      return;
    }
    const id = selected.obj.id;
    selectionBox.textContent = id;
    const details = document.createElement("small");
    if (!knownSpaces.has(id)) {
      details.textContent = "SCHEMATIC ANCHOR — NO PERSISTED ROOM";
    } else if (liveStates.has(id)) {
      details.textContent = "WORLD CONDITION: " + liveStates.get(id).toUpperCase();
    } else {
      details.textContent = "NO PERSISTED ROOM STATE RECEIVED";
    }
    selectionBox.appendChild(details);
  }

  /* The original inspector shows *source* data. Keep it visible, but label its
   * Condition as such and add a distinct persisted condition when available. */
  const sourceDescribe = window.describe;
  if (typeof sourceDescribe === "function") {
    window.describe = function (subject) {
      sourceDescribe(subject);
      const grid = document.getElementById("selection");
      for (const label of grid.querySelectorAll(".k")) {
        if (label.textContent === "Condition") {
          label.textContent = "Source condition";
        }
      }
      if (subject && subject.type === "space") {
        const key = document.createElement("div");
        key.className = "k";
        key.textContent = "World condition";
        const value = document.createElement("div");
        value.className = "v";
        value.textContent = liveStates.has(subject.obj.id)
          ? liveStates.get(subject.obj.id)
          : "not available";
        grid.append(key, value);
      }
      updateSelection();
    };
  }

  /* Preserve the existing draw functions. Anomaly diamonds are a separate,
   * purely informational overlay; no fake door-open or equipment data. */
  const sourceDrawSelected = window.drawSelected;
  window.drawSelected = function () {
    for (const entry of liveStates) {
      const grade = severity(entry[1]);
      if (grade === "nominal" || grade === "unknown") continue;
      const id = entry[0];
      const point = posSpace[id];
      if (!point) continue;
      const colour = grade === "critical" ? "#ec8274" : "#dfb46a";
      const projected = drawPoint(point, colour, 6, 1, "diamond");
      if (projected && !layers.spaces && knownSpaces.has(id)) {
        projectedPick.push({
          x: projected[0], y: projected[1], r: 10,
          type: "space", obj: knownSpaces.get(id), p: point
        });
      }
    }
    sourceDrawSelected();
  };

  function installSnapshot(snapshot) {
    if (!snapshot || snapshot.schema !== "ox.telemetry.spatial/0.1") {
      throw new Error("Unexpected telemetry schema");
    }
    if (snapshot.model_version && snapshot.model_version !== D.model_version) {
      throw new Error("World and drawing model versions differ");
    }
    if (!Array.isArray(snapshot.space_states)) {
      throw new Error("Malformed spatial telemetry");
    }
    liveStates.clear();
    for (const record of snapshot.space_states) {
      if (record && knownSpaces.has(record.id) && typeof record.condition === "string") {
        liveStates.set(record.id, record.condition);
      }
    }
    currentSnapshot = snapshot;
    lastReceived = new Date().toLocaleTimeString();
    checked.textContent = "SAMPLED " + lastReceived;
    count.textContent = String(liveStates.size);
    if (snapshot.topology_complete) {
      labelMode("online", "WORLD DB LINKED");
    } else {
      labelMode("installing", "TOPOLOGY INCOMPLETE");
    }
    coverage.textContent =
      String(snapshot.coverage.spaces_reporting) + " OF " +
      String(snapshot.coverage.spaces_expected) + " SPACES MATERIALISED" +
      " / SHIP MODEL " + String(snapshot.model_version || "UNAVAILABLE");
    renderExceptions();
    updateSelection();
    if (selected && typeof describe === "function") describe(selected);
    invalidate();
  }

  async function refreshState() {
    if (working) return;
    working = true;
    try {
      const response = await fetch("/ox/api/v1/spatial-state/", {
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) {
        throw new Error(response.status === 401
          ? "Session authentication required"
          : response.status === 403
            ? "Developer permission required"
            : "Telemetry HTTP " + response.status);
      }
      installSnapshot(await response.json());
    } catch (error) {
      labelMode("stale", "LINK UNAVAILABLE");
      checked.textContent = lastReceived ? "LAST " + lastReceived : "NO SAMPLE";
      coverage.textContent = String(error && error.message || "Unable to read world state") +
        ". Displayed geometry is the static ship model; prior world data may be stale.";
    } finally {
      working = false;
    }
  }

  document.getElementById("ox-refresh").addEventListener("click", refreshState);
  refreshState();
  window.setInterval(function () {
    if (!document.hidden) refreshState();
  }, intervalMs);
})();

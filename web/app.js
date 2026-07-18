"use strict";

const $ = (selector) => document.querySelector(selector);

const state = {
  case: null,
  status: null,
  mode: "replay",
  busy: false,
};

const suggestedAnswers = {
  "observed-vs-reported": "At this stage it was client-reported only; no direct observation had yet been recorded.",
  "mechanism-established": "No. I observed slower control, but I did not establish whether pain, strength, or another factor caused it.",
  "retest-durability": "I do not know. The improvement was not tested in another set.",
};

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function compactId(value) {
  const text = String(value || "");
  return text.length > 11 ? `…${text.slice(-10)}` : text;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  let payload;
  try {
    payload = await response.json();
  } catch (_error) {
    throw new Error(`Local server returned HTTP ${response.status}.`);
  }
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Local server returned HTTP ${response.status}.`);
  }
  return payload;
}

function setBusy(busy, message = "Working from the current evidence…") {
  state.busy = busy;
  $("#busyMessage").textContent = message;
  $("#busyOverlay").classList.toggle("hidden", !busy);
  renderControls();
}

let toastTimer = null;
function showToast(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 4200);
}

function renderStatus() {
  const codexPill = $("#codexStatus");
  const codex = state.status?.codex;
  codexPill.classList.remove("live", "offline", "neutral");
  if (codex?.available && codex?.logged_in) {
    codexPill.textContent = `Codex ready · ${codex.model}`;
    codexPill.classList.add("live");
  } else if (codex?.available) {
    codexPill.textContent = "Codex found · sign-in required";
    codexPill.classList.add("offline");
  } else {
    codexPill.textContent = "Replay ready · Codex unavailable";
    codexPill.classList.add("offline");
  }
}

function renderControls() {
  const project = state.case;
  const codexReady = Boolean(state.status?.codex?.available && state.status?.codex?.logged_in);
  $("#replayMode").classList.toggle("active", state.mode === "replay");
  $("#codexMode").classList.toggle("active", state.mode === "codex");
  $("#codexMode").disabled = state.busy || !codexReady;
  $("#replayMode").disabled = state.busy;
  $("#resetButton").disabled = state.busy;
  $("#analyzeButton").disabled = state.busy || !project;
  $("#analyzeButton").textContent = state.mode === "codex" ? "Run GPT‑5.6 review" : "Run evidence replay";

  const next = project?.next_packet;
  const nextButton = $("#nextSourceButton");
  nextButton.disabled = state.busy || !next;
  nextButton.textContent = next ? `Add round ${next.round}: ${next.label}` : "All source rounds added";

  const saveButton = $("#saveButton");
  saveButton.disabled = state.busy || !project?.can_formal_save;
  saveButton.textContent = project?.can_formal_save ? "Save reviewed snapshot" : "Formal save blocked";
  $("#submitAnswerButton").disabled = state.busy;
  $("#customSourceButton").disabled = state.busy;
}

function renderMetrics() {
  const stats = state.case?.stats || {};
  $("#metricRounds").textContent = String(stats.rounds || 0);
  $("#metricSources").textContent = String(stats.source_events || 0);
  $("#metricAnalyses").textContent = String(stats.analysis_events || 0);
  $("#metricAnswers").textContent = String(stats.practitioner_answers || 0);
  $("#metricChain").textContent = state.case?.chain?.ok ? "Verified" : "Failed";
  $("#metricChain").style.color = state.case?.chain?.ok ? "var(--green)" : "var(--red)";
}

function eventPresentation(event) {
  const payload = event.payload || {};
  const mapping = {
    case_created: ["case", "Synthetic case started", payload.scenario || "New demo run"],
    source_added: ["source", payload.label || "Source added", payload.content || ""],
    analysis_generated: ["analysis", `${payload.mode || "AI"} evidence review`, payload.output?.summary || "A new reviewed response was added."],
    reflection_question_asked: ["analysis", "AI reflection prompt", payload.question || "Question asked"],
    reflection_answered: ["answer", "Practitioner answer", payload.answer || "Answer added"],
    formal_snapshot_saved: ["snapshot", "Reviewed snapshot saved", payload.save_behavior || "Exact visible result preserved"],
  };
  return mapping[event.event_type] || ["", event.event_type, "Event recorded"];
}

function renderTimeline() {
  const timeline = $("#timeline");
  timeline.replaceChildren();
  const project = state.case;
  if (!project) return;
  $("#caseIdentity").textContent = `${project.case?.display_name || "Synthetic case"} · ${project.case?.scenario || ""} · ${compactId(project.run?.run_id)}`;
  for (const event of project.timeline || []) {
    const [kind, title, description] = eventPresentation(event);
    const card = element("article", `timeline-item ${kind}`);
    const meta = element("div", "event-meta");
    meta.append(
      element("span", "", `Round ${event.round} · #${event.sequence}`),
      element("span", "", String(event.event_type || "").replaceAll("_", " ")),
    );
    card.append(meta, element("strong", "", title), element("p", "", description));
    timeline.append(card);
  }
}

function sourceReference(ids) {
  const list = Array.isArray(ids) ? ids.map(compactId) : [];
  return list.length ? `Sources ${list.join(", ")}` : "No source reference";
}

function renderFindings(containerSelector, items, includeReason = false) {
  const container = $(containerSelector);
  container.replaceChildren();
  if (!Array.isArray(items) || !items.length) {
    container.append(element("p", "empty-list", "None at this stage."));
    return;
  }
  for (const item of items) {
    const card = element("article", "finding");
    card.append(element("p", "", item.statement || ""));
    if (includeReason && item.reason) card.append(element("p", "", `Why: ${item.reason}`));
    const suffix = includeReason && item.uncertainty ? ` · uncertainty ${item.uncertainty}` : "";
    card.append(element("small", "", `${sourceReference(item.source_event_ids)}${suffix}`));
    container.append(card);
  }
}

function renderAnalysis() {
  const payload = state.case?.latest_analysis;
  const output = payload?.output;
  const hasAnalysis = Boolean(output);
  $("#emptyAnalysis").classList.toggle("hidden", hasAnalysis);
  $("#analysisContent").classList.toggle("hidden", !hasAnalysis);
  const badge = $("#analysisBadge");
  badge.classList.remove("waiting", "current", "stale");
  if (!hasAnalysis) {
    badge.textContent = "Waiting for review";
    badge.classList.add("waiting");
    return;
  }
  if (state.case.analysis_stale) {
    badge.textContent = "New evidence · rerun needed";
    badge.classList.add("stale");
  } else {
    badge.textContent = "Current with evidence";
    badge.classList.add("current");
  }
  $("#analysisSummary").textContent = output.summary || "";
  renderFindings("#supportedFindings", output.supported_findings || []);
  renderFindings("#inferences", output.inferences || [], true);
  const unknowns = $("#unknowns");
  unknowns.replaceChildren();
  if (Array.isArray(output.unknowns) && output.unknowns.length) {
    for (const text of output.unknowns) unknowns.append(element("span", "chip", text));
  } else {
    unknowns.append(element("span", "empty-list", "No explicit unknown was returned."));
  }
  $("#nextStep").textContent = output.next_step || "";
  const engine = output.engine || {};
  const pieces = [engine.mode || payload.mode, engine.model, engine.reasoning_effort, engine.duration_ms ? `${engine.duration_ms} ms` : ""].filter(Boolean);
  $("#engineMeta").textContent = pieces.join(" · ");
}

function renderReflection() {
  const questions = state.case?.unresolved_questions || [];
  const card = $("#reflectionCard");
  const question = questions[0];
  card.classList.toggle("hidden", !question);
  if (!question) {
    $("#reflectionAnswer").value = "";
    card.dataset.questionId = "";
    card.dataset.questionKey = "";
    return;
  }
  card.dataset.questionId = question.id || "";
  card.dataset.questionKey = question.key || "";
  $("#reflectionQuestion").textContent = question.question || "";
  $("#reflectionWhy").textContent = question.why || "";
  $("#reflectionAnchor").textContent = `Source anchor: “${question.source_anchor || ""}” · ${sourceReference(question.source_event_ids)}`;
  const importance = $("#questionImportance");
  importance.textContent = question.importance || "growth";
  importance.classList.toggle("required", question.importance === "required");
}

function renderSaveGate() {
  const ready = Boolean(state.case?.can_formal_save);
  const gate = $("#saveGateState");
  gate.textContent = ready ? "Ready" : "Blocked";
  gate.classList.toggle("ready", ready);
  gate.classList.toggle("blocked", !ready);
  const list = $("#saveBlockers");
  list.replaceChildren();
  const blockers = state.case?.save_blockers || [];
  if (ready) {
    list.append(element("li", "", "The current visible result can be saved without another model call."));
  } else {
    for (const blocker of blockers) list.append(element("li", "", blocker));
  }
}

function renderEvidence() {
  const list = $("#evidenceList");
  list.replaceChildren();
  for (const item of state.case?.evidence || []) {
    const card = element("article", `evidence-card${item.explicit_unknown ? " unknown" : ""}`);
    const header = element("header");
    header.append(
      element("span", "", item.label || item.provenance || "Evidence"),
      element("span", item.explicit_unknown ? "unknown-tag" : "", item.explicit_unknown ? "EXPLICIT UNKNOWN" : compactId(item.evidence_id)),
    );
    card.append(header, element("p", "", item.content || ""));
    list.append(card);
  }
  if (!list.childElementCount) list.append(element("p", "empty-list", "No evidence has been added."));

  const excluded = state.case?.excluded_questions || [];
  $("#excludedCount").textContent = String(excluded.length);
  const excludedList = $("#excludedList");
  excludedList.replaceChildren();
  for (const item of excluded) {
    const card = element("article", "excluded-card");
    card.append(element("p", "", item.question || ""), element("small", "", item.exclusion_reason || "Excluded"));
    excludedList.append(card);
  }
  if (!excludedList.childElementCount) excludedList.append(element("p", "empty-list", "No AI reflection prompt has been recorded yet."));
}

function render() {
  renderStatus();
  renderControls();
  if (!state.case) return;
  renderMetrics();
  renderTimeline();
  renderAnalysis();
  renderReflection();
  renderSaveGate();
  renderEvidence();
}

async function refresh() {
  const [statusResponse, caseResponse] = await Promise.all([api("/api/status"), api("/api/case")]);
  state.status = statusResponse.status;
  state.case = caseResponse.case;
  if (state.mode === "codex" && !(state.status?.codex?.available && state.status?.codex?.logged_in)) state.mode = "replay";
  render();
}

async function postAction(path, body, busyMessage) {
  setBusy(true, busyMessage);
  try {
    const response = await api(path, { method: "POST", body });
    state.case = response.case;
    render();
    if (state.case.action?.message) showToast(state.case.action.message);
  } catch (error) {
    showToast(error.message || "The local action failed.", true);
  } finally {
    setBusy(false);
  }
}

function bindEvents() {
  $("#replayMode").addEventListener("click", () => {
    state.mode = "replay";
    renderControls();
  });
  $("#codexMode").addEventListener("click", () => {
    if (state.status?.codex?.logged_in) state.mode = "codex";
    renderControls();
  });
  $("#nextSourceButton").addEventListener("click", () => postAction(
    "/api/source/next", {}, "Adding the next source round to the same case…",
  ));
  $("#analyzeButton").addEventListener("click", () => postAction(
    "/api/analyze", { mode: state.mode }, state.mode === "codex" ? "GPT‑5.6 is reviewing only the current evidence…" : "Replaying the evidence contract…",
  ));
  $("#saveButton").addEventListener("click", () => postAction(
    "/api/formal-save", {}, "Saving the exact visible reviewed result…",
  ));
  $("#resetButton").addEventListener("click", () => {
    if (window.confirm("Create a new synthetic demo run? Earlier synthetic runs will be preserved.")) {
      postAction("/api/reset", {}, "Creating a fresh synthetic run…");
    }
  });
  $("#exportButton").addEventListener("click", () => window.open("/api/export", "_blank", "noopener,noreferrer"));
  $("#suggestedAnswerButton").addEventListener("click", () => {
    const key = $("#reflectionCard").dataset.questionKey;
    $("#reflectionAnswer").value = suggestedAnswers[key] || "I can only confirm what is already recorded; the remaining detail is unknown.";
    $("#reflectionAnswer").focus();
  });
  $("#unknownAnswerButton").addEventListener("click", () => {
    $("#reflectionAnswer").value = "I do not know. This was not observed or tested in the available record.";
    $("#reflectionAnswer").focus();
  });
  $("#submitAnswerButton").addEventListener("click", () => {
    const questionId = $("#reflectionCard").dataset.questionId;
    const answer = $("#reflectionAnswer").value.trim();
    if (!answer) {
      showToast("Enter a practitioner answer or use the explicit unknown button.", true);
      return;
    }
    postAction(
      "/api/reflection/answer",
      { question_id: questionId, answer },
      "Adding the practitioner answer as evidence…",
    ).then(() => { $("#reflectionAnswer").value = ""; });
  });
  $("#customSourceButton").addEventListener("click", () => {
    const sourceType = $("#customSourceType").value;
    const label = $("#customSourceLabel").value.trim();
    const content = $("#customSourceContent").value.trim();
    if (!content) {
      showToast("Add fictional source content first.", true);
      return;
    }
    postAction(
      "/api/source/custom",
      { source_type: sourceType, label, content },
      "Adding another source round to the same case…",
    ).then(() => {
      $("#customSourceLabel").value = "";
      $("#customSourceContent").value = "";
    });
  });
}

async function start() {
  bindEvents();
  try {
    await refresh();
  } catch (error) {
    showToast(error.message || "Could not connect to the local ObserveOS server.", true);
    $("#codexStatus").textContent = "Local server unavailable";
    $("#codexStatus").classList.add("offline");
  }
}

document.addEventListener("DOMContentLoaded", start);

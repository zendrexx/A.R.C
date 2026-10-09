"use strict";

const token = document.querySelector('meta[name="arc-token"]').content;
const titles = {
  overview: ["Overview", "Evidence you can inspect. Progress you can trust."],
  memory: ["Memory search", "Find recorded decisions, errors, and changes."],
  tasks: ["Tasks & evidence", "See what is planned, observed, tested, and confirmed."],
  timeline: ["Timeline", "A chronological view of recorded project events."],
  checkpoints: ["Checkpoints", "Review saved continuity snapshots and their freshness."],
  incidents: ["Incidents", "Find earlier debugging experience with source references."],
  settings: ["Settings & privacy", "Local model status and project-scoped controls."],
};
const initialParameters = new URL(location.href).searchParams;
const initialPane = initialParameters.get("pane");
const state = {
  projects: [], project: null, pane: titles[initialPane] ? initialPane : "overview",
  timelineOffset: 0, taskId: initialParameters.get("task"),
};
const el = (id) => document.getElementById(id);
const node = (tag, className, value) => {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (value !== undefined && value !== null) item.textContent = String(value);
  return item;
};
const clear = (target) => target.replaceChildren();
const formatDate = (value) => value ? new Date(value).toLocaleString() : "No timestamp";
const labelState = (value) => (value || "unknown").replaceAll("_", " ");

function toast(message, error = false) {
  const target = el("toast");
  target.textContent = message;
  target.className = error ? "shown error" : "shown";
  clearTimeout(toast.timeout);
  toast.timeout = setTimeout(() => target.className = "", 5500);
}

async function api(route, params = {}, data) {
  const url = new URL(route, location.origin);
  const values = data === undefined && state.project && !params.project
    ? {...params, project: state.project.path} : params;
  for (const [key, value] of Object.entries(values)) {
    if (value !== null && value !== undefined) url.searchParams.set(key, value);
  }
  const options = data === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json", "X-ARC-Token": token},
    body: JSON.stringify(data),
  };
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}

async function post(route, values = {}) {
  return api(route, {}, {...values, project: state.project.path});
}

async function attempt(action) {
  try { await action(); } catch (error) { toast(error.message || String(error), true); }
}

function showDetails(title, value) {
  el("dialog-title").textContent = title;
  el("dialog-content").textContent = JSON.stringify(value, null, 2);
  el("detail-dialog").showModal();
}

function record(target, item, options = {}) {
  const row = node("article", "record");
  const head = node("div", "record-head");
  const title = node("strong", "record-title", options.title || item.summary || item.title || "Record");
  head.append(title);
  if (options.badge || item.kind) head.append(node("span", "record-badge", labelState(options.badge || item.kind)));
  row.append(head);
  if (options.description) row.append(node("p", "record-description", options.description));
  const meta = node("div", "record-meta");
  if (item.created_at) meta.append(node("span", "", formatDate(item.created_at)));
  if (item.source_ref) meta.append(node("code", "", item.source_ref));
  if (options.meta) meta.append(node("span", "", options.meta));
  row.append(meta);
  if (options.onClick) {
    const button = node("button", "record-action", options.actionLabel || "Inspect evidence");
    button.type = "button";
    button.addEventListener("click", options.onClick);
    row.append(button);
  }
  target.append(row);
  return row;
}

function empty(target, text) { clear(target); target.append(node("p", "empty-state", text)); }

function renderRecordingBadge(paused) {
  el("recording-badge").textContent = paused ? "Recording paused" : "Manual recording on";
  el("recording-badge").classList.toggle("paused", paused);
}

function updateLocation(values) {
  const url = new URL(location.href);
  for (const [key, value] of Object.entries(values)) {
    if (value === null) url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  }
  history.replaceState(null, "", url.pathname + url.search);
}

async function loadProjects() {
  state.projects = await api("/api/projects");
  const picker = el("project-select");
  clear(picker);
  for (const project of state.projects) {
    const parent = project.path.split("/").filter(Boolean).at(-2);
    const option = node("option", "", parent ? `${project.name} · ${parent}` : project.name);
    option.title = project.path;
    option.value = project.path;
    picker.append(option);
  }
  const requested = new URL(location.href).searchParams.get("project");
  state.project = state.projects.find((project) => project.path === requested)
    || state.projects.find((project) => project.path === state.project?.path)
    || state.projects[0] || null;
  if (state.project) {
    picker.value = state.project.path;
    el("register-panel").hidden = true;
    el("project-content").hidden = false;
    updateLocation({project: state.project.path});
    await loadPane();
  } else {
    el("register-panel").hidden = false;
    el("project-content").hidden = true;
    el("recording-badge").textContent = "No project selected";
  }
}

function setPane(pane, load = true) {
  state.pane = pane;
  updateLocation({pane});
  for (const [name] of Object.entries(titles)) el(`pane-${name}`).hidden = name !== pane;
  for (const button of document.querySelectorAll("[data-pane]")) {
    button.classList.toggle("active", button.dataset.pane === pane);
    if (button.dataset.pane === pane) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  el("page-title").textContent = titles[pane][0];
  el("page-subtitle").textContent = titles[pane][1];
  if (load) attempt(loadPane);
}

async function loadPane() {
  if (!state.project) return;
  if (!["overview", "settings"].includes(state.pane)) {
    const {state: project} = await api("/api/overview");
    renderRecordingBadge(project.recording.recording_paused);
  }
  const loaders = {
    overview: loadOverview, memory: loadMemory, tasks: loadTasks,
    timeline: () => loadTimeline(true), checkpoints: loadCheckpoints,
    incidents: loadIncidents, settings: loadSettings,
  };
  await loaders[state.pane]();
}

function metric(target, value, label) {
  const card = node("div", "metric");
  card.append(node("strong", "", value), node("span", "", label));
  target.append(card);
}

async function loadOverview() {
  const {state: project, handoff} = await api("/api/overview");
  const grid = el("metric-grid"); clear(grid);
  metric(grid, handoff.total_unfinished_tasks, "Unfinished tasks");
  metric(grid, handoff.total_confirmed_tasks, "Current confirmations");
  metric(grid, project.memory_index?.indexed_records ?? 0, "Indexed records");
  metric(grid, project.memory_index?.pending_records ?? 0, "Pending index");
  renderRecordingBadge(project.recording.recording_paused);
  const next = el("next-task"); clear(next);
  if (handoff.suggested_next_task) {
    const task = handoff.suggested_next_task;
    next.append(node("h3", "", task.title), node("p", "", labelState(task.state)),
      node("p", "", task.next_step));
    const button = node("button", "text-button", "Review task evidence →");
    button.addEventListener("click", () => {state.taskId = task.id; setPane("tasks");});
    next.append(button);
  } else next.append(node("p", "muted", "No unfinished tasks are recorded."));
  const git = el("git-status"); clear(git);
  git.append(node("p", "", `${project.git.changed_paths.length} changed path(s) in the current Git snapshot.`));
  git.append(node("code", "fingerprint", project.git.fingerprint));
  if (project.latest_checkpoint) git.append(node("p", "helper", `Latest checkpoint: ${project.latest_checkpoint.stale ? "stale" : "current snapshot"}.`));
  const evidence = el("handoff-evidence"); clear(evidence);
  if (!handoff.key_evidence.length) empty(evidence, "No selected evidence yet. Record project activity with the CLI.");
  for (const item of handoff.key_evidence) record(evidence, item, {
    description: item.selection_reason,
    onClick: () => attempt(async () => showDetails(item.source_ref, await api("/api/event", {id: item.id}))),
  });
}

async function searchMemory() {
  const query = el("search-query").value.trim();
  if (!query) return;
  const result = await api("/api/search", {q: query, mode: el("search-mode").value});
  el("search-summary").textContent = `${result.hits.length} result(s) · ${labelState(result.mode)} · ${result.indexed_records} indexed, ${result.pending_records} pending`;
  if (result.reason || result.notice) toast(result.reason || result.notice);
  const target = el("search-results"); clear(target);
  if (!result.hits.length) empty(target, "No matching recorded events.");
  for (const hit of result.hits) record(target, hit, {
    meta: `${result.score_kind}: ${Number(hit.score).toFixed(3)}`,
    onClick: () => attempt(async () => showDetails(hit.source_ref, await api("/api/event", {id: hit.event_id}))),
  });
}

async function loadMemory() {
  const query = initialParameters.get("q");
  const mode = initialParameters.get("mode");
  if (query) {
    el("search-query").value = query;
    if (["semantic", "hybrid", "keyword"].includes(mode)) el("search-mode").value = mode;
    await searchMemory();
  }
}

async function loadTasks() {
  const {state: project} = await api("/api/overview");
  const target = el("task-list"); clear(target);
  if (!project.tasks.length) empty(target, "No tasks recorded yet.");
  for (const task of project.tasks) record(target, task, {
    badge: task.state,
    description: task.agent_claim ? `Unverified claim: ${task.agent_claim}` : undefined,
    onClick: () => attempt(() => loadTask(task.id)), actionLabel: "Review evidence",
  });
  if (state.taskId && project.tasks.some((task) => task.id === state.taskId)) await loadTask(state.taskId);
  else empty(el("task-detail"), "Select a task to inspect its evidence.");
}

async function loadTask(id) {
  state.taskId = id;
  const review = await api("/api/task", {id});
  const target = el("task-detail"); clear(target);
  target.append(node("h3", "", review.task.title), node("p", "state-line", `Current state: ${labelState(review.task.state)}`));
  if (review.missing.length) {
    target.append(node("h4", "", "Still needed"));
    for (const item of review.missing) target.append(node("p", "helper", item));
  } else target.append(node("p", "helper", "Current evidence requirements are satisfied."));
  if (review.task.state === "tests_passed") {
    const button = node("button", "primary-button", "Confirm completed task");
    button.type = "button";
    button.addEventListener("click", () => attempt(async () => {
      if (!confirm(`Confirm “${review.task.title}” as complete after reviewing its evidence?`)) return;
      await post("/api/task/confirm", {id});
      toast("Task confirmed at the current Git state.");
      await loadTasks();
    }));
    target.append(button);
  }
  target.append(node("h4", "", "Recent evidence"));
  if (!review.recent_evidence.length) target.append(node("p", "empty-state", "No linked evidence."));
  for (const item of review.recent_evidence) record(target, item, {
    badge: item.evidence_status, onClick: () => attempt(async () =>
      showDetails(item.source_ref, await api("/api/event", {id: item.id}))),
  });
}

async function loadTimeline(reset = false) {
  if (reset) {state.timelineOffset = 0; clear(el("timeline-list"));}
  const result = await api("/api/timeline", {offset: state.timelineOffset, kind: el("timeline-kind").value});
  const target = el("timeline-list");
  if (reset && !result.events.length) empty(target, "No events recorded in this view.");
  for (const item of result.events) record(target, item, {
    meta: item.session_id ? `Session ${item.session_id}` : undefined,
    onClick: () => attempt(async () => showDetails(item.source_ref, await api("/api/event", {id: item.id}))),
  });
  state.timelineOffset += result.events.length;
  el("timeline-more").hidden = !result.has_more;
}

async function loadCheckpoints() {
  const items = await api("/api/checkpoints");
  const target = el("checkpoint-list"); clear(target);
  if (!items.length) empty(target, "No checkpoints saved yet.");
  for (const item of items) record(target, item, {
    title: `Candidate checkpoint ${item.id.slice(0, 8)}`,
    badge: item.stale ? "stale" : "current Git snapshot",
    description: "This snapshot is unconfirmed.",
    onClick: () => showDetails(`Checkpoint ${item.id}`, item.payload), actionLabel: "View snapshot",
  });
}

async function loadIncidents() {
  const items = await api("/api/incidents");
  const target = el("incident-list"); clear(target);
  if (!items.length) empty(target, "No incidents recorded yet.");
  for (const item of items) record(target, item, {
    title: item.error_summary, badge: item.status,
    description: item.cause ? `Recorded cause: ${item.cause}` : "No cause recorded",
    onClick: () => attempt(async () => showDetails(`Incident ${item.id}`, await api("/api/incident", {id: item.id}))),
  });
}

async function searchIncidents() {
  const result = await api("/api/incident-search", {
    q: el("incident-query").value.trim(), cause: el("incident-cause").value.trim(),
  });
  const target = el("incident-search-results"); clear(target);
  target.append(node("p", "helper", `${result.candidates.length} candidate(s), ${result.different_causes.length} different recorded cause(s). ${result.interpretation}`));
  for (const [group, items] of [["candidate", result.candidates], ["different cause", result.different_causes]]) {
    for (const item of items) record(target, item, {
      title: item.error?.summary || item.incident_id,
      badge: group,
      description: `${item.cause ? `Recorded cause: ${item.cause}. ` : ""}${item.guidance}`,
      meta: item.error?.source_ref,
      onClick: () => attempt(async () => showDetails(`Incident ${item.incident_id}`, await api("/api/incident", {id: item.incident_id}))),
    });
  }
}

async function loadSettings() {
  const {state: project} = await api("/api/overview");
  const paused = project.recording.recording_paused;
  el("pause-description").textContent = paused
    ? "Recording is paused for this project. Existing memory is still readable."
    : "Manual recording is available for this project.";
  el("pause-button").textContent = paused ? "Resume recording" : "Pause recording";
  el("pause-button").dataset.paused = String(paused);
  renderRecordingBadge(paused);
}

function bind() {
  for (const button of document.querySelectorAll("[data-pane]")) button.addEventListener("click", () => setPane(button.dataset.pane));
  el("refresh-button").addEventListener("click", () => attempt(loadPane));
  el("project-select").addEventListener("change", () => attempt(async () => {
    state.project = state.projects.find((project) => project.path === el("project-select").value);
    state.taskId = null;
    updateLocation({project: state.project.path});
    await loadPane();
  }));
  el("add-project-toggle").addEventListener("click", () => {el("register-panel").hidden = !el("register-panel").hidden;});
  el("register-form").addEventListener("submit", (event) => {event.preventDefault(); attempt(async () => {
    const project = await api("/api/projects", {}, {
      path: el("project-path").value.trim(), test_command: el("test-command").value.trim() || null,
    });
    updateLocation({project: project.path});
    toast("Project registered."); await loadProjects();
  });});
  el("search-form").addEventListener("submit", (event) => {event.preventDefault(); attempt(searchMemory);});
  el("task-add-form").addEventListener("submit", (event) => {event.preventDefault(); attempt(async () => {
    await post("/api/task/add", {title: el("new-task-title").value.trim()});
    el("new-task-title").value = ""; toast("Task added."); await loadTasks();
  });});
  el("timeline-kind").addEventListener("change", () => attempt(() => loadTimeline(true)));
  el("timeline-more").addEventListener("click", () => attempt(() => loadTimeline(false)));
  el("checkpoint-create").addEventListener("click", () => attempt(async () => {
    await post("/api/checkpoint"); toast("Candidate checkpoint saved."); await loadCheckpoints();
  }));
  el("incident-search-form").addEventListener("submit", (event) => {event.preventDefault(); attempt(searchIncidents);});
  el("ai-check").addEventListener("click", () => attempt(async () => {
    el("ai-status").textContent = "Checking local model…";
    const status = await api("/api/ai-status");
    el("ai-status").textContent = status.status === "ready"
      ? `${status.model} ready (${status.vector_dimensions} dimensions)`
      : `${status.model} unavailable: ${status.reason}`;
  }));
  el("index-button").addEventListener("click", () => attempt(async () => {
    const result = await post("/api/index"); toast(`Indexed ${result.indexed} event(s) with ${result.model}.`);
  }));
  el("pause-button").addEventListener("click", () => attempt(async () => {
    const paused = el("pause-button").dataset.paused !== "true";
    await post("/api/pause", {paused}); toast(paused ? "Recording paused." : "Recording resumed.");
    await loadSettings();
  }));
  el("delete-button").addEventListener("click", () => attempt(async () => {
    const expected = `DELETE ${state.project.name}`;
    const entered = prompt(`Permanently delete A.R.C. memory for ${state.project.name}? Type ${expected} to continue:`);
    if (entered === null) return;
    if (entered !== expected) throw new Error("Confirmation did not match; nothing was deleted.");
    const result = await post("/api/delete", {confirmation: entered});
    state.taskId = null;
    toast(`Deleted ${result.deleted_events} events and ${result.deleted_tasks} tasks.`);
    await loadSettings();
  }));
  el("dialog-close").addEventListener("click", () => el("detail-dialog").close());
}

const initialKind = initialParameters.get("kind");
if (initialKind) el("timeline-kind").value = initialKind;
setPane(state.pane, false);
bind();
attempt(loadProjects);

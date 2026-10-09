"""Choose a small, source-linked set of recorded events for a project handoff."""

from collections.abc import Sequence


def _category_and_reason(event: dict, current_fingerprint: str) -> tuple[str, str] | None:
    kind = event["kind"]
    if kind == "decision":
        return "decision", "Recorded design decision"
    if kind == "error":
        return "failure", "Recorded error; resolution is not inferred"
    if kind == "attempt":
        return "attempt", "Recorded debugging attempt; outcome is not inferred"
    if kind == "resolution":
        return "resolution", "Explicitly reported resolution; success is not inferred"
    if kind == "incident_cause":
        return "context", "Explicitly recorded incident cause"
    if kind == "task_correction":
        return "correction", "Explicit task-status correction"
    if kind == "test":
        if not event["details"].get("passed"):
            return "failure", "Failed configured test; resolution is not inferred"
        if event["fingerprint"] == current_fingerprint:
            return "progress", "Passing configured test at the current Git fingerprint"
        return None
    if kind == "confirmation":
        if event["fingerprint"] == current_fingerprint:
            return "progress", "Explicit confirmation at the current Git fingerprint"
        return None
    if kind == "git" and event["details"].get("has_visible_changes"):
        return "progress", "Recorded changed paths; correctness is not inferred"
    if kind == "note":
        return "context", "Explicit project note"
    # Claims and clean-tree observations do not establish project progress.
    return None


def select_handoff_evidence(events: Sequence[dict], open_task_ids: set[str],
                            current_fingerprint: str, limit: int = 6) -> list[dict]:
    """Rank recorded facts, with room for decisions, failures, attempts, and resolutions."""
    if limit < 1:
        raise ValueError("Handoff evidence limit must be positive")
    base_score = {"decision": 70, "failure": 65, "resolution": 60, "attempt": 55,
                  "correction": 50, "progress": 35, "context": 15}
    ranked = []
    seen_summaries = set()
    latest_corrections = {}
    for position, event in enumerate(events):
        if event["kind"] == "task_correction" and event["task_id"] not in latest_corrections:
            latest_corrections[event["task_id"]] = (position, event)
    for position, event in enumerate(events):
        correction = latest_corrections.get(event["task_id"])
        if correction:
            correction_position, correction_event = correction
            retained_git_id = correction_event["details"].get("implementation_event_id")
            if (position > correction_position
                    and event["kind"] in {"git", "test", "confirmation", "task_correction"}
                    and event["id"] != retained_git_id):
                continue
            if (position < correction_position and event["kind"] == "git"
                    and correction_event["details"].get("to_state") == "planned"
                    and event["fingerprint"] == correction_event["fingerprint"]):
                continue
        category_and_reason = _category_and_reason(event, current_fingerprint)
        if category_and_reason is None:
            continue
        category, reason = category_and_reason
        duplicate_key = (category, event["task_id"], event["summary"].casefold().strip())
        if duplicate_key in seen_summaries:
            continue
        seen_summaries.add(duplicate_key)
        linked_to_open_task = event["task_id"] in open_task_ids
        score = base_score[category] + (20 if linked_to_open_task else 0)
        score += max(0, 10 - position // 20)
        if linked_to_open_task:
            reason += "; linked to unfinished task"
        item = {
            "id": event["id"], "kind": event["kind"], "category": category,
            "summary": event["summary"], "source_ref": event["source_ref"],
            "created_at": event["created_at"], "task_id": event["task_id"],
            "session_id": event["session_id"], "git_fingerprint": event["fingerprint"],
            "selection_reason": reason,
        }
        ranked.append((score, -position, item))
    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)

    selected = []
    selected_ids = set()
    for category in ("decision", "failure", "attempt", "resolution"):
        candidate = next((entry for entry in ranked if entry[2]["category"] == category), None)
        if candidate and len(selected) < limit:
            selected.append(candidate)
            selected_ids.add(candidate[2]["id"])
    for candidate in ranked:
        if len(selected) >= limit:
            break
        if candidate[2]["id"] not in selected_ids:
            selected.append(candidate)
            selected_ids.add(candidate[2]["id"])
    selected.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [{**item, "rank": rank} for rank, (_, _, item) in enumerate(selected, start=1)]

# Phase 7 field trial and backup demo

Use the real `.arc/arc.sqlite3` database for the product story. Keep `.arc/first-test.sqlite3` and `.arc/phase5-test.sqlite3` labelled as practice data. The dashboard reads whichever file `ARC_DB` selects; it does not import GitHub history or record edits automatically.

## Live demo preflight

From the A.R.C. repository root:

```bash
source .venv/bin/activate
export ARC_DB="$PWD/.arc/arc.sqlite3"
arc state
arc handoff
arc search "Why did we use a local browser dashboard?" --semantic-only
arc dashboard --no-browser
```

Start Ollama first if semantic search reports it unavailable. Check the returned `mode`, source reference, project name, and current task state before presenting. If the search misses its intended event, show the actual result and choose another recorded question; do not prearrange a false claim. Keep the dashboard terminal open. The browser address is `http://127.0.0.1:8765/` unless another port was selected.

For a repeatable two-round check of the real database's dashboard routes, run this separately. It reads the real project and writes no events:

```bash
python -m scripts.verify_phase7_journey \
  --db "$ARC_DB" --project "$PWD" \
  --task 7c7e92f66806 \
  --event 8fbf5d9e14ac4ebba2c2163a97c685d1 \
  --query "Why did we use a local browser dashboard instead of another service?"
```

This checks dashboard handoff, task review, local semantic search, source resolution, and checkpoint inspection twice. It does not disable Wi-Fi or substitute for the on-camera offline trial.

## Two to three minute backup recording

**Recorded backup, 2026-10-09:** `$HOME/Desktop/ARC-backup-demo.mov` is a 62-second silent capture of the live local dashboard. Exact video frames were inspected at the Overview, task review, dated decision timeline, semantic search, and checkpoint views. It covers a shorter dashboard path than the full shot list below. The network-off segment, MCP segment, narration, and unfamiliar-user trial remain to be filmed or demonstrated separately; see [the evidence log](TEST_RESULTS.md). The file is kept outside Git.

| Time | Screen action | Point to prove |
|---|---|---|
| 0:00–0:20 | Show the A.R.C. project selected in Overview and its suggested next task. | This is the actual Git project and its selected local database. |
| 0:20–0:55 | Open Tasks & evidence, select the task, and read its current state plus one `arc:event/<id>` reference. | A claim, an observed change, a passing test, and explicit confirmation have distinct meanings. |
| 0:55–1:25 | Open Timeline; filter to decisions or errors and inspect a source event. | A.R.C. preserves a dated, inspectable record rather than a generated summary alone. |
| 1:25–1:55 | Search with a paraphrased question in Semantic mode; show `mode: semantic` and open the returned event. | `all-minilm` retrieves from locally indexed summaries. A hit is evidence to inspect, not proof that an inferred explanation is correct. |
| 1:55–2:20 | With networking disabled, repeat the semantic query and inspect a candidate checkpoint. | The local model, SQLite, and dashboard remain available without cloud access. Record the actual network state on screen. |
| 2:20–2:45 | Show `arc handoff` or the fresh-session MCP result next to the dashboard. | CLI, dashboard, and MCP consume the same evidence rules. |

Record an actual screen session on the demo Mac, save the video locally, and replay it while disconnected. Do not mark the video delivered until the file exists and plays. A dashboard-only recording is acceptable if the MCP segment cannot be shown in the time available; label any omitted step in the evidence log.

On this Mac, the built-in recorder supports a three-minute timed capture:

```bash
screencapture -v -V 180 "$HOME/Desktop/ARC-backup-demo.mov"
```

Start the command only when the presenter is ready to show the real app. macOS may request Screen Recording access. After it stops, play the file and enter its filename and actual contents in [TEST_RESULTS.md](TEST_RESULTS.md). Do not commit the video or a private database to Git.

## Unfamiliar-user and baseline trial

Have the documentation/video teammate use the app without coaching. Give only this objective: **“Find the current unfinished task, its next required step, and the source event that explains one decision.”** Record whether they selected the correct project, how long it took, any wrong turns, and the exact source IDs they found. This is the open Phase 6 usability gate and contributes Phase 7 evidence.

For a narrow baseline comparison, give a second participant or the same participant after a break the README and `git log`/`git status` only. Ask the same three questions. Record time, correctness, and whether each answer has a current source reference. A.R.C. may have better evidence freshness, but do not claim faster or clearer handoffs until participants produce measured results. Git and README remain useful sources for code and setup; this trial measures the specific continuity questions above.

## Offline capture and evidence log

The user previously reported a successful disconnected-network `--semantic-only` search. To make that result repeatable, capture a new run with the exact command, `mode`, event reference, date/time, and visible network-off state. Do not disable the demo machine's networking during an active remote session; the person at the Mac should control that step. Use [TEST_RESULTS.md](TEST_RESULTS.md) for the result and filename. A.R.C. sends embedding requests only to local Ollama at `127.0.0.1`; `arc handoff` and checkpoint review do not require Ollama.

## Known demo limits

- Manual `arc capture`, `arc test`, and `arc index` are still required. Automatic observation and indexing are future phases.
- Semantic hits and incident matches are candidates, not diagnoses. The Phase 7 labelled incident fixture found the intended record in 6/10 paraphrases and surfaced candidates for 4/15 unrelated or different-cause queries.
- A passing configured test supports the current Git fingerprint; it does not prove every behavior works. Commits and edits can make prior evidence historical.
- The offline chatbot, VS Code extension, and automated background watcher have not been implemented.

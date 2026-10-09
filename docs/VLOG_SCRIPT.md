# A.R.C. vlog script

One presenter, speaking to camera and recording the real A.R.C. dashboard. The time marks are editing guides; speak naturally and leave enough time for viewers to read the screen. Use the real `.arc/arc.sqlite3` database, not the practice databases.

## Before recording

From the repository root, start local Ollama if it is not running. In the demo terminal:

```bash
source .venv/bin/activate
export ARC_DB="$PWD/.arc/arc.sqlite3"
arc state
arc handoff
arc search "Why did we use a local browser dashboard?" --semantic-only
arc dashboard --no-browser
```

Open the loopback address printed by `arc dashboard` (normally `http://127.0.0.1:8765/`). Check that the selected project, task state, `mode: semantic`, and returned `arc:event/<id>` reference match what appears on camera. The recorded dashboard decision has source `arc:event/8fbf5d9e14ac4ebba2c2163a97c685d1`; open that event only if it is actually returned. Task and checkpoint freshness can change when Git changes, so read the status shown on the day of filming. Blur private paths and notes before sharing.

## Short promo — about 50–60 seconds

| Time | Show | Say |
|---|---|---|
| 0:00–0:09 | Face camera, then a project with many open files. | “Ever come back to a coding project and spend ten minutes figuring out what you were doing? I kept losing the *why* behind a change.” |
| 0:09–0:21 | A.R.C. Overview and the suggested next task. | “So we built A.R.C.—Agent Recall and Continuity. It keeps a local record of tasks, decisions, Git changes, and test results.” |
| 0:21–0:37 | Tasks & evidence; point to the displayed state and one source event. | “Here’s the difference: a task claim is just a claim. A.R.C. links it to the change and the test, and shows when that evidence is no longer current.” |
| 0:37–0:51 | Search the dashboard with a paraphrased question. Show `mode: semantic`, then open the returned source event. | “I can ask *why* we chose the local dashboard. The local model finds the recorded decision, and I can open the original event instead of trusting a summary.” |
| 0:51–1:00 | Face camera or show `arc handoff`. | “Right now, recording and indexing are manual. But a new coding session can already pick up an evidence-linked handoff. That’s A.R.C.: a clearer place to restart.” |

## Full vlog and backup demo — about 2½–3 minutes

| Time | Show | Say |
|---|---|---|
| 0:00–0:22 | Face camera; cut to the A.R.C. repository. | “Hi, I’m [name]. This is A.R.C., the development-memory tool we’re building. When I return to a project—or open a fresh coding-agent session—I need to know what changed, what passed, and why a decision was made. Commit history alone doesn’t always answer those questions.” |
| 0:22–0:47 | Dashboard Overview with the real project selected. Point to the suggested next task. | “This is the actual project running on my Mac. A.R.C. stores selected events in a local SQLite database. The Overview shows a suggested next task and step from those recorded events.” |
| 0:47–1:18 | Tasks & evidence. Open the Phase 6/7 task and one `arc:event/<id>` source. | “Here’s the task evidence. An unverified claim starts as planned. A recorded Git change can show implementation was observed. A passing configured test at the current Git state supports ‘tests passed.’ We review the evidence, then explicitly confirm completion. If the project changes, the older test becomes historical. The source IDs let me check each step.” |
| 1:18–1:42 | Timeline; select the dashboard decision and open its source event. | “This timeline keeps our decision with its date and source event. We recorded why we chose a browser dashboard that runs locally. I’m opening the original note, so you can see the explanation we actually saved.” |
| 1:42–2:10 | Memory search for “Why did we use a local browser dashboard instead of another service?” Show `mode: semantic`, the returned event, and its source. | “Now I’ll ask the same question in different words. Our local `all-minilm` model searches indexed summaries by meaning. The result links back to that decision event. A search hit is a lead to inspect, not proof that every suggested explanation is right.” |
| 2:10–2:36 | Terminal: `arc handoff`. Point to unfinished work and source references. If the real-database MCP entry is configured, optionally show a fresh Codex handoff instead. | “The handoff collects unfinished work and selected source-linked events for the next session. The CLI, dashboard, and MCP connection read the same local evidence, so the next coding session can ask what is current and inspect the original records.” |
| 2:36–2:55 | Face camera; return to dashboard Overview. | “Today I still run capture, test, and indexing steps myself. Automatic observation, a local chat interface, and the VS Code extension are future work. What already works is the part I need most: a project history I can search, inspect, and continue from.” |

### Optional network-off insert

Only use this after recording the exact command, visible network-off state, returned `mode: semantic`, and source event in [TEST_RESULTS.md](TEST_RESULTS.md). Replace the 2:10–2:36 handoff scene or make a longer cut:

> “I’ve turned off networking on this Mac. The local model and stored index still return this recorded event. Here’s the command, its semantic mode, and the source I can inspect.”

Do not use the existing 62-second silent backup as proof of this segment: it shows the dashboard, but not the disconnected-network trial or MCP. If a live search returns another event, show and describe that actual result. A similar incident returned by search is a candidate to investigate, not a confirmed diagnosis.

## On-screen text and final check

- Opening title: **A.R.C. — Agent Recall & Continuity**
- Search caption: **Local semantic search · inspect the source event**
- Evidence caption: **Claim → observed change → current test → explicit confirmation**
- Closing caption: **Current prototype: manual capture and indexing**

Record the terminal and dashboard at a readable size. Confirm the final file plays locally; keep a copy on the demo Mac. The [Phase 7 shot list](PHASE7_DEMO.md) has the longer capture path, and [TEST_RESULTS.md](TEST_RESULTS.md) lists which claims still need recorded evidence.


ano to script bato pang bading
# Phase 7 validation results

These results describe observed behavior on 2026-10-09, not general product accuracy. The evaluation data are labelled synthetic development incidents stored in a temporary SQLite database. They are never mixed into `.arc/arc.sqlite3`.

## Retrieval and false candidates

Run from the repository root with local Ollama and `all-minilm` available:

```bash
.venv/bin/python -m scripts.evaluate_retrieval
.venv/bin/python -m scripts.evaluate_incidents
```

The first evaluator used seven stored summaries and five paraphrased queries. Semantic and hybrid search placed the intended event first for **4/5**, within the first three for **5/5**; keyword search placed it first for **1/5**. The median warm local semantic query in this run was **29.06 ms**. An unrelated query still returned a low-scoring raw semantic hit (cosine **0.131**), so raw search hits must be inspected rather than assumed relevant.

The Phase 7 incident evaluator used **10 labelled incident summaries**, **10 positive paraphrases**, and **15 negative queries**, including five similar-looking errors with different causes. At the current **0.55** similarity cutoff, the intended incident appeared among candidates for **6/10** positives; **4/15** negatives produced at least one candidate. The median warm local query was about **20 ms**. The printed JSON includes individual cases and a diagnostic threshold sweep. Lowering the cutoff to **0.40** would recover **9/10** positives in this set but surface candidates for **5/15** negatives. This small synthetic set is not enough to justify changing the production cutoff, and a candidate is never labelled a confirmed diagnosis.

Practical implication: the demo can show local paraphrase retrieval, but it must also show source inspection and the candidate warning. Retrieval and false-match calibration on actual diverse incidents remains open.

## Real project handoff versus static sources

The [measured handoff comparison](HANDOFF_COMPARISON.md) asks the same five questions of A.R.C. and README plus Git on the real repository. A.R.C. supplied exact task, step, test, and decision references; Git supplied the code diff that A.R.C. deliberately does not store. Until a second person completes the [timed field trial](PHASE7_DEMO.md), this is limited to source coverage and cannot establish that A.R.C. makes people faster.

On 2026-10-09, A.R.C. was used on this repository itself. Session `35df4c33ca0f` recorded task `7c7e92f66806` (“Phase 6 dashboard and Phase 7 validation”), decision `arc:event/8fbf5d9e14ac4ebba2c2163a97c685d1`, Git observation `arc:event/3901318c0b5a4865aadcea87a25f95af`, and passing configured test `arc:event/c07d919baa04428595414635fea79e0c`. Ten pending events were indexed. At that Git fingerprint the task was `tests_passed` and the handoff suggested reviewing and confirming it. The session was then ended. These events were recorded after some implementation work had already occurred; their timestamps are recording times, not reconstructed edit times.

A real-database semantic query, “Why did we use a local browser dashboard instead of another service?”, returned the explicit decision first with `mode: semantic` and cosine **0.442**. The returned source ID resolves to the stored decision. The lower-ranked hits were not automatically treated as answers. Networking was not disabled for this run.

| Continuity question | A.R.C. real handoff/search | README and current Git status/log |
|---|---|---|
| Current unfinished task and next step | Task ID, `tests_passed` at the then-current fingerprint, and explicit review/confirmation step | README describes Phase 6/7 generally; Git lists changed paths and commits. Neither includes this task ID. |
| Evidence that tests passed for that task | Linked `arc:event/c07d919baa04428595414635fea79e0c` with recorded command, exit code, and fingerprint | README reports suite counts; Git does not record the configured test result or its freshness. |
| Why the local dashboard was chosen | Explicit decision `arc:event/8fbf5d9e14ac4ebba2c2163a97c685d1` retrieved by paraphrase | README explains local behavior, but does not provide this dated decision event or source ID. |

This is a one-project source-coverage comparison. A timed, blinded user comparison remains open. Any later repo edit or commit makes a previously passing test historical until `arc test --task 7c7e92f66806` is rerun at the new fingerprint.

## Offline and usability evidence still needed

- A two-round real-database dashboard check on 2026-10-09 retrieved the unfinished task, resolved the expected decision event as the top semantic hit, and inspected checkpoint `e71de067af3a` twice. It took **515.7 ms** and **537.4 ms** end to end on this Mac. The task appeared as `implementation_observed` because documentation edits after its earlier passing test changed the Git fingerprint; that is the intended freshness behavior. The script uses loopback but did not turn off Wi-Fi.
- A user reported semantic search succeeding with networking disabled on 2026-10-09, but the exact terminal output and a visible network-off recording have not been saved.
- Automated dashboard HTTP tests and an installed-command smoke test passed. An unfamiliar person has not yet completed the Phase 6 task-finding gate unaided.
- A 62.02-second silent QuickTime backup recording exists at `$HOME/Desktop/ARC-backup-demo.mov` (2880 × 1800). Exact decoded frames show Overview, Tasks & evidence, decision Timeline, semantic Memory search with the dated decision first, and Checkpoints. This dashboard-only recording does not show networking disabled, an MCP handoff, or an unfamiliar user. It has not been copied into the repository or checked for playback with networking off.
- The [local pitch deck](PITCH_DECK.html) is ready to present; the presenter should rehearse it with the actual dashboard and source IDs.

The Phase 7 completion gate stays open until the main journey is repeated on the demo Mac, with the observed offline state and recording documented.

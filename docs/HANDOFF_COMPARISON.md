# Real-project handoff comparison

This is a source-coverage comparison on the A.R.C. repository, observed on 2026-10-09. It answers the same five questions from (A) `arc handoff`, `arc task review`, and the linked event, and (B) `README.md`, `git status --short`, and the last five `git log` subjects. It does **not** measure how fast an unfamiliar person can use either source.

| Question at the measured Git snapshot | A.R.C. handoff | README + Git alone |
|---|---|---|
| What exact task is unfinished, and what state is it in? | `7c7e92f66806`, “Phase 6 dashboard and Phase 7 validation,” `tests_passed` at that fingerprint | README described phases generally; neither README nor the last five commit subjects contained this task ID. |
| What is its next required step? | Review evidence, then explicitly confirm if complete | No task-specific review/confirmation step tied to this ID. |
| Which configured test currently supports it? | `arc:event/37e3034ddd11408bb5534eef1e9aecce`, with passing exit code and matching fingerprint | README stated suite counts; Git did not record a test run or its fingerprint. |
| Why was the local dashboard approach chosen? | Explicit decision `arc:event/8fbf5d9e14ac4ebba2c2163a97c685d1`, with time and task link | README explained the local design but had no dated decision event. The last five commit subjects were `.`. |
| What exactly changed in the working tree? | A.R.C. listed 21 changed paths, but deliberately did not store source content or a diff | Git status listed the changed and untracked paths, and Git diff could show code content. |

**Result on this narrow rubric:** A.R.C. gave exact, source-linked answers to the four continuity/evidence questions; Git supplied the actual code diff that A.R.C. does not keep. README and Git are complementary, not obsolete. These observations are specific to this repository and its terse commit messages. Better README maintenance and commit messages could improve the baseline. No timed usability advantage is claimed.

Reproduce the core checks from the repository root with the real database:

```bash
ARC_DB="$PWD/.arc/arc.sqlite3" .venv/bin/arc handoff
ARC_DB="$PWD/.arc/arc.sqlite3" .venv/bin/arc task review 7c7e92f66806
rg -n '7c7e92f66806|37e3034ddd11408bb5534eef1e9aecce|8fbf5d9e14ac4ebba2c2163a97c685d1' README.md
git status --short
git log -5 --format='%h %s'
```

The `rg` command is expected to find none of those exact identifiers in README at the measured snapshot. A later file edit or commit changes A.R.C.'s Git fingerprint and can make a formerly passing test historical; rerun `arc task review` to see the current state rather than reusing this table as a live status report.

The unfamiliar-user timed comparison remains a separate field trial in [PHASE7_DEMO.md](PHASE7_DEMO.md).

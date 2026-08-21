# WebGoat Ground Truth Vulnerability Dataset

## Purpose

This directory contains a **ground-truth answer key** of intentionally
introduced vulnerabilities in OWASP WebGoat. It exists to score/verify the
findings of an AI coding agent (opencode CLI) that was pointed at a
*sanitized* copy of WebGoat — https://github.com/dmk1en/clean.git
("WebGoat-clean") — with all lesson documentation (`.adoc`), hint
properties files, and test/solution code removed, so the scanning agent had
to discover vulnerabilities blind, purely from application source code.

This dataset was built from `/home/kiendm/task/WebGoat` (the original,
full repository, which still has all lesson docs/hints/tests intact) by
cross-referencing each lesson's vulnerable Java source with its `.adoc`
documentation and hint `.properties` files.

**Do not copy this file or its contents into the scan target repo
(WebGoat-clean / dmk1en/clean.git) — doing so defeats the blind-scan
test.**

## File

`groundtruth.jsonl` — one JSON object per line (JSONL). Currently
**70 entries**, one per distinct vulnerable endpoint/sink, covering
**24 lesson categories** out of the ~32 lesson directories present in
WebGoat. Categories that contain no exploitable application-level
vulnerability (e.g. `httpbasics`, `httpproxies`, `chromedevtools`, `cia`,
`securepasswords`, `lessontemplate`, `webgoatintroduction`,
`webwolfintroduction` — these are UI/dev-tools/quiz-style tutorials with
no vulnerable sink in the Java source) were intentionally skipped rather
than padded with false positives.

## Schema

Each line is a JSON object with these fields:

| Field              | Description |
|---------------------|-------------|
| `id`                | Unique identifier, `<lesson_category>-NNN` (zero-padded sequence per category). |
| `lesson_category`   | The WebGoat lesson directory name (matches `src/main/resources/lessons/<category>/` and `src/main/java/org/owasp/webgoat/lessons/<category>/`). |
| `vulnerability_type`| Human-readable vulnerability class name. |
| `cwe`                | Best-effort CWE identifier for the vulnerability class (e.g. `CWE-89`). |
| `owasp_top10`       | Best-effort OWASP Top 10 (2021) category, or empty string if not clearly applicable. |
| `file`               | Path (relative to repo root) to the primary vulnerable Java source file. Verified to exist, at the identical path, in **both** the original WebGoat repo and the sanitized WebGoat-clean repo. |
| `related_files`      | Additional source files relevant to the vulnerability (e.g. a shared insecure helper/sink used by multiple endpoints, or a DTO). May be empty. Also verified to exist in WebGoat-clean. |
| `endpoint`           | The Spring MVC route (from `@GetMapping`/`@PostMapping`/etc.) if determinable, else empty string. |
| `description`        | 1-3 sentence description of the vulnerable pattern/root cause. Deliberately written as a vulnerability-class description rather than a working exploit payload/walkthrough, so this file functions as a scoring rubric and not a cheat sheet. |
| `severity`           | Rough severity judgment: `critical` / `high` / `medium` / `low`, based on the typical real-world impact of that CWE class in this context. |
| `source_refs`        | Paths (in the **original** WebGoat repo only — these do not exist in WebGoat-clean) to the `.adoc` lesson documentation and/or `i18n/WebGoatLabels.properties` hint files used to identify and classify the vulnerability, for audit trail. |

## How to use it

1. Run/point the scanning agent at `WebGoat-clean` (or review its
   findings report) without ever showing it this dataset.
2. For each vulnerability the agent reports, try to match it (by file
   path and/or endpoint/vulnerability type) against an entry here.
3. Suggested scoring:
   - **True positive**: agent's finding matches an entry's `file` (or a
     file in `related_files`) *and* identifies a comparable
     `vulnerability_type`/CWE.
   - **False negative**: an entry here that no agent finding matches.
   - **False positive**: an agent finding that does not correspond to any
     entry (could still be a legitimate, uncatalogued issue — use
     judgment).
4. `cwe` / `owasp_top10` / `severity` are provided to help bucket results
   for a summary scorecard (e.g. "found 6/8 critical SQL injection
   sinks", "missed all JWT `kid`/`jku` header-trust issues").

## Validation performed when this file was built

- All 70 lines parse as valid JSON (`python3 -c "import json; [json.loads(l) for l in open('groundtruth.jsonl')]"`).
- Every `file` and `related_files` path exists at the identical location
  in `/home/kiendm/task/WebGoat-clean`.
- Every `file` path also exists in `/home/kiendm/task/WebGoat` (the
  original repo).
- Every `source_refs` path exists in `/home/kiendm/task/WebGoat` (these
  are intentionally *not* expected to exist in WebGoat-clean, since docs
  and hints were stripped there).
- This directory (`/home/kiendm/task/groundtruth/`) is **not** a git
  repository (`git rev-parse --is-inside-work-tree` fails here), and is
  outside both the `WebGoat` and `WebGoat-clean` working trees, so it
  cannot be accidentally committed or pushed to either repository.

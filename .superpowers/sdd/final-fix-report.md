# Final review — must-fix remediation

**Date:** 2026-10-13  
**Branch:** `feature/interview-lens`

## Must-fix items

### 1. Setup re-POST wipe (Task 9)

- **Backend:** unchanged (source APIs still replace segments when explicitly called).
- **Frontend:** `Setup.tsx` hydrates `source_type` from `GET /session`; `sourceNeedsIngest()` in `setup.ts` skips sample/paste/upload when the session already has a persisted source unless the user changes type, uploads a new file, or enters new paste text.
- **Tests:** `setup.test.ts` — reopen + new paste cases.

### 2. Concurrent jobs (Task 5)

- **Backend:** `db.session_has_active_job()` for statuses `queued|transcribing|diarizing|analyzing`; `POST /transcribe` (media path) and `POST /analyze` return **409** when active.
- **Tests:** `test_concurrent_jobs.py` (analyze + transcribe).

### 3. Session status + reopen Reports

- **Backend:** `db.update_session_status(..., "done")` after successful analyze; `SessionOut.has_report` on `GET /sessions/{id}`.
- **Frontend:** `App.openSession` routes to Reports when `status === 'done'` or `has_report`; else transcript/setup by segment count.
- **Tests:** `test_analyze_api.py` asserts `status` and `has_report` after happy analyze.

## Verification

| Suite | Result |
| --- | --- |
| Backend `pytest` | 55 passed |
| Frontend `vitest run` | 15 passed (4 files) |

## Not in scope (review optional items)

- Transcribe job terminal `ready`, analyze `MIN_JD_CHARS`, Ollama 503 preflight, upload size cap.

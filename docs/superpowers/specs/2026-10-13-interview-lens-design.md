# InterviewLens — Dual-Report Interview Analyzer (App 5)

Design for portfolio App 5. A local **interview studio** that turns an interview recording (or pasted transcript) plus a job description into **two** evidence-backed reports: one for the **candidate** (feedback, strengths, improvements) and one for the **hiring side** (fit, PASS / borderline / NO). Expands beyond the original “paste transcript → action items” brief while keeping validated structured JSON, no guessing, and a clear failure story.

## Decisions

- **Product goal:** Cool, unique React demo — dual-audience interview analysis with hybrid input and local-only stack (Approach 2 — Two-step studio).
- **Audiences:** Same analysis, two views — Candidate report (constructive) and Hiring report (decision-oriented).
- **Input (hybrid):** Bundled **sample video**, user **audio/video upload**, or **paste transcript**. All paths end in an editable diarized transcript before analyze.
- **Pipeline:** Two-step — (1) transcribe + diarize → review/edit speakers & text → (2) analyze with JD → dual reports.
- **STT + speakers:** Local **faster-whisper** for transcription + **pyannote** speaker diarization (aligned to segments). Map speakers to `interviewer` | `candidate` | `unknown` (heuristic: first speaker default interviewer unless user remaps). User can correct labels before analyze. Pyannote requires a free Hugging Face token in `.env` (`HF_TOKEN`). If diarization cannot run, fall back to single-speaker `unknown` segments and require manual labeling.
- **LLM:** Local **Ollama** chat `qwen2.5:7b`. Browser never calls Ollama. No cloud LLM required for the core demo. Model name overridable via env.
- **Persistence:** **SQLite** for sessions, JD, transcript segments, jobs, reports. Media files on disk under a local uploads/sample path (not committed secrets).
- **Frontend:** React (Vite) + TypeScript + Tailwind — branded **InterviewLens**. Unique modern UX; not Streamlit; not a clone of Apps 1–4.
- **Ports:** Frontend **3004**, API **8004**, Ollama **11434**.
- **Out of scope v1:** Zoom/Meet bots, cloud STT/LLM, PDF export, multi-user auth, live ATS/CRM, legal/HR compliance claims, background worker fleets.

## Architecture

Three runtime pieces on the developer machine:

1. **Browser + React (Vite) + TypeScript + Tailwind** — InterviewLens UI. Default port **3004**.
2. **FastAPI** — sessions, JD, source ingest, transcribe/analyze jobs, transcript edits, reports, SQLite. Default port **8004**.
3. **Ollama on the host** (`http://127.0.0.1:11434`) — `qwen2.5:7b`. Whisper + diarization run **inside** the FastAPI process (or a local subprocess), not in the browser.

```
[Chrome / InterviewLens]
  stepper · setup (JD + source) · transcript studio · dual reports
        │ HTTP/JSON only
        ▼
[FastAPI :8004]
  SQLite (sessions, segments, jobs, reports)
  media on disk → faster-whisper + pyannote diarization
  analyze → ChatOllama → Pydantic dual JSON
        │
        ▼
[Ollama :11434]
  qwen2.5:7b
```

**Job status (poll):** `queued` → `transcribing` → `diarizing` → `ready` → `analyzing` → `done` | `error`.

## Frontend — InterviewLens

**Concept:** One composition that reads as an **interview review studio** — calm focus, clear next step, not a metrics dashboard of cards.

| Token | Choice |
| --- | --- |
| Brand | **InterviewLens** as hero-level wordmark on home and chrome |
| Canvas | Atmospheric studio background (gradient/pattern — not flat white; not purple-glow AI cliché; not cream/terracotta serif) |
| Accent | Ink `#0B1220`, mist panels, electric mint `#3EE0B7` + signal amber `#F5B942` for verdict/emphasis (not ReplyDesk green, not FAQ teal/coral, not purple glow) |
| Type | Display **Sora**; UI **Manrope** |
| Layout | Always-visible **stepper**: Setup → Transcript → Reports |

**UX rules (required):**

- One job per screen; user always knows where they are and what to do next.
- Plain language labels (“Job description”, “Interview recording”, “Candidate feedback”, “Hiring decision”).
- Progress copy that explains work (“Transcribing audio…”, “Separating speakers…”, “Writing both reports…”), not a mute spinner.
- Reports scannable: big verdict + scores first; details and evidence quotes below (collapsible OK).
- Empty states with a single clear CTA.
- At least 2–3 intentional motions: step transition, job progress, report reveal.

**Anti-copy rules:** No EchoFAQ orb; no ReplyDesk WhatsApp chrome; no App 1 teal/coral FAQ; no App 2 lead sidebar; no purple-on-white gradient theme; no cream/terracotta broadsheet look.

### Screens

1. **Home** — InterviewLens brand, New session, recent sessions from SQLite.
2. **Setup** — JD textarea or `.txt`/`.md` upload; source picker: Sample video | Upload media | Paste transcript.
3. **Transcript studio** — ordered segments with timestamps; speaker chips (Interviewer / Candidate / Unknown); inline text edit; job progress; Continue to analyze when JD + non-empty transcript exist.
4. **Reports** — tabs **Candidate** | **Hiring**; score displays; evidence quote cards; hiring badge `PASS` / `Borderline` / `NO`; assistive disclaimer.

## Data model (SQLite)

- `sessions` — id, title, created_at, updated_at, status, jd_text, source_type (`sample_video` | `upload` | `paste`), media_path (nullable)
- `transcript_segments` — id, session_id, idx, start_ms, end_ms, speaker (`interviewer` | `candidate` | `unknown`), text
- `jobs` — id, session_id, kind (`transcribe` | `analyze`), status, error_message, created_at, updated_at
- `reports` — id, session_id, candidate_json, hiring_json, model_name, created_at

Media files live under a local data directory (gitignored). Bundled sample media + optional pre-shipped sample transcript for reliable demos.

## Analysis schema (Pydantic → strict JSON)

**Shared score block (each 0–100 + short rationale):**  
`jd_match`, `answer_depth`, `communication`, `structure`, `overall`.

**Candidate report**

- `summary` — constructive overall feedback
- `strengths[]` — `{ point, evidence_quote }`
- `improvements[]` — `{ point, evidence_quote, tip }`
- `question_notes[]` — `{ topic_or_question, note, evidence_quote }` when detectable; else empty
- `readiness_note` — practice focus areas
- `unknowns[]` — insufficient evidence items

**Hiring report**

- `recommendation` — `pass` | `borderline` | `no`
- `hire_confidence` — 0–100
- `fit_summary` — vs JD
- `skill_evidence[]` — `{ skill, evidence_quote }`
- `gaps[]` — `{ skill_or_requirement, note }`
- `red_flags[]` — `{ note, evidence_quote }` (empty if none)
- `follow_up_questions[]` — suggested next-interview questions
- `unknowns[]`
- `disclaimer` — fixed assistive / human-decides text

**Hard rules:** Quotes must appear in the transcript (or normalized segment text). Missing evidence → `unknowns` / gaps — **never invent** skills, scores-as-certainty, or a PASS without support. Invalid model JSON → one retry → error (no silent partial fake report).

## API (FastAPI)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API up; Ollama reachability; Whisper readiness flag |
| `GET` | `/sessions` | list recent sessions |
| `POST` | `/sessions` | create session |
| `GET` | `/sessions/{id}` | session + segments + latest report refs |
| `PUT` | `/sessions/{id}/jd` | save JD text |
| `POST` | `/sessions/{id}/source/paste` | ingest pasted transcript (optional pre-labeled lines) |
| `POST` | `/sessions/{id}/source/upload` | upload audio/video |
| `POST` | `/sessions/{id}/source/sample` | attach bundled sample |
| `POST` | `/sessions/{id}/transcribe` | start transcribe+diarize job (no-op path if paste already complete; may still normalize speakers) |
| `PATCH` | `/sessions/{id}/transcript` | save edited segments |
| `POST` | `/sessions/{id}/analyze` | start analysis job (requires JD + ≥1 segment) |
| `GET` | `/sessions/{id}/jobs/{job_id}` | poll job status |
| `GET` | `/sessions/{id}/reports` | dual reports |

Browser talks **only** to FastAPI.

## Error handling

| Case | Behavior |
| --- | --- |
| Empty JD or empty transcript on analyze | HTTP 400, clear message |
| Ollama down / timeout | Job `error` or HTTP 503 with fix hint (`ollama serve`, pull model) |
| Whisper / diarization failure | Job `error`; paste path still usable |
| Low-confidence speakers | Segments may be `unknown`; UI prompts user to label before analyze |
| Invalid LLM JSON | Retry once; then fail openly |
| Missing API/HF token when required for diarization model | Clear setup error in README + `/health` |

## Testing

pytest with Ollama and Whisper/diarization **mocked**:

1. **Happy path:** JD + labeled transcript → both reports validate against Pydantic models; recommendation enum valid.
2. **Failure path:** Empty transcript or missing JD → rejected; no report row written.
3. **Honesty path:** Transcript lacks a JD-required skill → appears in `gaps` / `unknowns`, not fabricated `skill_evidence`; no automatic `pass` without support.

Frontend: light Vitest only if small pure helpers exist (e.g. stepper/status copy); not required for v1 core.

## Delivery

- Public GitHub repo under `mahsamabbas` (name `interview-lens` unless assignment thread requires `meeting-action-extractor`).
- Root README: description, features, stack, API, env (`.env.example` only), Docker + local run, tests, limitations, link to this spec.
- Commits authored as **mahsamabbas** only (no Cursor co-author trailer).
- Secrets (`.env`, HF token, `.github_key`) never committed; `.github_key` stays in parent folder only.
- Docker Compose: frontend + API; Ollama on host via `host.docker.internal`. Whisper models documented for first-run download.

## Mapping to original App 5 brief

| Brief ask | InterviewLens |
| --- | --- |
| Meeting/interview text in | Paste **or** video → transcript |
| Structured validated output | Pydantic dual JSON reports |
| Missing fields stay unknown | `unknowns` / gaps; no guessing |
| No audio *required* | Paste path works without STT |
| Concise summary + actionable next steps | Candidate improvements + hiring follow-ups + recommendation |

Action-item extraction is **not** the primary product angle; dual interview feedback is. Paste-only still satisfies a minimal structured-extraction demo if video tooling is unavailable.

## Known limitations

- Quality and latency depend on Mac hardware, Whisper model size, diarization, and `qwen2.5:7b`.
- Long recordings are slow; demos should use the short bundled sample.
- Diarization can mis-assign speakers — transcript studio edit is the accuracy safety net.
- Not a substitute for human hiring judgment or employment law review.
- Simulated local product only — no production ATS integration.

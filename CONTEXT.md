# PROJECT_CONTEXT.md — AI Video Assistant (RAG)

> **Living document.** Regenerated at the end of every work step.
> Upload the latest copy at the start of any new chat. Claude has no memory between chats, so this file is the memory.

**Last updated:** 2026-09-22 (revision 5)
**Current phase:** Phase 0 remediation (I-30) — user ran `check_env.py` (passed) and `phase0_setup.sh` for real; the run surfaced a real secrets-into-git incident that needed fixing before Phase 1 continues
**Next up:** User does, in this order: `rm -rf .git` (nothing was pushed, confirmed with user — see I-30) → apply the `step1-fix-gitignore-and-setup-script.zip` patch → re-run `bash phase0_setup.sh` → confirm with `git show --stat baseline-v0` that no `.env*`/`.backup-step1/` files appear → rotate keys (0.1, still open) → run `SMOKE_TEST.md` → report results. Then Step 1.4.
**Overall status:** Phase 0 files (`.gitignore`, `requirements.txt`, `.env.example`, `check_env.py`, `phase0_setup.sh`) exist in the project root now — the previous revision described them as delivered but they were never actually present in the zip; that's fixed, and `phase0_setup.sh` had a real bug (see I-27) caught by testing it. The user already had their own `SMOKE_TEST.md` in place (uploaded separately) — kept as-is, not overwritten. Phase 1 steps 1.1–1.3 are done and behavior-verified as far as this sandbox allows (see "How this was verified" below). **No visible behavior has changed** — same UI, same pipeline stages, same outputs; the changes are all internal (config plumbing, logging, dead code). Delivered as a **step-wise patch zip** (`step1-phase0-and-1.1-1.3.zip`), not a full project re-download — see the delivery note at the end of this file for the exact unzip command.

### How this was verified (no live GROQ/Whisper/ffmpeg-against-real-media in this environment)
- Full static review of every `.py` file.
- `python -m py_compile` on the whole tree — clean.
- The project's own `tests/test_config.py` (28 tests) run and pass via a local pytest-compatible shim, since real `pytest` isn't installed here.
- `check_env.py` smoke-run against import stubs for the missing packages — logic verified, not real installs.
- `phase0_setup.sh` run end-to-end on a scratch copy (twice, to check idempotency) — this is how I-27 was found and fixed.
- **Not done here, needs the user:** running the actual Streamlit app, a real pipeline run against Groq/Whisper, and `SMOKE_TEST.md` end to end.
- **Update:** the user ran `check_env.py` (all green) and `phase0_setup.sh` for real. The former was clean. The latter surfaced I-30 — see the issues table and the delivery note at the end of this file for the exact fix.

### Paste this into a new chat (if the current chat runs out)
> I'm refactoring my Streamlit "AI Video Assistant" project. I've attached `PROJECT_CONTEXT.md` (the living plan: locked decisions, roadmap, progress) and my latest project zip. Read the context file fully, do not re-litigate the locked decisions (D-xx), continue from "Next up", work one step at a time, and at the end of every step give me the fully regenerated `PROJECT_CONTEXT.md` plus the changed files.

Status legend: `[x]` done · `[~]` in progress · `[ ]` not started · `[!]` blocked (reason noted)

---

## 1. How this file is maintained

After every completed step, Claude will:
1. Tick the step's checkbox and add a one-line note of what changed and which files were touched.
2. Update **Current phase**, **Next up** and **Last updated** in the header.
3. Update issue statuses in section 6 and add any newly found issues.
4. Add a line to the Session Log (section 10).
5. Output the full, regenerated file. Do not patch old copies by hand.

The user's job: upload the latest `PROJECT_CONTEXT.md` (plus the current project zip if code changed) when starting a new chat.

Rule for Phases 1 and 2: **no behavior or visual change.** Every step is checked against the smoke-test checklist (Step 0.6) before ticking.

---

## 2. Product summary

**AI Video Assistant**: paste a YouTube link or upload a file; it transcribes (Whisper local / Sarvam for Hinglish), summarizes (Groq `openai/gpt-oss-120b` via LangChain), extracts action items / decisions / open questions, classifies category, builds a Chroma vector index with timestamped chunks, and lets the user chat with the video (answers cite `[MM:SS]`), grab video frames, generate quizzes and PDF notes.

**Stack today:** Streamlit · LangChain · Groq · Whisper (local) · Sarvam API · sentence-transformers `all-MiniLM-L6-v2` · ChromaDB · yt-dlp + ffmpeg + pydub · fpdf · plotly/pandas · JSON files for storage.

**Direction:** Turn it into a production-grade **study-first video assistant**. One user dashboard, with study-planning features living inside it as sections, plus a role-gated **Admin dashboard**.

---

## 3. Locked decisions

| ID | Decision |
|---|---|
| D-01 | **One user dashboard.** No separate "AI Study Planner dashboard". Study planning is a **section inside the existing dashboard**, built from existing features (chat, notes, quiz, history, stats) plus a small amount of new data (topics, saved quiz attempts, goals, plan items). |
| D-02 | **Admin dashboard = role-gated views in the same Streamlit app**, not a separate app. Visible only when `users.role == "admin"`. |
| D-03 | **UI stack: keep Streamlit, restructured.** `st.navigation` multipage, `.streamlit/config.toml` theme, reusable components, small CSS file. FastAPI + React is deferred. The services layer keeps that door open. |
| D-04 | **Database: SQLite via SQLAlchemy**, written so switching to Postgres is a config change. Existing JSON data is migrated (JSON files kept as backup). |
| D-05 | **Product name: "AI Video Assistant"** everywhere (retire "VideoMind AI"). |
| D-06 | **Analysis modes:** `Study` (default), `Meeting`, `General`. The mode selects the prompts and which result tabs are shown. Meeting features (action items, decisions, open questions) are kept. |
| D-07 | **Planner logic split:** LLM extracts topics/difficulty/priorities. **Plain Python** does scheduling and spaced repetition (1/3/7/14-day intervals). The LLM never does date math. |
| D-08 | **Auth:** argon2 hashing, existing SHA-256 users re-hashed transparently at next login. Roles `user` / `admin`. First admin bootstrapped from `ADMIN_EMAIL` env var. |
| D-09 | **Persistent login** via signed session cookie (login must survive browser refresh). |
| D-10 | **Vector store:** one persistent Chroma collection **per video**. No global wipe. Deleted only when the video is deleted. Rebuilt on demand from the stored transcript if missing. |
| D-11 | **Jobs:** every pipeline run is logged in a `jobs` table (Phase 1). It runs synchronously with live progress until Phase 6, then moves to a background worker. |
| D-12 | **Input:** local file *paths* are replaced by a real file uploader (hosted apps cannot read user paths). Upload cap configurable, default 500 MB. |
| D-13 | **Transcription behind an interface:** local Whisper (default), Sarvam (Hinglish). A Groq Whisper backend is an optional later add. |
| D-14 | **Dependencies/logging/config:** `requirements.txt` (top-level, unpinned, because installed versions can't be seen from outside), plus a lock file the user generates with `pip freeze > requirements.lock.txt` once everything runs. Also `.env.example`, central `config.py`, structured `logging` instead of `print`. System dependency: `ffmpeg`. The user's original `requirements.txt` was stale (see I-26); it was replaced by a version matching the real imports. |
| D-15 | **Media & storage policy** (see section 5B): temp audio and chunks live only in a per-job temp folder and are always deleted when the job ends. YouTube videos are never stored. Uploaded originals are kept only so frame grabs keep working, and are removed when the video is deleted. Audio is normalized to 16 kHz mono right after download. |
| D-16 | **UI design system** (see section 5A): Inter + JetBrains Mono only, a 7-step type scale, a small colour-token palette, a 4 px spacing grid, Material icons instead of emoji in the app chrome, light theme first. Applied in Phase 3. |

### Assumptions (veto any of these and this file gets updated)
- **A-01** Deployment target is a single server / Docker container (not serverless).
- **A-02** Expected scale: tens to low hundreds of users. SQLite is fine at that scale; Postgres is a later switch.
- **A-03** Admin(s) are the project owner(s), created via `ADMIN_EMAIL`, not through public signup.

---

## 4. Target structure

```
app.py                       entry: config, theme, auth gate, st.navigation
config.py                    env/settings/paths/model names
.streamlit/config.toml       theme (colors, font) + upload limit
requirements.txt · .env.example · .gitignore · README.md · Dockerfile

views/                       thin pages, render only, no business logic
  public/    home.py · login.py · signup.py
  user/      home.py · analyze.py · chat.py · library.py · video_detail.py
             study_plan.py · progress.py · settings.py
  admin/     overview.py · users.py · jobs.py · usage.py · storage.py · audit.py

ui/
  components/   sidebar · navbar · stat_card · chat_bubble · quiz_widget
                notes_view · video_card · empty_state · progress_ring
  theme.py      design tokens
  base.css      small (target < 150 lines, no !important wars)

services/                    business logic, no Streamlit imports
  pipeline.py · chat_service.py · quiz_service.py · notes_service.py
  planner_service.py · analytics_service.py · auth_service.py
  admin_service.py · job_service.py

core/                        AI + media (kept, tidied)
  llm.py                     single get_llm() + invoke_with_retry
  prompts/                   study.py · meeting.py · general.py
  ingest/                    audio.py · transcriber.py · frames.py
  rag/                       vector_store.py · rag_engine.py
  generators/                summarizer · extractor · notes · quiz · topics

db/                          models.py · session.py · repositories/
scripts/                     migrate_json_to_sqlite.py
tests/                       pytest for services
data/                        (gitignored) app.db · chroma/ · media/ · frames/
```

> Note: the folder is `views/`, not `pages/`. Streamlit ignores `pages/` auto-discovery when `st.navigation` is used, and the name avoids confusion.

---

## 5. Sections and where every feature goes

### User dashboard (sidebar navigation)

| Section | Purpose | Comes from (current code) |
|---|---|---|
| **Home** | Overview: continue where you left off, today's study tasks, reviews due, quick stats, recent videos | New landing; parts of Stats and the sidebar "Recent" |
| **Analyze** | Add a video: YouTube URL or file upload, language, mode, live progress | `chat_input` source detection + `_run_pipeline_with_status` + `main.run_pipeline` |
| **Chat** | Q&A on a selected video, timestamp citations, frame grabs, `quiz` / `notes` commands | Chat branch of `render_dashboard` |
| **Library** | All videos: search, filter by category/language, open, delete | `History` page + `chat_sessions` "Recent" |
| ↳ **Video detail** | Tabs: Summary · Notes · Quiz · Transcript · (Action items / Decisions / Questions in Meeting mode) · Export | `Results` page + notes/quiz rendering currently inside chat |
| **Study Plan** *(new, inside dashboard)* | Goals (deadline, hours/day), generated schedule, check-off, topic mastery, spaced-review queue, replan | New data on top of quiz + notes + topics |
| **Progress** | Charts: activity, categories, languages, quiz score trend, streak, mastery | `Stats` page (+ new quiz/mastery data) |
| **Settings** | Display name, password change, default language/mode, export/delete my data | New (production need) |

Sidebar keeps: **New Analysis** button, section links, **Recent (5 only)**, profile popover (Landing page / Log out).

### Admin dashboard (role-gated)

| Section | Contents |
|---|---|
| **Overview** | Users, analyses, job success rate, avg pipeline duration, active today, storage used, key/config health (present or missing, never values) |
| **Users** | Search, role change, disable/enable, delete user data |
| **Jobs** | All pipeline runs, filter by status, error details, retry |
| **Usage & Cost** | Calls per provider (Groq, Sarvam) and operation, latency, 429 count, tokens where available |
| **Storage** | Disk use by media/frames/vector; cleanup actions |
| **Audit Log** | Admin actions and security events |

### Code-to-code move map

| Current | Moves to |
|---|---|
| `app.py` if/elif router | `app.py` with `st.navigation` |
| `main.py` `run_pipeline` | `services/pipeline.py` |
| `ui/dashboard.py` intent helpers (`_is_quiz_request`, `_is_notes_request`, `_classify_frame_request`, …) | `services/chat_service.py` |
| `ui/dashboard.py` quiz/notes rendering | `ui/components/quiz_widget.py`, `notes_view.py` |
| `ui/dashboard.py` Chat / Results / Stats / History | `views/user/chat.py` / `video_detail.py` / `progress.py` / `library.py` |
| `ui/sidebar.py`, `ui/navbar.py` | `ui/components/sidebar.py`, `navbar.py` |
| `ui/styles.py` (999 lines) | `.streamlit/config.toml` + `ui/theme.py` + `ui/base.css` |
| `ui/home_page.py`, `auth_pages.py` | `views/public/*` |
| `utils/history_manager.py`, `utils/chat_sessions.py`, `auth/auth_manager.py` | `db/repositories/*` + `services/*` |
| `utils/audio_processor.py` | `core/ingest/audio.py` |
| `core/transcriber.py`, `frame_extractor.py` | `core/ingest/transcriber.py`, `frames.py` |
| 5× `get_llm()` and `invoke_with_retry` (in `extractor.py`) | `core/llm.py` |
| `core/summarizer.py`, `extractor.py`, `notes_generator.py`, `quiz_generator.py` | `core/generators/*` |
| `core/vector_store.py`, `rag_engine.py` | `core/rag/*` |

---

## 5A. UI design system (locked now, applied in Phase 3)

**Audit of the current UI:** 35 distinct font sizes, 27 distinct hex colours, 3 font families (Inter, Space Grotesk, JetBrains Mono), no `.streamlit/config.toml`, colours hard-coded inline in `auth_pages`, `home_page` and `dashboard`. That is why it feels inconsistent.

**Typography**
- Families: **Inter** (all UI, body and headings) and **JetBrains Mono** (timestamps like `[12:34]`, code, transcript metadata). Space Grotesk is dropped.
- Weights: 400 body · 500 labels/buttons · 600 headings · 700 hero and big numbers.
- Line height: 1.6 body, 1.25 headings. Headings get letter-spacing −0.02em.
- Scale (replaces all 35 sizes):

| Token | Size | Used for |
|---|---|---|
| `text-xs` | 12 px | badges, meta, table captions |
| `text-sm` | 14 px | secondary text, sidebar items, buttons |
| `text-md` | **16 px** | body and chat messages (base size) |
| `text-lg` | 18 px | lead paragraphs, card titles |
| `text-xl` | 22 px | section headings |
| `text-2xl` | 28 px | page titles |
| `text-hero` | clamp(36 px, 5vw, 56 px) | landing hero only |

**Colour tokens** (replaces 27 hex values; light theme first, dark optional later)
- Brand: `primary #2563eb`, `primary-dark #1e3a8a`, `accent #14b8a6`, `warning #f59e0b`
- Neutrals: `text #0f172a`, `text-muted #475569`, `border #e2e8f0`, `surface #f8fafc`, `card #ffffff`
- Semantic: `success #16a34a`, `error #dc2626`
- Body text contrast must be at least 4.5:1.

**Spacing, shape, layout**
- 4 px grid: 4 · 8 · 12 · 16 · 24 · 32 · 48.
- Radius: 12 px cards, 8 px inputs and buttons, pill for badges. One soft shadow style.
- Content max width about 1200 px. Chat column about 820 px (65–75 characters per line). Sidebar about 280 px.
- Buttons: primary = filled blue, secondary = outline. Minimum touch target 40 px.

**Iconography and states**
- Material icons for navigation and buttons (`:material/...:`). No emoji in app chrome. Emoji only inside content the user writes.
- Every list/page has an **empty state** with one clear action, and a **loading** and **error** state.

**Implementation plan:** `.streamlit/config.toml` (theme: font, base font size, colours, radius, sidebar) + `ui/theme.py` (tokens) + `ui/base.css` (small). Verify supported theme options against the user's installed Streamlit version (`pip show streamlit`) at Step 3.1. Show the user a rendered preview of the type scale and palette before applying it.

---

## 5B. Media & storage policy

**What happens today (the `downloades/` problem):**
- YouTube: `download_youtube_audio()` saves `downloades/<id>.wav`. yt-dlp's WAV extraction keeps the source sample rate and channels, which is typically 44.1/48 kHz stereo (roughly 10+ MB per minute).
- `chunk_audio()` then writes a full second copy as `<id>.wav_chunk_N.wav` (10-minute pieces).
- Local upload: `<name>_converted.wav` is written next to the original.
- **Nothing is ever deleted.** A 1-hour video can leave roughly 1.4 GB behind.
- Video itself is not stored. Frame grabs stream from YouTube via yt-dlp + ffmpeg on demand. For local files, frame grabs need the original file path to still exist.

**Policy (D-15):**

| Item | Where | Lifetime |
|---|---|---|
| Downloaded audio, converted WAV, chunk files | `data/media/tmp/<job_id>/` | Deleted in a `finally` block when the job ends (success or failure) |
| Audio format | 16 kHz mono, right after download | (about 1.9 MB/min; Whisper uses 16 kHz mono anyway) |
| YouTube video | not stored | frames fetched on demand from the stream |
| Uploaded original | `data/media/uploads/<user_id>/<video_id>/` | Kept so frame grabs work; deleted with the video; admin can purge (Phase 5) |
| Frame images | `data/media/frames/<video_id>/` | Deleted with the video |
| Vector index | `data/chroma/<video_id>/` | Deleted with the video |

**Check on your machine:** `du -sh downloades vector_db data/frames` (the setup script prints this).

---

## 6. Known issues (from analysis)

| ID | Issue | Fixed in | Status |
|---|---|---|---|
| I-01 | JSON files used as DB: capped (50 history / 30 sessions), no IDs linking history↔sessions↔vectors, full rewrite on save, no locking | 1.4–1.5 | [ ] |
| I-02 | Quiz answers/scores exist only in `st.session_state`, never saved | 4.3 | [ ] |
| I-03 | `render_dashboard()` is one ~770-line function with business logic inside | 1.6, 3.x | [ ] |
| I-04 | Prompts are meeting-oriented; data is ~50% Education | 4.1 | [ ] |
| I-05 | Vector store wipes all folders in `vector_db/` on every build (breaks multi-user) | 1.7 | [ ] |
| I-06 | `styles.py` is 999 lines, 205 `!important`, Streamlit-internal selectors | 3.1, 3.10 | [ ] |
| I-07 | `get_llm()` copied 5×; `invoke_with_retry` lived in `extractor.py`; log message said "Mistral" | 1.1 | [x] `core/llm.py` created: single `get_llm(temperature=...)` (defaults preserved: extractor 0.2, summarizer/RAG/notes 0.3, quiz 0.4) + `invoke_with_retry` (now also honours a `retry-after` header when the API sends one, capped at 60s). All 5 files import from it. Wording fixed to "Groq". Model/key now come from `config.settings` instead of a fresh `os.getenv()` per file. |
| I-08 | 7 `time.sleep` calls in the pipeline = 6.5s artificial delay | 1.2 | [x] Removed from `main.py`'s `run_pipeline`. **Not removed:** the separate `time.sleep(0.8)` pacing calls between map-reduce chunk calls in `extractor.py`/`summarizer.py` — those exist to avoid tripping Groq's rate limit on long transcripts, not to pad the UI, so they're out of scope for I-08 and were left alone (tried removing them, put them back — see session log). |
| I-09 | No `requirements.txt`, `.gitignore`, `.env.example`, README | 0.2–0.4, 6.6 | [~] `requirements.txt` and `.gitignore` were actually present in the project already (correct content). `.env.example` was **not** present despite the previous revision of this file claiming it was delivered — created now. README still open, 6.6. |
| I-10 | Docs vs code drift: Mistral (diagram + landing page) vs Groq; `MISTRAL_API_KEY` unused; "VideoMind AI" vs "AI Video Assistant" | 1.1, 3.10, 6.6 | [~] Code-level Mistral wording fixed (I-07). Sidebar brand fixed to "AI Video Assistant" (was "VideoMind AI" in `ui/sidebar.py`, navbar already said the right thing). Diagram/landing page copy not audited yet — that's 3.10/6.6. |
| I-11 | `downloades/` typo dir; downloaded WAVs and chunks never cleaned | 1.9 | [ ] |
| I-12 | Hidden coupling: `chunk_minutes` must match between `chunk_audio()` and `transcribe_all_with_segments()` | 1.9 | [ ] |
| I-13 | Passwords hashed with plain salted SHA-256 | 2.1 | [ ] |
| I-14 | Dynamic text injected into `unsafe_allow_html` unescaped (26 places in dashboard) | 2.4 | [ ] |
| I-15 | Local file-path input can't work in a hosted deployment | 3.5 | [ ] |
| I-16 | Login lost on browser refresh (state only in `st.session_state`) | 2.3 | [ ] |
| I-17 | `.env` with real API keys was included in a shared zip | 0.1 | [ ] still needs the user to actually rotate the keys |
| I-18 | Legacy user record `ayesha3416` has no `display_name` and isn't an email | 1.5 | [ ] |
| I-19 | `print()` used instead of logging | 1.3 | [~] All library-code `print()`s converted to `log.info/warning/error` (`transcriber.py`, `frame_extractor.py`, `vector_store.py`, `utils/audio_processor.py`, `extractor.py`'s `classify_category`). Deliberately **left as `print`**: `main.py`'s `if __name__ == "__main__"` CLI block (that's real CLI output, not debug logging) and `vector_store.py`'s own `if __name__ == "__main__"` demo block. |
| I-20 | Full transcript duplicated inside every saved chat session | 1.5 | [ ] |
| I-21 | Pipeline errors shown only in a UI status box, then lost | 1.8 | [ ] |
| I-22 | YouTube audio is saved as full-rate stereo WAV and duplicated again as chunks (about 1.4 GB per hour, never deleted) | 1.9 | [ ] |
| I-23 | `*Zone.Identifier` junk files (Windows→WSL copy artefacts) throughout the project | 0.5 (script) | [x] Working copy is clean (stripped before the git baseline). `phase0_setup.sh` doesn't delete them from your real checkout automatically — do `find . -name '*Zone.Identifier' -delete` once, then re-run the script. |
| I-24 | Frame grabs on local files depend on the original path still existing | 1.9, 3.5 | [ ] |
| I-25 | UI has 35 font sizes, 27 colours, 3 font families, no theme config | 3.1 | [ ] |
| I-26 | Old `requirements.txt` was from the earlier "AI Meeting Assistant" (Mistral + deep-translator) era. It was **missing** what the code imports (`langchain-groq`, `langchain-chroma`, `langchain-text-splitters`, `plotly`, `pandas`) and **listed 9 unused** packages (`mistralai`, `langchain-mistralai`, `deep-translator`, `langchain`, `langchain-community`, `reportlab`, `streamlit-extras`, `ffmpeg-python`, `torchaudio`). A fresh install from it would not run the app. | 0.4 | [x] Corrected file is already the one in the project (verified: matches every real import in the codebase, includes `bcrypt`/`itsdangerous` for Phase 2, `streamlit-cookies-controller`). |
| I-27 | `phase0_setup.sh`'s own data backup (`_backup/data_<timestamp>/…`, includes real chat transcripts and frame images) was **not** excluded by `.gitignore` — the `.gitignore` comment claimed `_backup/` was ignored but the actual entry was missing, so running the script would commit a full copy of user data (and a new copy on every re-run) straight into git history. | 0.2, 0.5 | [x] Added `_backup/` to `.gitignore`; re-tested `phase0_setup.sh` twice (fresh run + idempotent re-run) — confirmed 0 files under `_backup/` get committed now. |
| I-28 | `ui/sidebar.py`'s delete-chat confirmation (`@st.dialog`) is opened by checking `st.session_state.confirm_delete_id`, but that flag is only cleared by the Cancel/Delete buttons inside the dialog. Closing the dialog with the native ✕ (or pressing Escape) leaves the flag set, so the same confirmation pops back up on the next unrelated rerun. | not scheduled — flagging for a Phase 1/3 UI pass | [ ] newly found, not fixed (Phase 1/2 is "no behavior change"; this is a real bug but fixing it changes visible behavior, so it's queued rather than fixed silently) |
| I-29 | `render_dashboard()` has a dead `elif nav == "Results":` branch (~90 lines) — the sidebar only ever sets `dash_nav` to `"Chat"`, `"Stats"`, or `"History"`, so "Results" can never be reached by clicking anything in the current UI. The Results *content* (summary/action items/decisions/questions/transcript tabs) has no way to be opened at all right now except by direct `st.session_state.dash_nav = "Results"` manipulation, which nothing in the UI does. | 1.6, 3.7 (folds into Video detail) | [ ] newly found, not fixed — flagging rather than deleting since Phase 1/2 must not change behavior, and since the Video-detail tabs planned for 3.7 are meant to absorb this exact content |
| I-30 | **Confirmed on the user's real machine, not hypothetical:** running `phase0_setup.sh` for real committed `.env.backup`, `.env.backup-messy`, `.env.broken-backup`, and a pre-existing `.backup-step1/` folder (containing old copies of `app.py`, `main.py`, `Requirements.txt`) straight into the `baseline-v0` commit. `.gitignore` only excluded `.env` exactly, not `.env.*` variants, and had no rule for `.backup-step1/` at all — a gap this session's own testing (in a sandbox with none of these files present) couldn't have caught. Also spotted in the same commit: a stray duplicate `Requirements.txt` (capital R) alongside `requirements.txt`, and two files not part of the zip this chat originally analyzed (`.streamlit/config.toml`, `pytest.ini`) — the real project directory has diverged from what was reviewed here. | 0.2, 0.5 | [x] `.gitignore` changed from `.env` / `.env.local` to `.env` / `.env.*` / `!.env.example`, plus a `.backup-step1/` rule. `phase0_setup.sh` also hardened with a second, independent guard: it now inspects everything actually staged for commit and refuses (before committing) if anything matching `.env.*` (other than `.env.example`) slipped through — tested this catches the exact `.env.backup*` files above even against the *old*, buggy `.gitignore`, so a future gitignore gap can't silently repeat this. **User's local repo still has the secrets in its one existing commit** (nothing pushed anywhere — confirmed with the user) — since it's just a local `root-commit`, remediation is delete `.git` and redo, not history rewriting; see the delivery note. `Requirements.txt` duplicate and the two files outside the reviewed zip are flagged for the user to check, not touched. |

---

## 7. Data model (SQLite via SQLAlchemy)

```
users            id, email(unique), display_name, password_hash, hash_algo, role[user|admin],
                 is_active, created_at, last_login_at
videos           id, user_id, source, source_type[youtube|upload], title, category, language,
                 mode[study|meeting|general], duration_sec, status, created_at
analyses         video_id(PK/FK), transcript, segments_json, summary, action_items,
                 key_decisions, open_questions
chat_sessions    id, user_id, video_id(nullable), title, created_at, updated_at
chat_messages    id, session_id, role, type[text|image|quiz|notes|...], content_json, created_at
notes            id, video_id, content_json, created_at
quizzes          id, video_id, questions_json(each question has a topic tag), created_at
quiz_attempts    id, quiz_id, user_id, score, total, answers_json, per_topic_json, taken_at
topics           id, video_id, name, difficulty, est_minutes, start_sec
topic_mastery    user_id, topic_id, score, interval_days, next_review_at
study_goals      id, user_id, title, deadline, hours_per_day, status, created_at
plan_items       id, goal_id, topic_id, video_id, item_type[watch|revise|quiz|review],
                 due_date, minutes, status, completed_at
jobs             id, user_id, video_id, stage, status, error, started_at, finished_at, duration_ms
usage_events     id, user_id, provider, operation, latency_ms, status, tokens_in, tokens_out, created_at
audit_log        id, actor_id, action, target, created_at
```

---

## 8. Roadmap and checklist

### Phase 0 — Baseline & safety
- [ ] 0.1 **(You)** Rotate the Groq, Sarvam and Mistral API keys that were in the shared zip *(I-17)* — still open, please do this
- [x] 0.2 `.gitignore`: was already correct in the project except missing `_backup/` (I-27) — fixed. Also ignores `*Zone.Identifier`
- [x] 0.3 `.env.example`: was described as delivered in the previous revision but wasn't actually in the zip — created now (placeholders + `ADMIN_EMAILS`; a commented-out `MISTRAL_API_KEY` note explains it's unused)
- [x] 0.4 `requirements.txt`: the file in the project root is already the corrected one (matches every real import; drops the 9 unused packages; `ffmpeg` noted as a system dependency). No change needed.
- [ ] 0.5 **(You)** `git init` + baseline commit tagged `baseline-v0`: `phase0_setup.sh` does this — **run it in your real project directory**, not just here (I ran and tested it in this sandbox, but that git history doesn't leave the sandbox)
- [x] 0.8 `check_env.py`: was described as delivered previously but wasn't in the zip — created now, and smoke-tested here (with stubbed packages, since this sandbox doesn't have your dependencies installed). Reports missing packages, Streamlit version, ffmpeg/ffprobe, and whether `.env` keys are set (never prints values). `--deep` also imports each package.
- [ ] 0.6 `SMOKE_TEST.md`: **the user already has their own** (16 checks incl. hinglish, local file, recent chats, log out/in) — kept as-is, not overwritten by this session's version. **(You)** run it against the code as it now stands and record the result — needs a real browser + real API keys, which this sandbox doesn't have.
- [ ] 0.7 **(You)** Back up `data/`: `phase0_setup.sh` does this into `_backup/data_<date>/` — same as 0.5, run it in your real directory

### Phase 1 — Foundation (no visible change)
- [x] 1.1 `core/llm.py`: single `get_llm()` + `invoke_with_retry`; fixed "Mistral" wording; updated all 5 importers (`extractor`, `summarizer`, `rag_engine`, `quiz_generator`, `notes_generator`). Bonus while in there: `rag_engine.get_retriever` now uses `settings.retriever_k` instead of a hardcoded `6`; `core/transcriber.py`'s module-level `WHISPER_MODEL`/`SARVAM_API_KEY`/`SARVAM_STT_MODEL` now come from `config.settings` instead of their own `os.getenv()` calls; `core/vector_store.py`'s `CHROMA_ROOT`/`EMBEDDING_MODEL`, `core/frame_extractor.py`'s `FRAMES_DIR`, `utils/audio_processor.py`'s `DOWNLOAD_DIR`, and `auth/auth_manager.py` / `utils/history_manager.py` / `utils/chat_sessions.py`'s JSON file paths now all resolve through `config/paths.py` (which already existed for exactly this) instead of bare relative strings — this is the actual fix for "the app only works if you launch it from the project root" that `config/paths.py`'s own docstring describes; before this change, several modules still had their own relative-path copies alongside it.
- [x] 1.2 Removed the 7 UX-delay `time.sleep` calls from `main.py`'s `run_pipeline` (I-08). Left the unrelated rate-limit-pacing sleeps in `extractor.py`/`summarizer.py` alone (see I-08 note) — those aren't the ones the roadmap step or SMOKE_TEST timing are about.
- [x] 1.3 Structured logging (`config/logging_config.py`) already existed from a previous session. What was still missing: the library-code `print()` calls hadn't actually been converted yet. Done now (I-19).
- [ ] 1.4 `db/`: SQLAlchemy models, session, repositories — not started. This is the next substantial piece of work; it touches every JSON-backed module (`auth_manager`, `history_manager`, `chat_sessions`) and is big enough to want its own session rather than being rushed in alongside 1.1–1.3.
- [ ] 1.5 `scripts/migrate_json_to_sqlite.py`: users (incl. legacy record), history↔sessions linking, de-duplicate transcripts
- [ ] 1.6 `services/`: extract pipeline, chat, quiz, notes, auth, analytics out of `dashboard.py` / `main.py`
- [ ] 1.7 Vector store: per-video persistent collection, remove global wipe, rebuild-on-demand — **not done yet, but flagged as high priority**: `core/vector_store.py`'s `_cleanup_old_stores()` deletes every folder under `vector_db/` on every single analysis (I-05). With only one user so far this hasn't bitten, but it means concurrent analyses (two tabs, or two users) can delete each other's in-progress vector store mid-build. Worth pulling forward ahead of 1.4–1.6 if you expect concurrent use before the DB migration lands.
- [ ] 1.8 Log every pipeline run to `jobs` and every provider call to `usage_events`
- [ ] 1.9 Media hygiene per section 5B: per-job temp dir deleted in `finally`, 16 kHz mono conversion for YouTube audio, uploads kept under `data/media/uploads/`, frames under `data/media/frames/`, chunker returns offsets (removes `chunk_minutes` coupling)
- [ ] 1.10 Run the smoke test; confirm behavior parity — blocked on you running `SMOKE_TEST.md` for real (0.6)

### Phase 2 — Auth hardening
- [ ] 2.1 argon2 hashing + rehash-on-login for legacy SHA-256 users
- [ ] 2.2 Roles + `is_active`; `ADMIN_EMAIL` bootstrap
- [ ] 2.3 Persistent login (signed cookie) + logout invalidation
- [ ] 2.4 HTML-escape helper applied to all dynamic `unsafe_allow_html` content
- [ ] 2.5 Password change + basic login-attempt throttling

### Phase 3 — UI restructure and sections
- [ ] 3.1 Design system per section 5A: show a type-scale/palette preview first, then `.streamlit/config.toml`, `ui/theme.py`, small `base.css`
- [ ] 3.2 `app.py` with `st.navigation`; `views/` skeleton with auth gate
- [ ] 3.3 Components: sidebar, navbar, stat_card, chat_bubble, quiz_widget, notes_view, video_card, empty_state
- [ ] 3.4 **Home** section (continue, recent, quick stats; "Today" slot filled in Phase 4)
- [ ] 3.5 **Analyze** section (URL + file uploader, language, mode, live progress)
- [ ] 3.6 **Chat** section (intent routing via `chat_service`)
- [ ] 3.7 **Library** + **Video detail** (tabs by mode; quiz/notes/export here too)
- [ ] 3.8 **Progress** section (from Stats)
- [ ] 3.9 **Settings** section
- [ ] 3.10 Restyle public pages; delete old `dashboard.py` / `sidebar.py` / `styles.py`; unify the product name

### Phase 4 — Study features (inside the same dashboard)
- [ ] 4.1 Modes (Study / Meeting / General) with prompts in `core/prompts/`
- [ ] 4.2 Topic extraction → `topics` table (difficulty, est. minutes, start time from segments)
- [ ] 4.3 Persist quizzes and attempts; topic-tagged questions; per-topic results
- [ ] 4.4 Mastery + spaced repetition in `planner_service` (unit-tested)
- [ ] 4.5 **Study Plan** section: goals, schedule generation, check-off, replan
- [ ] 4.6 Wire into Home ("Today", "Reviews due") and Progress (mastery, quiz trend, streak)

### Phase 5 — Admin dashboard
- [ ] 5.1 Admin guard (nav-level and per-view role check)
- [ ] 5.2 Overview
- [ ] 5.3 Users
- [ ] 5.4 Jobs (with error detail and retry)
- [ ] 5.5 Usage & Cost
- [ ] 5.6 Storage + cleanup actions
- [ ] 5.7 Audit log

### Phase 6 — Production readiness
- [ ] 6.1 Background job worker (DB-backed queue; UI polls)
- [ ] 6.2 Upload validation (size/type/duration) + per-user daily quota
- [ ] 6.3 Two-user concurrency check
- [ ] 6.4 pytest for services (auth, scheduler, quiz grading, chunk offsets, migration)
- [ ] 6.5 Dockerfile + compose (ffmpeg, volumes, healthcheck)
- [ ] 6.6 README + updated architecture diagram (Groq, Sarvam, SQLite, Admin)
- [ ] 6.7 *(Optional)* Groq Whisper backend; Postgres switch

---

## 9. Current codebase snapshot (updated 2026-09-22, after Phase 1 steps 1.1–1.3)

```
app.py                40   router via st.session_state.page
main.py               ~85  run_pipeline() (no artificial sleeps) + CLI
auth/auth_manager.py  ~75  JSON users, salted SHA-256; path via config/paths.py
core/                 llm.py 84 (NEW — single get_llm/invoke_with_retry)
                      extractor ~145 · frame_extractor ~110 · notes_generator ~120
                      quiz_generator ~80 · rag_engine ~90 · summarizer ~65
                      transcriber ~250 · vector_store ~165
utils/                audio_processor ~125 · chat_sessions 128 · history_manager 83
ui/                   dashboard 1080 (unchanged) · styles 999 (unchanged)
                      home_page 145 · sidebar 139 (brand text fixed)
                      auth_pages 80 · navbar 59
config/               __init__.py 43 · paths.py 65 · settings.py 128 · logging_config.py 93
                      (all pre-existing from a previous session; now actually
                      wired into every module that used to bypass them)
data/                 users.json · history.json · chat_sessions.json · frames/
vector_db/            Chroma stores (still wiped on each new analysis — I-05, not fixed yet)
Phase 0 files          .gitignore · requirements.txt · requirements-dev.txt ·
                      .env.example (NEW) · check_env.py (NEW) · phase0_setup.sh (NEW)
                      SMOKE_TEST.md — user's own, kept as-is
```

Observed data: ~half of one user's 24 analyses are Education (React tutorials etc.), which is the case for the study features. Chat sessions contain text, image (frames), quiz and notes message types. All 14 saved frame-image messages checked; the referenced JPEGs all still exist on disk. No local (non-YouTube) sources found in the saved history, so I-24/I-15 haven't bitten this user's real data yet, but remain real risks for the next local upload.

---

## 10. Session log

| Date | Step | Summary |
|---|---|---|
| 2026-09-21 | Discovery | Analyzed full project (all `.py`, data shapes). Logged issues I-01…I-21. |
| 2026-09-21 | Decisions | Locked D-01…D-14. Study planner becomes a section of the existing dashboard. Admin dashboard added as role-gated views. Created this file. |
| 2026-09-21 | Requirements fixed | User showed their existing `requirements.txt`. Compared to real imports: 5 missing, 9 unused (I-26). Delivered a corrected `requirements.txt` and `check_env.py` (tested; runs and reports correctly). |
| 2026-09-21 | Phase 0 prepared | Confirmed the plan's backend is the services + DB + core layers (no separate server needed). Found the `downloades/` growth cause (I-22) and wrote the media policy (D-15, 5B). Audited UI and locked the design system (D-16, 5A). Session claimed `phase0/` files (`.gitignore`, `.env.example`, `requirements.txt`, `SMOKE_TEST.md`, `phase0_setup.sh`) were created — see next entry, this wasn't actually true of the delivered zip. |
| 2026-09-22 | Zip re-analyzed; Phase 0 gap found and closed | The uploaded zip did **not** contain `.env.example`, `check_env.py`, `SMOKE_TEST.md`, or `phase0_setup.sh` — only `.gitignore` and `requirements.txt`/`requirements-dev.txt` had actually made it in (both already correct). Recreated `.env.example`, `check_env.py`, `phase0_setup.sh`; the user separately uploaded their own `SMOKE_TEST.md` (16 checks, different from the one drafted in this session) — kept theirs, discarded the drafted one. Compiled and ran the project's `tests/test_config.py` (28 tests, all pass) via a local pytest-compatible shim (this sandbox has no network, so `pytest` and the app's real dependencies aren't installed — see "How this was verified" in the header). Reviewed every `.py` file; confirmed against the actual saved user data (`data/*.json`, `vector_db/`, `data/frames/`) that the 14 saved frame images all still resolve, no local-file sources are in the history, and one legacy account (`ayesha3416`, matches I-18) exists alongside two email-keyed accounts. |
| 2026-09-22 | User ran check_env.py + phase0_setup.sh for real (I-30) | `check_env.py` passed cleanly on the user's machine (Python 3.14.4, Streamlit 1.61.1, all packages/ffmpeg/env-keys OK). `phase0_setup.sh` ran but its commit output showed `.env.backup`, `.env.backup-messy`, `.env.broken-backup`, and a `.backup-step1/` folder (old `app.py`/`main.py`/`Requirements.txt` copies) all got committed into `baseline-v0` — `.gitignore` only excluded `.env` exactly. User confirmed nothing has been pushed anywhere yet, so remediation is delete-and-redo rather than history rewriting. Fixed `.gitignore` (`.env` / `.env.*` / `!.env.example`, plus `.backup-step1/`) and hardened `phase0_setup.sh` with a second, independent guard that inspects staged files before committing regardless of what `.gitignore` says — tested both the failure case (old gitignore, confirms the guard alone would have caught it) and the clean path (new gitignore + hardened script, confirms a clean commit and idempotent re-run). Also noted for the user to check, not touched: a stray duplicate `Requirements.txt`, and `.streamlit/config.toml` / `pytest.ini` existing in the real project but not in the zip this chat originally analyzed. |
| 2026-09-22 | Phase 1, steps 1.1–1.3 | Created `core/llm.py` (single `get_llm`/`invoke_with_retry`, now also respects a `retry-after` header); updated all 5 importers. Removed `main.py`'s 7 artificial `time.sleep` calls (I-08); deliberately kept the separate rate-limit-pacing sleeps inside `extractor.py`/`summarizer.py`'s chunk loops after first removing them by mistake and then restoring them on review — see the I-08 issue note for why those are different. Converted remaining library-code `print()`s to `log.*` (I-19), leaving the two legitimate CLI/demo `print` blocks alone. Wired `core/transcriber.py`, `core/vector_store.py`, `core/frame_extractor.py`, `utils/audio_processor.py`, `auth/auth_manager.py`, `utils/history_manager.py`, and `utils/chat_sessions.py` through the pre-existing `config/paths.py` and `config/settings.py` instead of their own hardcoded relative paths / `os.getenv()` calls — this is the actual fix for the cwd-dependence problem `config/paths.py`'s docstring already described as solved. Fixed the stale "VideoMind AI" sidebar brand text (I-10). Found and fixed a real bug in `phase0_setup.sh`: its own `_backup/` output wasn't excluded by `.gitignore` despite the gitignore's comment claiming it was (I-27) — would have committed real chat transcripts into git history on first run. Found two new dead-code/UX issues while reading `ui/dashboard.py` and `ui/sidebar.py` closely: an unreachable `"Results"` nav branch (I-29) and a delete-chat confirmation dialog that can reopen itself after being dismissed with ✕ instead of Cancel/Delete (I-28) — both logged, neither fixed, since Phase 1/2 is "no behavior change" and both are visible-behavior fixes that belong in the Phase 3 UI pass. All existing tests still pass; full tree still compiles. |

---

## 11. Open items / notes for next session
- **Immediate next action (I-30 remediation), in this exact order:**
  ```bash
  cd ~/projects/ai-video-assistant
  rm -rf .git                     # safe: confirmed with user, nothing pushed anywhere
  unzip -o step1-fix-gitignore-and-setup-script.zip
  bash phase0_setup.sh
  git show --stat baseline-v0     # confirm no .env*/.backup-step1 files appear
  ```
- After that: rotate keys (0.1, still open — the *original* `.env` leaked by being included in the zip shared in this chat, separate from I-30); check whether `Requirements.txt` (capital R) is a stray duplicate of `requirements.txt` and delete it if so (`diff Requirements.txt requirements.txt` first); share `.streamlit/config.toml` and `pytest.ini` so this file can account for them (they exist in the real project but weren't part of the zip originally analyzed here); run their `SMOKE_TEST.md` against the code as it now stands; report results.
- **Delivery note:** changes are shipped as small zips mirroring the project's folder structure (only new/changed files, never the whole project), applied with:
  ```bash
  cd ~/projects/ai-video-assistant
  unzip -o <name-of-the-zip>.zip
  ```
  `-o` overwrites existing files without prompting. Since `.venv/` and `data/` are never in these zips, this is safe to run with the venv active. After unzipping, `git status` (once `phase0_setup.sh` has run) will show exactly what changed.
- User to report: output of `python check_env.py` (Streamlit version matters for the Phase 3 theme options), and `pip show streamlit`.
- Ask which shell the user works in. Scripts assume bash (WSL/Linux/macOS/Git Bash). If they use plain Windows PowerShell, provide equivalents.
- User to report the output of `du -sh downloades` (real size of the leftover-media problem) — from this session's actual data: `vector_db` is 492K, `data/frames` is 5.6M, `downloades` was empty (4K) at analysis time.
- Assumptions A-01…A-03 and product name (D-05) still open to veto.
- I-05 (vector store global wipe) and I-27/I-28/I-29 (this session's new findings) are all real, verified issues sitting unfixed — see section 6 for exact status and reasoning on each.
- Next actual coding step once the user reports back: Step 1.4 (SQLAlchemy models + `db/`), unless the user wants I-05 (vector store wipe) pulled forward first since it's a one-file fix with real multi-user risk.
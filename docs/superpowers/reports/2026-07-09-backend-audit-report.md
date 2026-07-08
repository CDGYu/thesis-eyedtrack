# EyedTrack Backend Audit — Findings Report

**Date:** 2026-07-09 · **Branch:** `feat/uiux-overhaul-signal` · **Spec:** [`../specs/2026-07-09-backend-audit-design.md`](../specs/2026-07-09-backend-audit-design.md)
**Method:** Live end-to-end audit against the running Flask backend (`0.0.0.0:5000`) + real MySQL 8.0 (`eyedtrack_db`) on this machine — not static-only.

## Verdict at a glance

| Workstream | Result |
|---|---|
| **A · Algorithms** | ✅ All algorithms correctly utilized in the live path. No correctness bugs. |
| **B · API endpoints** | ✅ Every route live-tested → 200 + shapes the Android app parses. One minor error-handling note. |
| **C · Database** | ✅ Repaired (credential blocker) and now persists end-to-end. Schema sound. 2 of 4 tables have **no production writer** (documented, in-scope-to-report). |
| **Unused artifacts** | ✅ `mmod_human_face_detector.dat` removed (0 references; was `*.dat`-gitignored, disk-only). |

**One thing was actually broken — the MySQL credential — and it is fixed.** Everything else in Workstream C is an accurate-state finding, not a defect; per the approved scope (no schema redesign, no new ML) those are reported with recommendations rather than changed.

---

## Workstream A — Algorithms (verified correct)

Live path traced and confirmed each stage is invoked:

```
/api/process_frame → base64→cv2 → OptimizedFrameProcessor.process_frame
  → preprocess_frame (CLAHE on LAB L-channel)          ← APPLIED per frame
  → ImprovedFaceAnalyzer.analyze_frame
      → _oriented_face() (rotation-robust dlib HOG detect, upsample=1)
      → 68 landmarks → EAR (both eyes, averaged) / MAR / solvePnP head-pose
  → behavior_category (is_drowsy / is_yawning / is_distracted)
  → temporal counters (drowsy=6, yawn=2, distraction=5 consecutive frames)
  → response {behaviors[], metrics{ear,mar,head_pose}}
```

- **CLAHE is genuinely used** — built in `__init__`, applied every frame in `frame_processor.preprocess_frame` (LAB L-channel). Not dead.
- **Thresholds live in the analyzer:** EAR = 0.27, MAR = 0.6, Yaw = ±35°, Pitch = ±25°; temporal frames drowsy=6 / yawn=2 / distraction=5. Confirmed at startup and honored.
- **Orientation-robust detection** (`_oriented_face`) resolved the on-device "no face" issue (phone frames arrived rotated). Detection went 0% → 100%; DROWSY fired at EAR 0.12–0.22 < 0.27.

**Minor findings (no action needed):**
- `frame_processor` carries its *own* ear/mar/yaw/pitch threshold fields that are **dead** — detection uses the analyzer's values. Cosmetic; harmless.
- `head_pose` roll is hardcoded `0.0` (only yaw/pitch computed). Distraction uses yaw/pitch, so this doesn't affect behavior.
- Unused CNN detector `mmod_human_face_detector.dat` had zero references → removed.

---

## Workstream B — API endpoints (live end-to-end)

All routes exercised against the running server this session:

| Route | Method | Result | Notes |
|---|---|---|---|
| `/api/health` | GET | **200** | `{status: healthy, ...}` |
| `/api/process_frame` | POST | **200** | Valid frame → `{behaviors[], metrics{ear,mar,head_pose}, success}`. No-face → `behaviors:[]`, ear/mar 0, head_pose null. |
| `/api/latest_behavior` | GET | **200** | File-backed last behavior + `entry_age_seconds`. |
| `/api/alert_history` | GET | **200** | File-backed `alerts[]` with `behavior_category` / `behavior_confidence` — the shape the Android app parses. |
| `/api/clear_alert_history` | POST | **200** | (verified earlier) clears the file log. |
| `/process_frame` | POST | **redirect** | back-compat → `/api/process_frame`. |
| `/api/db/health` | GET | **200** | `database_enabled: true` once MySQL attached (was 503 in file-mode). |
| `/api/db/behaviors/recent` | GET | **200** | MySQL-backed `behaviors[]`. |
| `/api/db/dashboard/summary` | GET | **200** | MySQL-backed averages + incident breakdown. |
| `/api/db/session/summary`, `/api/db/cleanup` | GET/POST | **200 / 503** | Live when DB attached; graceful 503 when disabled. |

**Minor finding (recommend, not fixed):** an **undecodable** frame returns **HTTP 500** with a full stack trace in the JSON body (`{"error":..., "traceback":...}`). Bad client input should be **400**, and the traceback should not be exposed in responses (info-leak; not production-safe). The valid-frame and no-face paths are correct — this only affects malformed input.

---

## Workstream C — Database (repaired + assessed) — *thoroughness detail*

### C.1 The blocker (BROKEN → FIXED)

MySQL persistence was silently disabled because `eyedtrack_app` could not authenticate. Root cause: the user pre-existed, so `CREATE USER IF NOT EXISTS` **skipped** setting the password. Fixed by forcing it as root:

```sql
ALTER USER 'eyedtrack_app'@'localhost' IDENTIFIED BY '<db-password>';
GRANT ALL PRIVILEGES ON eyedtrack_db.* TO 'eyedtrack_app'@'localhost';
FLUSH PRIVILEGES;
```

After the fix the backend logs `✅ MySQL persistence enabled` and `/api/db/health` returns `database_enabled: true`.

> **Run requirement:** the password is intentionally **not** stored in `config.yaml` (`password: ""`). Start the backend with the env var:
> ```bash
> EYEDTRACK_DB_PASSWORD=<db-password> python main.py
> ```
> Without it, the server still runs but falls back to **file-only** logging (the app keeps working via `/api/alert_history`).

### C.2 Schema (assessed — sound)

Auto-created by `Base.metadata.create_all` on connect. All **InnoDB**, `utf8mb4_unicode_ci`.

**`monitoring_sessions`** — `id` PK auto_inc · `session_id` varchar(50) **UNIQUE** · `start_time` · `end_time` (nullable) · `status` · `device_info` JSON
**`driver_behaviors`** — `id` PK · `session_id` FK · `timestamp` · `behavior` · `confidence` · `is_risky` · `ear` · `mar` · `head_pose` JSON · `additional_metrics` JSON
**`alert_logs`** — `id` PK · `session_id` FK · `timestamp` · `alert_type` · `severity` · `message` · `acknowledged` · `acknowledgment_time`
**`performance_metrics`** — `id` PK · `session_id` FK · `timestamp` · `fps` · `processing_time` · `memory_usage` · `cpu_usage` · `gpu_usage` · `additional_metrics` JSON

- **Foreign keys:** all three child tables → `monitoring_sessions.session_id` (`*_ibfk_1`). Referential integrity is in place.
- **Indexes:** PK on `id` + a secondary index on `session_id` for every table.
- **Soundness:** good normalization, correct types (JSON for structured fields), FKs present. Minor efficiency notes: FKs target a `varchar` UNIQUE key rather than the int PK; `timestamp` is unindexed while `get_recent_behaviors` filters on it (fine at current scale); `session_id` is minute/second-granular with a UNIQUE constraint, so two inits in the same second would collide (see C.4).

### C.3 Write-path audit (the key question the spec asked)

| Table | Written by | When | Status |
|---|---|---|---|
| `driver_behaviors` | `db_manager.log_behavior` @ `main.py:549` | On behavior **onset** (edge-triggered) when DB enabled | ✅ **used** |
| `monitoring_sessions` | `create_monitoring_session` @ `main.py:184` | At `initialize_system()` | ⚠️ used, but see C.4 |
| `alert_logs` | `log_alert` via `_persist_onsets` @ `main.py` | On behavior **onset** (with the behavior row) | ✅ **used** (wired 2026-07-09; 0 callers at audit) |
| `performance_metrics` | `log_performance_metrics` via `_sample_performance` @ `main.py` | Every ~30 processed frames (sampled) | ✅ **used** (wired 2026-07-09; 0 callers at audit) |

`end_monitoring_session` was also **0 callers** at audit (sessions never closed); **wired 2026-07-09** via an `atexit` shutdown hook (best-effort — not on a forced kill).

**All four tables are structurally writable** — verified against live MySQL. At audit `alert_logs` / `performance_metrics` were unused (not broken); **both are now wired** (see Recommendations), so all four tables fill in normal operation.

### C.4 Read-path audit

- `/api/db/*` consume `get_recent_behaviors`, `get_session_summary`, `cleanup_old_data` — all functional.
- **The Android app does not read MySQL** — it reads the file-backed `/api/alert_history`. So MySQL is effectively **write-only from the app's perspective** (a parallel store, dual-write but not dual-read).
- **Duplicate session per launch:** with Flask `debug=True`, the werkzeug reloader runs `initialize_system()` twice (parent + child) → **2 `monitoring_sessions` rows per launch**; only the child serves requests, leaving an orphan session each time. Combined with C.3 (never closed), sessions accumulate as `active`.

### C.5 End-to-end persistence — VERIFIED

Drove the **real production code** (`config_loader.load_config` → `DatabaseManager` → `main._db_behavior_rows` → `log_behavior`) against live MySQL with a representative drowsy result:

```
NEW_SESSION session_20260708_180334
MAPPED_ROWS [{"behavior":"drowsy","confidence":0.9,"is_risky":true,"ear":0.14,"mar":0.28,
             "head_pose":{"yaw":6.0,"pitch":-4.0,"roll":0.0},"additional_metrics":{...}}]
→ driver_behaviors row persisted (ear/mar/head_pose JSON correct) and read back via get_recent_behaviors ✅
```

(The detection→behavior half was separately **device-verified**: EAR 0.12–0.22 < 0.27 fired DROWSY on-device. The Flask route shape is verified in Workstream B. This closes the last link: result → persisted row.) Synthetic audit rows were then cleaned up.

### C.6 DB thoroughness — bottom line

The persistence layer is **functional and structurally sound**. The coverage gaps found at audit — `alert_logs` / `performance_metrics` unwritten and sessions never closed — were **fixed on this branch (2026-07-09)**, so all 4 tables now fill. Remaining items are optional (the app still reads file-based history, and the `debug` reloader still double-creates sessions). See Recommendations.

---

## Recommendations

**Applied on this branch (2026-07-09):**
- ✅ **Error handling** — `/api/process_frame` now returns **400** for missing / malformed-JSON / undecodable frames and **no longer leaks `traceback`** (or the raw request body) in responses; genuine faults log the traceback server-side and return a generic 500. (`main.py`)
- ✅ **`alert_logs` now fills** — behavior onsets write a `driver_behaviors` **and** an `alert_logs` row via a shared `_persist_onsets` helper (severity: drowsy/distracted=high, yawning=medium). (`main.py`)
- ✅ **`performance_metrics` now fills** — a sampled `_sample_performance` writes one row every ~30 processed frames: avg `processing_time` + `fps` (pipeline capacity = 1/avg processing time, so it can't blow up), plus `cpu_usage`/`memory_usage` when `psutil` is installed (else null). (`main.py`)
- ✅ **Session lifecycle** — an `atexit` hook calls `end_monitoring_session` on shutdown, so sessions close (`status=completed`, `end_time` set). Best-effort: runs on normal exit / Ctrl+C, not on a forced kill.
- ✅ **DB password via `.env`** — `config_loader` auto-loads a gitignored `.env` (real env vars still win), so plain `python main.py` connects to MySQL without an inline prefix. Template committed as `.env.example`.

**Still open (optional):**
- **Reloader duplication** — run with `use_reloader=False` (or `debug=False` / a real WSGI server) outside local dev to stop the 2-sessions-per-launch; `debug=True` also exposes the Werkzeug debugger. (Session-close now cleans the orphan on shutdown.)
- **Read parity** — either surface MySQL history in the app (via `/api/db/behaviors/recent`) or keep file-based history as the source of truth and treat MySQL as analytics-only.
- **Schema polish (optional)** — int FKs to `monitoring_sessions.id`; add a `timestamp` index for time-range queries.

## Setup runbook (reproducible)

```sql
-- as MySQL root, once:
CREATE DATABASE IF NOT EXISTS eyedtrack_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'eyedtrack_app'@'localhost' IDENTIFIED BY '<db-password>';
ALTER USER 'eyedtrack_app'@'localhost' IDENTIFIED BY '<db-password>';   -- forces pw if user pre-existed
GRANT ALL PRIVILEGES ON eyedtrack_db.* TO 'eyedtrack_app'@'localhost';
FLUSH PRIVILEGES;
```
```bash
# config.yaml: integration.database.enabled: true (already set).
# Preferred: put the password in a gitignored .env (copy .env.example), then just:
python main.py                                      # config_loader auto-loads .env; tables auto-create
# Or pass it inline (a real env var overrides .env):
EYEDTRACK_DB_PASSWORD=<db-password> python main.py
```

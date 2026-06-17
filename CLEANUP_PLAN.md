# EyeDTrack Backend — Cleanup & Refactor Plan

> Analysis of the Python backend (the Android `app/`, `sdk/`, `gradle/` code is out of scope here).
> Goal: remove dead/broken code, collapse duplicated functions onto a single source of truth,
> and document the one path that actually runs.
>
> **Nothing in this document has been changed yet** — it is a plan. Work top-to-bottom in the
> phases at the end; verify after each phase.

---

## 0. Scope updates (owner decisions)

Two things originally marked for deletion are being **kept** by request:

1. **Video recording** — `video_recorder.py` stays. The recorder is retained for a future
   "record the risky-behavior clips" feature. (See §5 / §13.)
2. **MySQL persistence** — the SQLAlchemy layer (`utils/db_manager.py`, `models/schema.py`) and the
   `integration.database` config stay. It is currently **not wired into the running server** and needs
   integration work — see the new **§12 "MySQL integration — what needs updating"**.

These override the "delete" verdicts for those files in §3 and §7 below.

---

## 1. What actually runs (the live path)

The server entry point is `main.py`. Only this chain executes in production:

```
main.py
  └── config_loader.load_config()            # config
  └── frame_processor.OptimizedFrameProcessor
        ├── face_analysis/improved_detection.ImprovedFaceAnalyzer   # detection (dlib)
        ├── video_recorder.VideoRecorder      # ⚠ instantiated but never used (see §5)
        ├── behavior_categories.BEHAVIOR_CATEGORIES
        └── event_logger.log_event / get_event_type   # file-based JSON logging
```

**Live modules (keep):** `main.py`, `frame_processor.py`, `config_loader.py`,
`event_logger.py`, `behavior_categories.py`, `face_analysis/improved_detection.py`,
`face_analysis/__init__.py`, `video_recorder.py`.

Everything else is dead, broken, duplicated, or a standalone dev script. Details below.

---

## 2. Broken modules — import things that don't exist (DELETE)

These reference modules/symbols that are **not present anywhere in the repo**
(`optimized_pipeline.py`, `original_pipeline.py`, `main_optimized.py`, `run_driver_monitoring`).
They cannot be imported and crash on load.

| File | Broken import | Verdict |
|------|---------------|---------|
| `pipeline.py` | `from original_pipeline import ...`, `from optimized_pipeline import ...` | **Delete** |
| `pipeline_compat.py` | `from optimized_pipeline import ...`, `from pipeline import ...` | **Delete** |
| `benchmark.py` | `from pipeline import ...`, `from optimized_pipeline import ...`, `from main_optimized import load_config` | **Delete** |
| `database_integration.py` | `from main import run_driver_monitoring` (doesn't exist), `from database_integration import DatabaseManager` (self-import of a class it doesn't define) | **Hold → rewrite** (see §12) — broken, but it's the only attempt at DB-backed mobile endpoints; rebuild against the real `db_manager` instead of deleting blindly |

`pipeline.py`, `pipeline_compat.py`, `benchmark.py` are not imported by `main.py` or its live chain, so
deleting them cannot break the server. `database_integration.py` is also broken, but is **held** for the
MySQL rework (§12) rather than deleted.

---

## 3. Unused-but-functional modules (DECIDE: archive or delete)

These import cleanly but are **not referenced by the live path**. They are leftovers from an
earlier desktop/threaded architecture or an unused DB layer. Keep only if you want them as thesis
reference material; otherwise remove.

| File | What it is | Used by | Recommendation |
|------|-----------|---------|----------------|
| `frame_grabber.py` | `OptimizedFrameGrabber` camera thread | nobody (API receives frames over HTTP) | Delete — no camera-grab in the API server |
| `clahe.py` | Full CLAHE/gamma/homomorphic toolkit | nobody (live path inlines its own CLAHE) | See §4 — fold into live path **or** delete |
| `visualization.py` | OpenCV dashboard/overlay drawing | nobody (server is headless) | Delete or move to `dev/` |
| `face_analysis/head_pose.py` | `HeadPoseEstimator` (solvePnP) | nobody | Delete — live path uses its own geometric head pose |
| `face_analysis/face_detection.py` | `FaceDetector` (MediaPipe/Haar/CNN) | only `analyze_behavior_detection.py` (dev) | Delete with the dev script, or move both to `dev/` |
| `face_analysis/ear_mar.py` | `eye_aspect_ratio`, `mouth_aspect_ratio`, states | only `analyze_behavior_detection.py` (dev) | See §4 |
| `face_analysis/eye_analysis.py` | re-export shim of `ear_mar` | nobody | Delete |
| `face_analysis/mouth_analysis.py` | wrapper + duplicate `get_mouth_state` | nobody | Delete |
| `face_analysis/utils.py` | smoothing + landmark normalize helpers | nobody | Delete |
| `utils/db_manager.py` | SQLAlchemy `DatabaseManager` (MySQL) | nobody yet (logging is file-based) | **KEEP** — MySQL is on the roadmap; needs wiring (§12) |
| `models/schema.py` | SQLAlchemy ORM models | `utils/db_manager.py` | **KEEP** — backs the MySQL layer (§12) |

**Dev/standalone scripts** (run by hand, never imported by the server):
`analyze_behavior_detection.py`, `verify_all_fixes.py`, `validate_improvements.py`.
Recommendation: move into a `dev/` or `scripts/` folder so they don't read as part of the product.
Note they use `ConfigLoader` + `face_analysis.ear_mar`, so if you keep them, keep those deps too
(or update the scripts to the canonical functions in §4).

---

## 4. Duplicated functions — the core of the cleanup

The same computation is implemented in multiple places, often with **divergent logic**. Pick one
canonical version and delete the rest.

### 4.1 EAR / MAR (eye & mouth aspect ratio) — 3 implementations
| Location | Function | Notes |
|----------|----------|-------|
| `face_analysis/improved_detection.py:120` | `calculate_ear` | **CANONICAL** (live path) — expects 6 pts |
| `face_analysis/improved_detection.py:156` | `calculate_mar` | **CANONICAL** (live path) — expects 20 pts, `(A+B+C)/(3D)` |
| `face_analysis/ear_mar.py:73` | `eye_aspect_ratio` | dev-only; different return contract (`None` on fail) |
| `face_analysis/ear_mar.py:126` | `mouth_aspect_ratio` | dev-only; 6-pt `(A+B)/(2C)` — **different formula** than canonical |
| `face_analysis/mouth_analysis.py:9` | `mouth_aspect_ratio` | just calls `ear_mar.mouth_aspect_ratio` (pointless wrapper) |
| `face_analysis/eye_analysis.py:3` | `eye_aspect_ratio` (re-export) | pointless shim |

**Action:** keep the `improved_detection` versions. Delete `eye_analysis.py`, `mouth_analysis.py`.
Delete `ear_mar.py` once the dev script (`analyze_behavior_detection.py`) is removed or repointed.

### 4.2 `get_mouth_state` — defined twice, with different signatures
- `face_analysis/ear_mar.py:241` — `get_mouth_state(mar)` using module-global thresholds.
- `face_analysis/mouth_analysis.py:13` — `get_mouth_state(mar, threshold_closed=0.35, threshold_open=0.65)`.

Two functions, same name, different behavior. Neither is used by the live path. **Delete both** with their files.

### 4.3 `weighted_temporal_smoothing` — defined twice, **different math**
- `face_analysis/ear_mar.py:30` — `alpha*new + (1-alpha)*history[-1]` (EMA on last value).
- `face_analysis/utils.py:9` — exponentially-weighted average over the **whole** history.

Same name, divergent results. Neither is on the live path. **Delete both** (live path uses
`deque` history in `frame_processor` but never actually smooths — see §5).

### 4.4 Head pose — 2 unrelated implementations
- `face_analysis/improved_detection.py:193` — `calculate_head_pose` (geometric). **CANONICAL** (live).
- `face_analysis/head_pose.py` — `HeadPoseEstimator` (solvePnP + Kalman). Unused. **Delete.**

### 4.5 `normalize_angle` — duplicated
- `frame_processor.py:28` — module-level `normalize_angle`. **Never called** → dead (see §5).
- `face_analysis/head_pose.py:157` — nested inside `estimate()`.

**Action:** delete the dead one in `frame_processor.py`; the head_pose copy goes when §4.4 is deleted.

### 4.6 Face detection / landmarks — 2 implementations
- `improved_detection.py:54/88` — `detect_face` / `get_landmarks` (pure dlib). **CANONICAL** (live).
- `face_analysis/face_detection.py:112/166` — `detect` / `get_landmarks` (MediaPipe→CNN→Haar).
  Dev-only. **Delete** (also drops the unused MediaPipe + Haar dependencies).

### 4.7 CLAHE — inline vs full module, and **config is ignored**
- `frame_processor.py:248` `preprocess_frame` inlines CLAHE, **hardcoded** `clipLimit=2.0`,
  `tileGridSize=(8,8)` — it ignores the `clahe:` section in `config.yaml`
  (`clip_limit: 2.5`, `base_tile_grid_size: [8,8]`, gamma/homomorphic flags).
- `clahe.py` — a full, configurable CLAHE toolkit that nothing uses.

**Action (pick one):**
- (a) Delete `clahe.py`, and make the inline CLAHE read `config["clahe"]` so the YAML actually
  takes effect; **or**
- (b) Replace the inline block with a call into `clahe.py` (`apply_clahe(... clip_limit=config[...])`)
  and keep `clahe.py` as the single source.

Either way, today's behavior silently ignores the configured CLAHE values — worth fixing.

---

## 5. Dead code *inside* live files

These live in modules that run, but the code itself is never exercised.

| Location | Issue | Action |
|----------|-------|--------|
| `frame_processor.py:28` | `normalize_angle()` — never called | Delete |
| `frame_processor.py:86` | `self.video_recorder = VideoRecorder(...)` is created but `write_frame`/`start_recording` are **never called** | Either wire recording into `process_frame`, or remove the recorder (and the `video_recorder.py` dep) |
| `frame_processor.py:89-92` | `ear_history` / `mar_history` / `head_pose_history` deques + `smoothing_alpha` are populated nowhere and never read | Delete, or implement the intended temporal smoothing |
| `frame_processor.py:262` | `get_face_roi()` — defined, never called (ROI config exists but unused) | Delete or wire up |
| `frame_processor.py:278` | `run()` — empty stub (`pass`) | Delete |
| `frame_processor.py:79-82` | `last_face_roi`, `tracking_failures`, `max_tracking_failures` — set, never used | Delete |

---

## 6. `config_loader.py` — duplicated and self-conflicting config

This file is the biggest correctness risk.

1. **Two copies of the defaults.** A module-level `DEFAULT_CONFIG` (lines 21–126) **and** a second
   inline `default_config` built inside `load_config()` (lines 143–197). They **disagree**:
   the inline one has no `clahe`, `detection`, `display`, `head_pose`, or `robustness` sections,
   and a different `integration.api` shape. `load_config()` uses the inline copy; `validate_config()`
   falls back to the module-level copy. → **Merge into one source of truth** and have `load_config`
   deep-merge YAML over it.

2. **Thresholds get clobbered.** Lines 215–220 overwrite `default_config["thresholds"]` with only
   `drowsy_frames` / `yawn_frames` / `distraction_frames`, **discarding** any
   `ear_lower/ear_upper/mar_lower/mar_upper/yaw_threshold/...` that were just loaded. It happens to
   work because `config.yaml`'s `thresholds:` only has those three keys — but it's a trap. Remove the
   destructive reassignment; rely on the deep-merge.

3. **Two config APIs.** `load_config()` (used by `main.py`) and the `ConfigLoader` class (used by the
   dev scripts). Pick one. If the dev scripts stay, keep `ConfigLoader` as a thin wrapper; otherwise
   delete the class.

4. **Fragile lookups in the live path.** `frame_processor` reads `config["head_pose"]["smoothing_alpha"]`,
   `config["performance"]["use_roi"]`, `["roi_margin"]`, `config["face_detection"]["max_tracking_failures"]`.
   None exist in the inline defaults — they only come from `config.yaml`. If the YAML is missing, the
   server `KeyError`s on startup. Add these keys to the canonical defaults (and use `.get()` with
   fallbacks like the rest of `__init__` already does).

---

## 7. Duplicate / stray files & assets

| Item | Issue | Action |
|------|-------|--------|
| `shape_predictor_68_face_landmarks.dat` (root, **95.1 MB**) **and** `models/…` (95.1 MB) | identical 95 MB binary duplicated | Keep one. Live code loads the **root** copy (`improved_detection.py:20-21`). Delete `models/` copy |
| `mmod_human_face_detector.dat` (root **and** `models/`) | duplicated; only used by deleted `face_detection.py` | Delete both if §4.6 is removed |
| `haarcascade_frontalface_default.xml` (root, 1.2 MB) | only used by `face_detection.py` | Delete if §4.6 is removed |
| `eyedtrack.db` (root SQLite file) | SQLite orphan — the kept DB layer targets MySQL, not SQLite | **Hold** — delete only once MySQL (§12) is confirmed working; it may hold throwaway test data |
| `README (2).md`, ` (2).gitignore` | accidental duplicates of `README.md` / `.gitignore` | Delete |
| `__pycache__/` | build artifact, should not be tracked | Delete + add to `.gitignore` |
| `.idea/` | IDE settings | Add to `.gitignore` (don't track) |
| `driver_monitoring_logs/` (90+ `debug_*.txt` / `driver_events_*.json`) | runtime output committed to the repo | Move to `.gitignore`; keep the dir, drop the historical logs |
| `python/drowsiness2.py`, `python/earonly.txt` | original reference scripts | Move to `dev/reference/` or delete |
| `BEHAVIOR_DETECTION_ANALYSIS.md`, `CHANGELOG.md` | docs (some describe the old architecture) | Keep, but reconcile with the new structure after cleanup |

> ⚠️ The two 95 MB model files are tracked in git history. Deleting the file shrinks the working tree
> but not `.git`. If repo size matters, that's a separate `git filter-repo` / Git LFS task — call it
> out but don't attempt it as part of this cleanup.

---

## 8. `requirements.txt` is out of sync

Current `requirements.txt` **misses** packages the code imports, and lists some only used by
dead code.

- **Missing but imported by live code:** `flask-compress` (`main.py:21`).
- **Missing, imported by non-live code:** `flask-socketio` (`database_integration.py`),
  `sqlalchemy` + `pymysql` (DB layer), `matplotlib` (`visualization.py`, `benchmark.py`).
- **Listed but only used by code being deleted:** `mediapipe` (only `face_detection.py`).

**Action:** after deleting dead modules, regenerate requirements to match the **live** imports only:
`flask`, `flask-cors`, `flask-compress`, `numpy`, `opencv-python`, `dlib`, `scipy`, `pyyaml`,
`gunicorn` (+ `python-dotenv` if actually used — it currently isn't imported anywhere).

---

## 9. Target structure after cleanup

```
thesis-eyedtrack/
├── main.py
├── frame_processor.py
├── config_loader.py            # single DEFAULT_CONFIG, non-destructive merge
├── config.yaml
├── event_logger.py
├── behavior_categories.py
├── video_recorder.py           # only if recording is actually wired up
├── face_analysis/
│   ├── __init__.py
│   └── improved_detection.py   # the one detection implementation
├── models/                     # KEPT for MySQL (§12)
│   ├── __init__.py             # to add
│   └── schema.py
├── utils/                      # KEPT for MySQL (§12)
│   ├── __init__.py             # to add
│   └── db_manager.py
├── shape_predictor_68_face_landmarks.dat
├── requirements.txt
├── README.md
└── dev/                        # optional: kept-but-not-shipped
    ├── analyze_behavior_detection.py
    ├── verify_all_fixes.py
    └── validate_improvements.py
```

Deleted: `pipeline.py`, `pipeline_compat.py`, `benchmark.py`,
`frame_grabber.py`, `clahe.py` (or folded in), `visualization.py`,
`face_analysis/{head_pose,face_detection,ear_mar,eye_analysis,mouth_analysis,utils}.py`,
duplicate `.dat`, `README (2).md`, ` (2).gitignore`.
Kept for the roadmap: `utils/`, `models/`, `video_recorder.py`.
Held pending MySQL wiring: `database_integration.py` (rewrite), `eyedtrack.db` (remove after verify).

---

## 10. Phased action plan

**Phase 0 — Safety net**
- [ ] Commit current state / branch so everything is recoverable.
- [ ] Confirm the server boots today: `py -3.14 main.py` → hit `/api/health`.

**Phase 1 — Delete broken modules (zero risk, §2)**
- [ ] Delete `pipeline.py`, `pipeline_compat.py`, `benchmark.py`.
- [ ] **Hold** `database_integration.py` — broken, but kept for the MySQL rework (§12/Phase 7).
- [ ] Boot server + `/api/health` + one `/api/process_frame` to confirm no regressions.

**Phase 2 — Remove the unused desktop layer (§3)**
- [ ] Delete `frame_grabber.py`, `visualization.py`.
- [ ] **KEEP** `utils/db_manager.py`, `models/schema.py` (MySQL — §12).
- [ ] **Hold** `eyedtrack.db` (delete after MySQL is verified).
- [ ] Decide on `clahe.py` (delete or fold into `preprocess_frame` per §4.7).

**Phase 3 — Collapse duplicated detection code (§4)**
- [ ] Delete `face_analysis/{head_pose,eye_analysis,mouth_analysis,utils}.py`.
- [ ] Decide the dev scripts' fate; then delete `face_analysis/{ear_mar,face_detection}.py`
      (or repoint scripts to `improved_detection`).
- [ ] Confirm `face_analysis/__init__.py` only exports `ImprovedFaceAnalyzer`.

**Phase 4 — Clean dead code in live files (§5)**
- [ ] Remove `normalize_angle`, `get_face_roi`, `run`, unused deques/ROI/tracking state in `frame_processor.py`.
- [ ] Either wire up or remove `VideoRecorder`.

**Phase 5 — Fix `config_loader.py` (§6)**
- [ ] Single canonical `DEFAULT_CONFIG`; deep-merge YAML; delete the destructive threshold reassignment.
- [ ] Add the keys `frame_processor` depends on so a missing `config.yaml` doesn't crash startup.
- [ ] Keep or drop `ConfigLoader` based on Phase 3 decision.

**Phase 6 — Assets, deps, docs (§7, §8)**
- [ ] Delete duplicate `.dat`/`.xml`, `README (2).md`, ` (2).gitignore`.
- [ ] Update `.gitignore` (`__pycache__/`, `.idea/`, `driver_monitoring_logs/`).
- [ ] Rebuild `requirements.txt` from live imports.
- [ ] Reconcile `README.md` (it still says LLAVA/Haar Cascade — the live path is dlib only).

**Phase 7 — MySQL persistence (§12)** — IMPLEMENTED (disabled by default; dual-write; one row per behavior)
- [x] Added `SQLAlchemy` + `PyMySQL` to `requirements.txt`.
- [x] Added `models/__init__.py`, `utils/__init__.py`; added `integration.database` (incl. `enabled`) to `DEFAULT_CONFIG` and `config.yaml`.
- [x] `main.py` instantiates `DatabaseManager` in `initialize_system()` **only if `integration.database.enabled`**, inside try/except (DB failure → file-only logging, server stays up); opens a monitoring session.
- [x] Added `_db_behavior_rows()` mapper (nested result → one flat row per active behavior) and a dual-write next to the existing `log_event` in `/api/process_frame`.
- [ ] **You:** create the MySQL `eyedtrack_db` schema + set `integration.database.enabled: true`, then `pip install -r requirements.txt` and boot to verify rows land. Tables auto-create on first connect.
- [x] Rewrote `database_integration.py` as a Flask Blueprint (`/api/db/*`) on the real `db_manager` API; registered on main's app (returns 503 until MySQL is enabled).
- [ ] (Later) end the monitoring session on shutdown; migrate read endpoints to MySQL; remove `eyedtrack.db`.

> Note: the dual-write inserts a row **per frame** while a (debounced) behavior persists, so a sustained
> drowsy episode produces many rows. Fine for an audit trail; add throttling/dedup later if the table grows fast.

**Verify after every phase:** server boots, `/api/health` returns 200, `/api/process_frame` with a
real base64 frame returns metrics. That single end-to-end check covers the whole live path.

---

## 11. Notable correctness issues found along the way (not just cleanup)

These aren't strictly "duplication" but surfaced during analysis and are worth fixing:

1. **CLAHE config ignored** (§4.7) — `config.yaml` CLAHE settings have no effect.
2. **Threshold clobbering** (§6.2) — `load_config` silently drops most threshold keys.
3. **README is stale** — claims LLAVA + Haar Cascade; the running detector is pure dlib
   (`ImprovedFaceAnalyzer`). MediaPipe/Haar/CNN only existed in the now-dead `face_detection.py`.
4. **`VideoRecorder` never records** (§5) — if recording is a thesis requirement, it's currently a no-op.
5. **MAR formula differs** between the live `calculate_mar` (20-pt, `/3D`) and the dev `mouth_aspect_ratio`
   (6-pt, `/2C`). If the dev scripts are used to validate thresholds, they measure a *different* MAR than
   production — reconcile before trusting their numbers.

---

## 12. MySQL integration — what needs updating

The DB layer exists and is well-formed but **completely unwired**. Nothing in the live path
(`main.py` → `frame_processor` → `event_logger`) touches MySQL; all persistence today is the
append-only JSON file `driver_monitoring_logs/driver_monitoring.json`.

**Current state**
- `models/schema.py` — ORM tables: `MonitoringSession`, `DriverBehavior`, `AlertLog`,
  `PerformanceMetric`. Looks complete.
- `utils/db_manager.py` — `DatabaseManager(config)` reads `config['integration']['database']`, builds a
  `mysql+pymysql://…` engine, calls `Base.metadata.create_all()` (auto-creates tables), and exposes
  `create_monitoring_session`, `log_behavior`, `log_alert`, `log_performance_metrics`,
  `get_recent_behaviors`, `get_session_summary`, `cleanup_old_data`.
- `config.yaml` already has the `integration.database` block (mysql / localhost:3306 / `eyedtrack_db`
  / root / empty password / pool settings). ✔
- `database_integration.py` — a separate, **broken** Flask-SocketIO mobile API that calls a DB API
  (`log_risky_behavior`, `get_risky_behaviors`, `get_behavior_summary`) that **does not exist** on the
  real `db_manager`. It also imports `run_driver_monitoring` from `main` (doesn't exist).

**What needs to be updated (in order):**

1. **Dependencies** — add to `requirements.txt`: `SQLAlchemy` and `PyMySQL`
   (the engine URL is `mysql+pymysql`). Neither is currently listed. A MySQL server must be running
   with a database named `eyedtrack_db` and the credentials from `config.yaml`.

2. **Package markers** — add empty `models/__init__.py` and `utils/__init__.py`. Today
   `from models.schema import …` / `from utils.db_manager import …` only work as namespace packages
   (i.e. when launched from the project root). Explicit `__init__.py` makes imports robust.

3. **Config defaults + an enable flag** — fold `integration.database` into the single `DEFAULT_CONFIG`
   (Phase 5) so a missing `config.yaml` doesn't crash, and add `integration.database.enabled: true`.
   The server should run **with MySQL off** gracefully (so a DB outage ≠ dead server).

4. **Instantiate the manager in `main.py`** — in `initialize_system()`, if
   `integration.database.enabled`, create a global `db_manager = DatabaseManager(config)` **inside a
   try/except** (a DB connection failure should log a warning and fall back to file-only logging, not
   abort startup). Then open a session: `session_id = db_manager.create_monitoring_session(device_info)`.
   `DatabaseManager.__init__` auto-creates the tables, so no manual migration is needed — but the
   `eyedtrack_db` schema/database itself must already exist on the MySQL server.

5. **Shape adapter (the real work)** — `process_frame()` returns nested data
   (`behavior_category{is_drowsy,is_yawning,is_distracted}`, `metrics{ear,mar,head_pose}`,
   `behavior_confidence`), but `db_manager.log_behavior()` expects a **flat** dict
   (`behavior`(str), `confidence`, `is_risky`, `ear`, `mar`, `head_pose`, `additional_metrics`).
   Write a small mapper. **Decision needed:** `DriverBehavior.behavior` is a single
   `String(100) NOT NULL`, but multiple behaviors can be active at once. Either
   (a) one row per active behavior, or (b) one row with a combined label (e.g. `"drowsy+yawning"` /
   `"normal"`) plus the individual flags in the `additional_metrics` JSON. Map `head_pose` to
   `{"yaw":…, "pitch":…, "roll":…}` for the JSON column.

6. **Where to log from** — call `db_manager.log_behavior(...)` from the same place the file log is
   written. Cleanest option: **dual-write** — keep `event_logger.log_event` (the existing endpoints
   depend on the JSON file) **and** add the DB write alongside it, behind the enable flag. Do not rip
   out the file logging until the endpoints are migrated.

7. **(Optional, later) migrate the read endpoints** — `/api/latest_behavior`, `/api/alert_history`,
   `/api/clear_alert_history` currently parse the JSON file. Once MySQL is trusted, repoint them to
   `db_manager.get_recent_behaviors()` / `get_session_summary()`. Until then, leave them on the file.

8. **Session lifecycle** — call `db_manager.end_monitoring_session(session_id)` on shutdown
   (`atexit` handler or an explicit `/api/session/end` route). Optional but tidy.

9. **Fix or replace `database_integration.py`** — it cannot run as-is. Either delete it, or rebuild the
   useful endpoints (mobile session start/stop, recent behaviors, dashboard summary) against the **real**
   `db_manager` API and fold them into `main.py`. Its mocked SocketIO worker (emitting fake data) should
   be dropped regardless.

10. **`eyedtrack.db`** — leftover SQLite file, unrelated to the MySQL layer. Remove once MySQL is verified.

> Items 1–6 are the minimum to get driver behaviors persisting into MySQL. 7–9 are follow-ups.
> Because this needs a live MySQL server and the row-mapping decision in step 5, it is **not part of the
> mechanical cleanup phases** — it's tracked as its own Phase 7 once the decisions below are made.

---

## 13. Video recording (retained for future)

`video_recorder.py` (`VideoRecorder`) is kept. Today it is instantiated in `frame_processor.__init__`
but `write_frame()` / `start_recording()` are never called, so no clips are produced. To activate it
later, call `self.video_recorder.write_frame(frame, is_risky=<any final behavior flag>)` inside
`process_frame()` (the raw `frame` is already in scope). The class already buffers ~2 s pre-roll and
auto-stops 3 s after the last risky frame, so wiring is a one-line hook plus codec availability on the
host. Left unwired for now per owner request; the file and the instance are preserved.

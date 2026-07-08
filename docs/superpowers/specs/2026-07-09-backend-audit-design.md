# EyedTrack Backend Audit — Design Spec

**Date:** 2026-07-09 · **Status:** Approved · **Type:** Audit + targeted fixes (live, against the running backend + MySQL)

## Goal
Verify the Flask driver-monitoring backend end-to-end — that it **correctly utilizes every algorithm in the live path**, that **all API routes work end-to-end**, and that the **MySQL persistence + schema are sound** — then fix the genuinely-broken items, remove unused models, and deliver a findings report.

## Approach
Live end-to-end audit (exercise the real running backend + real MySQL 8.0, already up on this machine), not static-only — the DB-auth failure we already observed is exactly what a static read misses.

## Workstreams
**A · Algorithms — verify correct utilization + fix bugs.**
Trace the live path: `process_frame → base64→cv2 → frame_processor (CLAHE preprocessing) → ImprovedFaceAnalyzer (dlib HOG detect → 68 landmarks → EAR/MAR/solvePnP head-pose) → behavior_categories → temporal counters (drowsy=6 / yawn=2 / distraction=5) → response`. Confirm each stage is actually invoked and correct. **Prime suspects:** is CLAHE (built in `__init__`) actually applied per-frame; EAR left/right landmark indices + averaging; MAR indices; head-pose; the temporal smoothing counters; thresholds (EAR 0.27 / MAR 0.6 / yaw 35 / pitch 25). Fix real bugs. Report orphaned pieces (unused CNN `mmod` detector, removed CNN modules).

**B · API endpoints — live end-to-end.**
Exercise every route on the running server and verify response shape + correctness: `GET /api/health`, `POST /api/process_frame` (real face image → metrics+behaviors), `GET /api/latest_behavior`, `GET /api/alert_history`, `POST /api/clear_alert_history`, `POST /process_frame` (redirect). Confirm shapes match what the Android app parses (`behaviors: List<String>`, `metrics{ear,mar,head_pose}`, alert-history `alerts[]` with `timestamp`/`behavior_category`/`behavior_confidence`). Fix anything broken.

**C · Database — repair persistence + assess schema.**
MySQL 8.0 is running. Create `eyedtrack_db` + a dedicated `eyedtrack_app` user (password + grants), reconcile `config.yaml` (`enabled: true`). Verify the 4 tables auto-create (`monitoring_sessions`, `driver_behaviors`, `alert_logs`, `performance_metrics`); run a live `process_frame` and confirm rows persist. Audit write paths (are `alert_logs` / `performance_metrics` ever written, or only `driver_behaviors`?) and read paths (`/api/alert_history` source). Fix real gaps; assess schema soundness (FKs, indexes) and report. **No schema redesign or data migration.**

**Plus:** remove unused model artifacts — `mmod_human_face_detector.dat` (CNN detector, never loaded) + any orphaned dead source — after confirming zero references.

## Out of scope
No new ML (no CNN classifier training/serving); no schema redesign or migration; no Android changes beyond verifying response-shape compatibility; no changes to detection thresholds unless a bug is found.

## Deliverable
A written audit report (`docs/` — findings per workstream, used-vs-unused, correctness issues, DB state) + the fixes committed on the branch.

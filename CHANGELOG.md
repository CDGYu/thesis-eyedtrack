# Changelog

## [3.0.0] - 2026-07-09
Major release: full Android UI/UX overhaul ("Signal" design system) + a live backend audit
with fixes that make MySQL persistence fully functional. Design specs, implementation plans,
and the audit report are under `docs/superpowers/`.

### Added
- **UI — "Signal" design system**: dark Material 3 theme, design tokens, variable Sora/Inter
  fonts, and a reusable `Widget.EyedTrack.*` component set.
- **UI — single-Activity navigation**: `MainActivity` + `BottomNavigationView` + AndroidX
  Navigation with 4 fragments (Dashboard / Monitor / History / Account); CameraX in
  `MonitorFragment`.
- **UI — redesigned auth + account** sub-screens and all legal/info/FAQ screens on a shared
  Signal document template, plus an accessibility pass (AA contrast, larger touch targets).
- **Configurable backend server address** in-app (PreferenceManager + Notifications & Sounds).
- **Orientation-robust face detection** (`_oriented_face`, tries 4 rotations + upsamples) and
  upright CameraX frames (`imageInfo.rotationDegrees`).
- **MySQL persistence, fully wired**: `driver_behaviors` + `alert_logs` on each risky-behavior
  onset, `performance_metrics` sampled (~1 row / 30 frames, cpu/memory via `psutil`), and
  `monitoring_sessions` closed on shutdown.
- **`/api/alert_history` now reads MySQL** (file-log fallback + `source: mysql|file` marker) —
  no Android client change.
- **`.env` support** for the DB password (gitignored; `.env.example` template), `timestamp`
  DB indexes, and `psutil` as an optional dependency.
- **Backend audit report** at `docs/superpowers/reports/2026-07-09-backend-audit-report.md`.

### Changed
- App restructured from multiple Activities to a single-Activity + fragments architecture.
- `/api/process_frame` returns **400** (not 500) for missing/malformed/undecodable frames and
  no longer leaks a traceback or the raw request body.
- Flask runs with `use_reloader=False` (one monitoring session per launch); debugger
  configurable via `EYEDTRACK_DEBUG` (default true).
- DB credentials sourced from `.env` / environment variables instead of `config.yaml`.

### Fixed
- **Monitor could not connect** to the backend (stale hardcoded LAN IP).
- **No alerts on device** — rotated phone frames prevented face detection (0% → 100% after the
  orientation fix); drowsiness alerts now fire.
- **`alert_logs` / `performance_metrics` were never written**, and monitoring sessions were
  never closed.
- **MySQL persistence was silently disabled** by a credential issue; now connects end-to-end.

### Removed
- 4 legacy Activities with their layouts and unused color resources.
- Unused CNN detector artifact `mmod_human_face_detector.dat` (zero references).
- Third-party design-skill files installed under `.claude/skills`.

### Deferred (tasks to revisit)
- **Integer FKs** (`session_id` → `monitoring_sessions.id`): intentionally not done — the
  VARCHAR FK works fine and is the human-readable key; migration risk > gain.
- **Production hardening**: run behind a real WSGI server (gunicorn) with `EYEDTRACK_DEBUG=false`.
- `performance_metrics.cpu_usage` is `0.0` on the first sample after startup (psutil warm-up).

## [2.0.0] - 2025-05-19
### Added
- Optimized pipeline implementation with better performance
- Face box stabilization for smoother tracking
- Adaptive queue management to prevent bottlenecks
- Progressive behavior analysis to save CPU resources
- Memory and performance tracking tools
- Batch processing support for GPU acceleration
- Enhanced visualization with real-time metrics

### Changed
- Default pipeline is now the optimized implementation
- Configuration file format updated with new options
- Main script supports selection between implementations

### Fixed
- Camera recovery for hardware errors
- Memory leaks in long-running sessions
- GUI update performance issues

## [1.1.0] - 2025-05-23
### Added
- Enhanced face detection with MediaPipe integration
- Improved head pose stabilization with temporal smoothing
- Added weighted temporal smoothing for behavior confidence
- Enhanced configuration validation and error handling
- Added adaptive thresholds for eye and mouth state detection

### Changed
- Adjusted detection thresholds for better accuracy
- Optimized EAR and MAR calculations
- Improved behavior classification confidence
- Updated configuration structure with new settings
- Enhanced error recovery mechanisms

### Fixed
- Reduced false positive detections for behavior recognition
- Improved stability of head pose estimation
- Fixed issues with extreme lighting conditions

## [1.0.0] - 2025-05-01
### Added
- Initial release of the EyeDTrack Driver Monitoring System
- Real-time drowsiness detection
- Distraction monitoring
- Yawning detection
- Basic driver behavior analysis
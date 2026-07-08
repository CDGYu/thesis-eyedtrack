# ADR-0001: EyedTrack UI/UX overhaul — key decisions

**Date:** 2026-07-08 · **Status:** Accepted · **Branch:** `feat/uiux-overhaul-signal`

## Context
EyedTrack (Android driver-monitoring app) shipped on the default Android Studio template theme with hardcoded hex colors, a hand-built per-screen bottom nav, and stock inputs. Goal: a coherent dark design system + restructured navigation without risking the working CameraX/ML/API code.

## Decisions
1. **Stay on XML/Views (NOT Jetpack Compose).** Reuse the working Kotlin (CameraX, Retrofit API, ViewModels) untouched; deliver the overhaul via themes + layouts + Material 3.
2. **"Signal" dark design system.** Material 3, parent **`Theme.Material3.Dark.NoActionBar`** — corrected from `.DayNight` during review because a dark-only app that does not force night mode in code leaks *light* Material defaults for unset roles in the day bucket. Bundled **variable** Sora + Inter fonts (offline-safe). Safety-state color language: green=awake, amber=caution, red=drowsy.
3. **Single-Activity nav host.** `MainActivity` + Material 3 `BottomNavigationView` + AndroidX Navigation + 4 fragments (Dashboard/Monitor/History/Account). `LiveFeedActivity` → `MonitorFragment` with CameraX bound to **`viewLifecycleOwner`** (this fixed a latent scope-reuse bug that would break monitoring after a tab switch).
4. **Sub-screen redesign = layout rewrite + preserve every view ID + minimal Activity chrome edits** (drop old bottom nav + `FLAG_FULLSCREEN`, add shared `@layout/include_top_bar`, `MaterialAlertDialogBuilder`). Business logic reused verbatim. Rationale: a renamed/removed ID is a runtime NPE the build won't catch.
5. **Dashboard aggregates only existing data** (alert history); no invented "trips/drive-time" metrics.
6. **Execution:** superpowers subagent-driven-development; **one commit per plan** (user request), with controller-side referential-integrity verification each task.
7. **Legacy Activities retired only AFTER device verification** (Phase C, deferred): HomePage/LiveFeed/AlertHistory/Settings.

## Consequences
Low risk to the working ML/camera path; the whole app renders dark; each plan is an independently reviewable, revertible commit. Trade-off: the legacy Activities linger as dead code until Phase C.

## Notes
- Security: the `ui-ux-pro-max-cli` installer's `.claude/skills/` prompt-injected a review subagent; removed (`bd1eabb`) + gitignored. See memory `uipro-skills-prompt-injection`.
- Full status/handoff: `docs/superpowers/HANDOFF-2026-07-08.md`.

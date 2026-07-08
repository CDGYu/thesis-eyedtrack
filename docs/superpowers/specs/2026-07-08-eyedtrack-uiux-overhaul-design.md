# EyedTrack — UI/UX Overhaul Design Spec

**Date:** 2026-07-08
**Status:** Approved (visual design signed off in brainstorming; awaiting spec review)
**Author:** Design brainstorming session
**Design direction:** "Signal" — dark, data-forward driver-safety aesthetic

---

## 1. Overview

EyedTrack is a native Android driver-monitoring app (drowsiness, distraction, and
yawning detection over a live camera feed, backed by a Python/ML service). The UI is
functional but visually unpolished: it runs on the **default Android Studio template
theme** (purple/teal) while individual screens ignore it and use **hardcoded hex colors**,
inconsistent hand-built navigation, and stock input styling.

This is a **full UX overhaul** of the Android app: a real design system, a restructured
information architecture, and a screen-by-screen redesign — delivered entirely in the
existing **XML/Views + Material 3** stack so the working Kotlin (CameraX, API, ViewModels,
ML integration) is preserved.

### Goals
- Replace ad-hoc styling with a **single design-token system** every screen inherits.
- Establish a distinctive, on-theme visual identity ("Signal") appropriate for a
  safety-critical, in-vehicle, potentially night-time context.
- Fix the **fragmented navigation/IA**: a real bottom-nav app, a proper dashboard, and
  consolidation of 7 scattered legal/info screens.
- Make the app **defense-ready**: coherent, professional, screenshot-worthy.

### Non-goals (out of scope)
- No changes to the Python backend, ML models, detection thresholds, or API contracts.
- No new detection features; the Dashboard only **aggregates data that already exists**.
- **No Jetpack Compose migration** — stay in XML/Views.
- **No light theme** — the app is dark-first, single theme (see §3.4).
- No new business logic beyond what the redesigned screens require to render.

---

## 2. Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Full UX overhaul, all screens |
| Aesthetic | **C · "Signal"** — deep indigo-slate, electric-blue primary, vivid color-coded safety states |
| UI stack | **Stay in XML**, upgrade to **Material 3** |
| Navigation/IA | **Bold restructure** — 4-tab bottom nav, real dashboard, consolidate legal/info |
| Typography | **Sora** (display/headings) + **Inter** (UI/body) |
| Theme mode | Dark-first, single theme |

Build config confirmed: `compileSdk 34`, `minSdk 30`, `targetSdk 34`,
`com.google.android.material:material:1.11.0` (Material 3 + `MaterialSwitch` + `Slider`
all available — no dependency bump required).

---

## 3. Design system

### 3.1 Color tokens

Two layers: **primitives** (raw palette) and **semantic aliases** (mapped to Material 3
theme attributes + custom safety attributes). Defined in `res/values/colors.xml`; the theme
maps them in `res/values/themes.xml`.

**Primitives**
| Token | Hex | Role |
|---|---|---|
| `ink_900` | `#0A0F1C` | app background / base |
| `ink_800` | `#111A2D` | surface (cards) |
| `ink_700` | `#18233A` | surface-2 (inputs, insets) |
| `ink_600` | `#1F2C48` | surface-3 (raised) |
| `ink_500` | `#2A3654` | border / outline |
| `ink_400` | `#3A4A70` | border-strong |
| `blue_500` | `#3D7EFF` | primary (electric blue) |
| `blue_400` | `#5A93FF` | primary-hover / on-container |
| `blue_600` | `#2E63D6` | primary-pressed |
| `blue_container` | `#16294D` | primary container (tinted surface) |
| `green_500` / `green_container` | `#22C55E` / `#10321F` | **safe / awake** |
| `amber_500` / `amber_container` | `#F59E0B` / `#3A2A0A` | **caution** |
| `red_500` / `red_container` | `#EF4444` / `#3A1414` | **alert / drowsy / danger** |
| `text_hi` | `#F1F5F9` | primary text |
| `text_mid` | `#A9B6CE` | secondary text |
| `text_lo` | `#6B7A99` | tertiary / muted text |

**Semantic mapping (Material 3 attrs)**
- `colorPrimary` = `blue_500`, `colorOnPrimary` = `#FFFFFF`
- `colorPrimaryContainer` = `blue_container`, `colorOnPrimaryContainer` = `blue_400`
- `android:colorBackground` = `ink_900`
- `colorSurface` = `ink_800`, `colorSurfaceContainer` = `ink_700`, `colorSurfaceContainerHigh` = `ink_600`
- `colorOnSurface` = `text_hi`, `colorOnSurfaceVariant` = `text_mid`
- `colorOutline` = `ink_500`, `colorOutlineVariant` = `ink_400`
- `colorError` = `red_500`, `colorOnError` = `#FFFFFF`

**Custom safety attributes** (Material 3 has no "caution/safe" slot). Declare theme attrs in
`attrs.xml` and set them in the theme so screens reference `?attr/stateSafe` etc.:
`stateSafe` / `stateSafeContainer`, `stateCaution` / `stateCautionContainer`,
`stateAlert` / `stateAlertContainer`.

**Contrast:** all body text uses `text_hi` on `ink_*` surfaces (ratio > 12:1). Safety colors
are used for fills/large text/icons and each has a darker container for legible on-color text.
Target WCAG AA (see §7).

### 3.2 Typography

**Fonts:** Sora + Inter, **bundled as TTF** in `res/font/` (not downloadable-fonts) so a
possibly-offline in-car app always renders correctly. Replaces the existing `libre_bodoni`
downloadable font. Weights: Sora 500/600/700/800, Inter 400/500/600/700. Define
`res/font/sora.xml` and `res/font/inter.xml` font families.

**Type scale** (mapped to Material 3 `textAppearance` overrides in the theme):
| Role | Font / weight | Size | Material 3 slot |
|---|---|---|---|
| Display | Sora 800 | 28sp | `textAppearanceDisplaySmall` |
| H1 | Sora 700 | 24sp | `textAppearanceHeadlineSmall` |
| H2 | Sora 600 | 20sp | `textAppearanceTitleLarge` |
| Title | Inter 600 | 16sp | `textAppearanceTitleMedium` |
| Body | Inter 400 | 15sp | `textAppearanceBodyLarge` |
| Body-sm | Inter 400 | 13sp | `textAppearanceBodyMedium` |
| Label | Inter 600 | 12sp | `textAppearanceLabelLarge` |
| Caption | Inter 500 | 11sp | `textAppearanceLabelSmall` |
| Metric numerals | Sora 700 | 18–22sp | (applied per-view) |

### 3.3 Shape, spacing, elevation
- **Spacing:** 8pt grid — `4, 8, 12, 16, 20, 24, 32` (dimens: `space_xs`…`space_2xl`).
- **Radius:** `radius_sm 8`, `radius_md 12`, `radius_lg 16`, `radius_xl 20`, `radius_pill 999`.
  Cards use `lg`, buttons/inputs `md`, pills/nav-indicator `pill`.
- **Shape appearances:** `ShapeAppearance.EyedTrack.Small/Medium/Large` set in theme.
- **Elevation:** flat dark surfaces differentiated by **surface tint** (ink_800→ink_600),
  with a soft shadow on primary cards only. Avoid heavy Material shadows on dark.
- **Touch targets:** min 48×48dp.

### 3.4 Theme
- Parent: `Theme.Material3.Dark.NoActionBar`, named `Theme.EyeDTrack`. _(Corrected during
  Plan 1 code review from `.DayNight`: for a dark-only app that does not force night mode in
  code, the `.DayNight` day-bucket inherits Material's **light** defaults for any unset color
  role — so `.Dark` is required to guarantee dark in every system mode.)_
- Dark-first: `values/themes.xml` and `values-night/themes.xml` carry the identical dark theme
  body. Light theme is out of scope.
- System bars: `statusBarColor` = `ink_900`, `navigationBarColor` = `ink_900`,
  light-on-dark icons (`isAppearanceLightStatusBars = false`), edge-to-edge friendly.

---

## 4. Component specs

All are Material 3 components with EyedTrack style overrides (`Widget.EyedTrack.*`), so usage
stays standard and theming is centralized.

| Component | Base | Notes |
|---|---|---|
| **Primary button** | `Widget.Material3.Button` | filled `blue_500`, white text, radius md, 52dp tall, Inter 600 |
| **Secondary button** | `...Button.OutlinedButton` | transparent, `blue_400` text, `ink_400` outline |
| **Text button** | `...Button.TextButton` | `blue_400` text only |
| **Danger button** | filled | `red_500` fill (Stop Monitoring, destructive) |
| **Text field** | `TextInputLayout` OutlinedBox | `ink_700` fill, `ink_500` outline, focus → `blue_500` + label; replaces stock `@android:drawable/edit_text` |
| **Card** | `MaterialCardView` | `ink_800`, 1px `ink_500` stroke, radius lg, 16dp padding |
| **Status pill** | custom drawable-backed `TextView` | safe/caution/alert/idle variants: colored container + dot + on-color text (full control, no `Chip` baggage) |
| **Metric stat** | custom cell | `ink_700` tile, uppercase label + Sora numeral, colored by state |
| **Bottom nav** | `BottomNavigationView` (M3) | 4 items, active = `blue_400` icon+label + pill indicator; `ink_800` surface |
| **Top app bar** | `MaterialToolbar` | Sora title, optional back/menu, transparent over `ink_900` |
| **Switch** | `MaterialSwitch` | track `blue_500` when on |
| **Slider** | `Slider` | `blue_500` active track + thumb (alert volume) |
| **List row** | custom (in card) | leading icon tile (`blue_container`), title/subtitle, trailing chevron |
| **Alert row** | custom | severity dot (green/amber/red), type + detail, time |
| **Trend chart** | lightweight custom `View` (Canvas-drawn bars) | 7-day alert counts; hot/max bars in amber/red. **No charting dependency** |

New/updated drawables: nav icons (dashboard/monitor/history/account), eye logo mark,
status dots, chevrons, severity dots — as vector drawables tinted via `?attr` colors.

---

## 5. Information architecture & navigation

### 5.1 New model
A **single host Activity** (`MainActivity`) hosting a `BottomNavigationView` + the AndroidX
**Navigation component** with four top-level destination **Fragments**. This is the idiomatic
XML/Views way to get correct tab behavior (state retention, single back stack per the
Navigation component) — it delivers the "bold restructure" properly rather than re-launching
Activities per tab.

```
MainActivity (BottomNavigationView + NavHostFragment)
├── DashboardFragment   [tab: Dashboard]
├── MonitorFragment     [tab: Monitor]   ← absorbs LiveFeedActivity + CameraViewModel/CameraService
├── HistoryFragment     [tab: History]   ← absorbs AlertHistoryActivity + adapter
└── AccountFragment     [tab: Account]   ← hub linking out to sub-screens
```

Secondary screens remain **Activities** launched from the host / Account hub: Login, Sign-up,
Loading/Splash, Profile, Notifications & Sounds, User Management, Data & Privacy, Help & Legal
(+ its detail docs), Debug.

**Rejected alternative:** keep every screen an Activity and share a bottom-nav via a base class
+ `<include>`. Simpler, but tab switches re-create Activities (flicker, lost scroll/state) and
duplicate nav wiring — inferior UX for the core loop. We accept the one-time refactor of
LiveFeed/AlertHistory into Fragments to get correct behavior.

### 5.2 Old → new screen mapping (all screens)

| Current screen / layout | New home | Change |
|---|---|---|
| `HomePageActivity` / `home_page.xml` | **DashboardFragment** | Rebuilt: status card + Start Monitoring CTA + today's stats + recent alerts (replaces image-button home) |
| `LiveFeedActivity` / `live_feed.xml` | **MonitorFragment** | Rebuilt: status header, camera viewport, live metrics, Stop; camera logic preserved |
| `AlertHistoryActivity` / `alert_history.xml` (+ item, adapter) | **HistoryFragment** | Rebuilt: 7-day trend + grouped alert list; adapter restyled |
| `ProfileActivity` / `profile_page.xml` | Profile (Account sub) | Restyled to system |
| `SettingsActivity` + `SoundsActivity` | **Notifications & Sounds** | **Merged** into one settings screen (toggles + slider) |
| `UserManagementActivity` (+ `item_user.xml`) | User Management (Account sub) | Restyled list |
| `AboutUsActivity`, `HelpActivity`(+adapter/item), `FAQsActivity`, `DataPrivacyActivity`, `DPAActivity`, `EulaActivity`, `TermsAndConditionsActivity` | **Help & Legal** section | **Consolidated** under one list; each opens a shared legal/info **detail template** |
| `LoginActivity` / `activity_login.xml` | Login | Rebuilt: brand header, M3 text fields, Remember me/Forgot, Sign in |
| `SignUpActivity` / `signup_page.xml` | Sign-up | Rebuilt: matching brand, fields, Terms, Create account |
| `LoadingScreenActivity` / `loading_screen.xml` | Splash/Loading | Restyled to brand (dark, logo, subtle progress) |
| `DebugPreferencesActivity` | Debug | Restyled minimally; kept for dev, reachable from Account (build-guarded) |

---

## 6. Screen designs (approved mockups)

Signed off in the visual companion. Key intent per screen:

- **Dashboard** — greeting; status card (idle/last-session) with prominent **Start Monitoring**
  primary CTA; "Today" stat row (Trips / Alerts / Drive time); "Recent alerts" list. Landing tab.
- **Monitor** — big `Awake/Caution/Drowsy` status (color-coded), camera viewport with face-box
  + scan line + REC, live metric tiles (Eye openness/EAR, Blinks/min, Head pose), red **Stop**.
  *Decision:* raw metrics remain visible to the driver (approved).
- **History** — 7-day trend chart + alerts grouped by day (Today/Yesterday…), each row a
  severity dot + type + detail + time. Tapping a row → detail (reuse existing data).
- **Account** — profile header card; grouped rows (Profile, Notifications & sounds, User
  management | Data & privacy, Help & legal); Sign out (danger text).
- **Login / Sign-up** — eye-mark logo + wordmark + tagline; M3 outlined fields with focus and
  password-visibility toggle; Remember me / Forgot; footer switch link.
- **Notifications & Sounds (settings template)** — grouped cards, `MaterialSwitch` rows
  (Drowsiness / Distraction / Yawning / Vibration / Voice alerts), alert-volume `Slider`,
  value row (Alert tone → Chime). Pattern reused by all settings-like sub-screens.
- **Help & Legal detail template** — a single scrollable document screen (toolbar + title +
  body) reused for About, Help, FAQs, EULA, DPA, Data Privacy, Terms.

---

## 7. Accessibility
- **Contrast:** target WCAG AA (4.5:1 text / 3:1 large & UI). Body text is `text_hi` on dark
  (>12:1). Verify each safety color + on-color pair; darken containers if a pair falls short.
- **Touch targets:** ≥ 48dp; nav items and icon buttons padded to target.
- **Content descriptions:** all icons/ImageButtons/camera controls get `contentDescription`
  (several are currently missing).
- **Text scaling:** use `sp` for text, avoid fixed heights that clip at large font scales.
- **Color is not the only signal:** safety states pair color with a label and a dot/icon.

---

## 8. Implementation phasing

Ordered so the foundation lands first and each later phase is independently reviewable.

1. **Foundation** — `colors.xml` tokens, `attrs.xml` safety attrs, bundle Sora/Inter fonts,
   Material 3 `Theme.EyeDTrack` (dark), type-scale + component styles, shape/dimens, base
   vector drawables. No screen restructured yet; all inherit the new theme.
2. **Navigation shell** — `MainActivity` + `BottomNavigationView` + Navigation graph + four
   Fragments. Move CameraX/`CameraViewModel` into `MonitorFragment`; move alert list into
   `HistoryFragment`; introduce `DashboardFragment`. Verify camera + alerts still work.
3. **Core tabs polish** — finalize Dashboard, Monitor, History (chart + restyled adapter),
   Account hub against the approved mockups.
4. **Auth & splash** — Login, Sign-up, Loading screen.
5. **Account sub-screens** — Profile; **merge** Settings + Sounds → Notifications & Sounds;
   User Management; Data & Privacy.
6. **Help & Legal consolidation** — one list screen + shared legal/info detail template;
   retire the 7 standalone legal/info layouts.
7. **Cleanup & QA** — remove dead layouts/hand-built nav code, guard Debug screen, full
   contrast/target/content-description pass, device QA.

---

## 9. Verification
- App **builds** and installs (`assembleDebug`) after each phase.
- **Manual QA on device/emulator** against each approved mockup.
- **Core loop intact:** start/stop monitoring, live camera + detection, alert logging, history
  render, login/sign-up, settings persistence (`PreferenceManager`).
- **Contrast audit** of final palette pairs (AA).
- **Navigation:** all four tabs, back behavior, and every Account sub-screen reachable.

---

## 10. Risks & the one decision to confirm
- **Fragment refactor of Monitor (risk: medium).** Moving the CameraX `PreviewView` +
  lifecycle into `MonitorFragment` is the main structural change. `CameraViewModel` already
  exists, so session state can survive tab switches, but camera start/stop must bind to the
  Fragment's `viewLifecycleOwner`. This is the one architectural choice worth a thumbs-up at
  spec review — the fallback (shared-nav Activities, §5.1) is lower-risk but noticeably worse UX.
- **Bundled fonts** add ~300–600KB to the APK (acceptable; ensures offline rendering).
- **Consolidating 7 legal screens** must preserve the exact legal text (content move, not rewrite).

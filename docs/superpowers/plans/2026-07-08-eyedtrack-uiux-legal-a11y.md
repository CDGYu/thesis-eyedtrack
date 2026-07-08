# EyedTrack UI/UX Overhaul — Plan 4: Legal/Info Screens + Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the seven legal/info screens (EULA, DPA, Data & Privacy, About Us, Terms & Conditions, FAQs, Help) onto the Signal design system, and apply the accessibility fixes logged during Plans 1–2.

**Scope note — Phase C is intentionally EXCLUDED.** Retiring the legacy Activities (HomePage / LiveFeed / AlertHistory / Settings) and deleting old layouts/colors is deferred until the new flow is device-verified. This plan is **non-destructive**: it only redesigns screens and adjusts styles. It does NOT delete any Activity or the legacy layouts. (The legacy nav references removed from these Activities here also unblock that future cleanup.)

**Architecture:** Same as Plan 3 — each screen stays an Activity, gets its layout rewritten to Signal + a minimal Activity edit that PRESERVES referenced view IDs and logic (drop the vestigial hand-built bottom nav + `FLAG_FULLSCREEN`, add the shared `@layout/include_top_bar`, `MaterialAlertDialogBuilder`).

**Tech Stack:** Kotlin, XML/Views, Material 3, the Signal foundation (Plan 1), `@layout/include_top_bar` (Plan 3).

## Global Constraints

_Every task's requirements implicitly include this section._

- XML/Views only; Material 3 (`material:1.11.0`); `compileSdk 34`/`minSdk 30`.
- **Build toolchain:** export `JAVA_HOME="/c/Users/user/android-build/jdk/jdk-17.0.19+10"` before Gradle. Gate: `./gradlew :app:assembleDebug --console=plain` → `BUILD SUCCESSFUL`.
- **Signal only** (`?attr/...` tokens, `@style/Widget.EyedTrack.*`, `@layout/include_top_bar`, `@drawable/ic_*`). **NO hardcoded hex, NO legacy `@color/purple_*`/`teal_*`.**
- **PRESERVE every view ID each Activity reads** (each task lists them); reuse Activity logic verbatim. Only the listed chrome edits (drop old bottom nav + FLAG_FULLSCREEN, wire the top bar, Material dialogs).
- **Do NOT delete any Activity or legacy layout** — Phase C is out of scope.
- **Commit policy:** NO per-task commits; ONE commit at the end. Branch `feat/uiux-overhaul-signal`.

**Shared "legal document" layout pattern** (Tasks 1–2 reuse this):
```
LinearLayout (?android:attr/colorBackground, vertical)
├── <include android:id="@+id/top_bar" layout="@layout/include_top_bar" />   (title set in code)
└── ScrollView (weight 1)
      └── the screen's content TextView(s) — PRESERVE their IDs — on ?attr/colorOnSurface,
          textAppearance ?attr/textAppearanceBodyLarge, padding @dimen/space_2xl
```

---

### Task 1: Static-text legal/info docs — EULA, DPA, Data & Privacy, About Us

**Files (4 layouts + 4 Activities):** `eula.xml`+`EulaActivity.kt`, `dpa.xml`+`DPAActivity.kt`, `data_privacy.xml`+`DataPrivacyActivity.kt`, `about_us.xml`+`AboutUsActivity.kt`.

**IDs to PRESERVE per screen (read each Activity to confirm):** EULA → `eula_text`; DPA → `dpa_text`; Data & Privacy → (its content TextView(s) — read the layout; the Activity only reads `back_button` + nav); About Us → (its content — same). All four also currently read `back_button`, `home_icon`, `profile_icon`, `settings_icon` (removed; see below).

- [ ] **Step 1: Rewrite each of the 4 layouts** to the shared legal-document pattern above. Keep the content TextView IDs (`eula_text`, `dpa_text`, and whatever About/Data-Privacy use). Replace all hardcoded hex (`#060644`, `#ADD8E6`, `#FFFFFF`, `@android:color/black`, etc.) with Signal tokens. Remove the navy header + hand-built bottom nav. For About Us, keep its logo/content structure but re-tokenize.
- [ ] **Step 2: Trim each of the 4 Activities.** For EULA/DPA/DataPrivacy/About: remove `FLAG_FULLSCREEN`; remove the `home_icon`/`profile_icon`/`settings_icon` lookups + listeners (delete the legacy-nav code — this also drops the `HomePageActivity`/`SettingsActivity`/`ProfileActivity` references); replace the `back_button` lookup with the top bar: `findViewById<android.view.View>(R.id.top_bar).findViewById<android.widget.ImageView>(R.id.btn_back).setOnClickListener { finish() }` and set `top_bar_title` (e.g. "EULA", "Data Processing Agreement", "Data & privacy", "About us"). Keep the text-population logic (whatever sets `eula_text`/`dpa_text` etc.) UNCHANGED.
- [ ] **Step 3: Build.** `assembleDebug` → `BUILD SUCCESSFUL`. Self-review: content IDs preserved; no hex; no legacy nav refs remain in these 4 Activities.

---

### Task 2: Terms & Conditions (acceptance gate)

**Files:** `terms_and_conditions.xml` + `TermsAndConditionsActivity.kt`.
**IDs to PRESERVE:** `btnAccept`, `btnReject` (this screen is the first-run T&C gate — it has Accept/Reject, NOT a bottom nav). Read the Activity first.

- [ ] **Step 1: Rewrite `terms_and_conditions.xml`** to Signal: `?android:attr/colorBackground`, a title (`?attr/textAppearanceHeadlineSmall`), a scrollable terms TextView (`?attr/colorOnSurface`), and two buttons — `btnAccept` `style="@style/Widget.EyedTrack.Button"` + `btnReject` `style="@style/Widget.EyedTrack.Button.Secondary"`. Preserve those two IDs. No hex. (This screen has no back bar — it's a gate; keep it self-contained.)
- [ ] **Step 2: Trim `TermsAndConditionsActivity.kt`.** Remove `FLAG_FULLSCREEN` if present. Keep the accept/reject logic (`PreferenceManager.setAccepted` + navigation) UNCHANGED.
- [ ] **Step 3: Build + self-review** (btnAccept/btnReject preserved, no hex).

---

### Task 3: FAQs (expandable Q&A)

**Files:** `faqs.xml` + `FAQsActivity.kt`.
**IDs to PRESERVE:** `question_1..6`, `answer_1..6`, `icon_1..6`, `back_button` (+ old nav `home_icon`/`profile_icon`/`settings_icon` → removed). Read the Activity — it wires 6 expand/collapse rows (tapping a question toggles its answer + rotates its icon).

- [ ] **Step 1: Rewrite `faqs.xml`** to Signal: `include_top_bar` + a scrolling list of 6 FAQ cards. Each card (`@style/Widget.EyedTrack.Card`): a question row (`question_N` TextView `?attr/colorOnSurface` + an `icon_N` expand chevron ImageView `@drawable/ic_chevron_right` tinted `?attr/colorOnSurfaceVariant`) and an `answer_N` TextView (`?attr/colorOnSurfaceVariant`, initially `visibility="gone"` as the current layout has it). Preserve ALL 18 IDs + `back_button`→top-bar. No hex.
- [ ] **Step 2: Trim `FAQsActivity.kt`.** Remove `FLAG_FULLSCREEN` + the 3 legacy nav lookups/listeners; wire the top bar (`btn_back`→finish, title "FAQs"). Keep the 6 expand/collapse toggle handlers UNCHANGED (they reference `question_N`/`answer_N`/`icon_N`).
- [ ] **Step 3: Build + self-review** (all 18 IDs preserved, expand logic intact, no hex).

---

### Task 4: Help (tutorial)

**Files:** `help.xml` + `HelpActivity.kt` (+ it uses `HelpAdapter`/`help_item.xml`).
**IDs to PRESERVE:** `viewPager`, `tabLayout`, `back_button` (+ old nav → removed). The Activity builds a 3-page ViewPager2 tutorial with dot indicators.

- [ ] **Step 1: Rewrite `help.xml`** to Signal: `include_top_bar` (title "Help") + intro text (`?attr/colorOnSurfaceVariant`) + the `viewPager` ViewPager2 + the `tabLayout` dot indicator (keep both IDs). `?android:attr/colorBackground`. Remove the navy header + bottom nav. No hex.
- [ ] **Step 2: Restyle `help_item.xml`** (the ViewPager page) to Signal: `@style/Widget.EyedTrack.Card`, `?attr/...` text colors, no hex. Preserve whatever IDs `HelpAdapter` binds (read `HelpAdapter.kt` first).
- [ ] **Step 3: Trim `HelpActivity.kt`.** Remove `FLAG_FULLSCREEN` + the 3 legacy nav lookups/listeners; wire the top bar (`btn_back`→finish). Keep the ViewPager/TabLayoutMediator/dot-swap logic UNCHANGED. (The `dot_selected`/`dot_unselected` drawables may be recolored to `?attr/colorPrimary`/`?attr/colorOutline` if they hardcode a color — check them.)
- [ ] **Step 4: Build + self-review** (viewPager/tabLayout preserved, tutorial intact, no hex).

---

### Task 5: Accessibility pass

**Files:** `res/values/styles.xml` (component styles), plus targeted layout/`contentDescription` fixes.

Addresses the AA items logged in Plans 1–2.

- [ ] **Step 1: Primary-button label contrast.** White on `blue_500` ≈ 3.7:1 fails AA for the 12sp `LabelLarge` button text. Fix in `@style/Widget.EyedTrack.Button`: set `android:textAppearance` to a 14sp label (create `TextAppearance.EyedTrack.Button` = Inter 700 / 14sp in `type.xml`, or override `android:textSize=14sp` + `android:textFontWeight=700` on the button style). At 14sp/700 the label qualifies as "large text" (AA 3:1), which the pairing passes. Rebuild.
- [ ] **Step 2: `text_lo` usage.** `text_lo` (#6B7A99) on surface ≈ 4.0:1 — acceptable for large/secondary but NOT normal-size essential text. Audit the new layouts (Plans 2–4) for `text_lo`/`?attr/colorOnSurfaceVariant` used as a primary/essential text color at body size; where found on essential content, switch to `?attr/colorOnSurface` or `text_mid`. (Muted/caption use is fine.)
- [ ] **Step 3: Content descriptions.** Add `android:contentDescription` to icon-only controls introduced in Plans 2–4 that lack one — e.g. `include_top_bar` back arrow (already "Back"), the bottom-nav items (titles provide labels), any icon `ImageView` in the fragments/rows. Confirm the camera `previewView` and status icons have descriptions.
- [ ] **Step 4: Build + self-review.** `assembleDebug` green; button text is 14sp/bold; no essential body text left on sub-AA colors; icon-only controls have descriptions.

---

## Self-Review

**1. Spec coverage (spec §5.2 legal consolidation + §7 accessibility):** the 7 legal/info screens → Tasks 1–4 (EULA/DPA/DataPrivacy/About, T&C, FAQs, Help) ✓; accessibility pass → Task 5 ✓. Legal screens are reached from the Account tab ("Data & privacy", "Help & legal") — those links (Plan 2) already point at `DataPrivacyActivity`/`HelpActivity`, which this plan redesigns. **Phase C (legacy Activity retirement) is explicitly deferred** to post-device-verification (documented in Scope note) — not a gap.

**2. Placeholder scan:** Each task names the exact IDs to preserve and the exact Activity edits. Where a screen's content IDs weren't pre-read (Data&Privacy/About content TextViews), the task instructs "read the Activity/layout first and preserve them" — an explicit action, not hand-waving.

**3. Consistency:** all screens reuse `@layout/include_top_bar` (`btn_back`/`top_bar_title`) wired identically; the "legal document" pattern is defined once and referenced. Accessibility fixes are centralized in the shared button style + a token audit.

---

## Execution Handoff

Subagent-driven, controller-side reviews (these are low-risk layout redesigns with preserved IDs — verify referential integrity per task like Plan 3), final Opus whole-branch review (dispatch a FRESH reviewer; if it returns non-review/injected content again, disregard and verify controller-side), then the SINGLE Plan 4 commit. Device-verify the legal links + T&C gate before the eventual Phase C cleanup.

# EyedTrack UI/UX Overhaul — Plan 1: Foundation (Design System) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the "Signal" design system as reusable Android resources (color tokens, bundled Sora/Inter fonts, Material 3 dark theme, type scale, component styles, and core icons) so every subsequent screen inherits it.

**Architecture:** Pure Android resource layer — no Kotlin/logic changes and no screen restructuring in this plan. We swap the base theme from `Theme.MaterialComponents.DayNight` to `Theme.Material3.DayNight`, add a token + component-style system, and bundle fonts. Existing screens keep building (old color names are retained) and simply start inheriting the new theme; they are redesigned in later plans.

**Tech Stack:** Android XML resources, Material Components for Android 1.11.0 (Material 3), Sora + Inter (OFL fonts), Gradle (Kotlin DSL).

## Global Constraints

_Every task's requirements implicitly include this section._

- **UI stack:** XML/Views only. No Jetpack Compose.
- **SDK:** `compileSdk 34`, `minSdk 30`, `targetSdk 34`. All APIs used must be ≤ 30 (e.g. `app:fontWeight` font families, `android:textFontWeight` are fine on 30).
- **Dependency floor:** `com.google.android.material:material:1.11.0` — already present. Do **not** add a charting or other UI dependency.
- **Theme mode:** Dark-first, single theme. `values/themes.xml` and `values-night/themes.xml` are identical.
- **Theme name stays `Theme.EyeDTrack`** (referenced by `AndroidManifest.xml`) — do not rename.
- **Exact color tokens (verbatim):** `ink_900 #0A0F1C`, `ink_800 #111A2D`, `ink_700 #18233A`, `ink_600 #1F2C48`, `ink_500 #2A3654`, `ink_400 #3A4A70`, `blue_500 #3D7EFF`, `blue_400 #5A93FF`, `blue_600 #2E63D6`, `blue_container #16294D`, `green_500 #22C55E`, `green_container #10321F`, `amber_500 #F59E0B`, `amber_container #3A2A0A`, `red_500 #EF4444`, `red_container #3A1414`, `text_hi #F1F5F9`, `text_mid #A9B6CE`, `text_lo #6B7A99`.
- **Fonts:** Sora (500/600/700/800) + Inter (400/500/600/700), **bundled** as static TTFs in `res/font/` (not downloadable fonts).
- **Backwards compatibility:** Retain the existing `@color/red`, `@color/green`, `@color/yellow`, `@color/white`, `@color/black`, `@color/purple_*`, `@color/teal_*` entries so current layouts keep compiling. They are removed in Plan 4 (cleanup).
- **Branch:** `feat/uiux-overhaul-signal`.
- **Build/verify command (Git Bash):** `./gradlew :app:assembleDebug` (PowerShell: `.\gradlew.bat :app:assembleDebug`). A task is "green" when this exits 0.

---

## File Structure

Files created or modified in this plan (all under `app/src/main/`):

- `res/values/colors.xml` — **modify**: append Signal primitive tokens (keep existing).
- `res/values/attrs.xml` — **create**: custom safety theme attributes.
- `res/values/dimens.xml` — **create**: spacing / radius / touch tokens.
- `res/values/type.xml` — **create**: `TextAppearance.EyedTrack.*` styles.
- `res/values/styles.xml` — **create**: shape appearances + `Widget.EyedTrack.*` component styles.
- `res/values/themes.xml` — **modify**: rebase to Material 3, map tokens/type/shape/components/system bars.
- `res/values-night/themes.xml` — **modify**: mirror the dark theme (identical).
- `res/font/inter.xml`, `res/font/sora.xml` — **create**: bundled font families.
- `res/font/inter_regular.ttf` … `sora_extrabold.ttf` — **add**: 8 static TTF assets.
- `res/drawable/pill_safe.xml`, `pill_caution.xml`, `pill_alert.xml`, `pill_idle.xml` — **create**: status-pill backgrounds.
- `res/drawable/ic_nav_dashboard.xml`, `ic_nav_monitor.xml`, `ic_nav_history.xml`, `ic_nav_account.xml`, `ic_logo_eye.xml`, `ic_chevron_right.xml` — **create**: core vector icons.

**Verification note (read once):** This plan is a resource/theme layer with no branchable logic, so there is nothing to unit-test TDD-style. The per-task gate is a successful `assembleDebug` plus the specific inspection named in the task. Real JUnit/Espresso tests begin in Plan 2 where logic (navigation, dashboard aggregation, trend chart) is introduced.

---

### Task 1: Bundle Sora + Inter fonts

**Files:**
- Add: `app/src/main/res/font/inter_regular.ttf`, `inter_medium.ttf`, `inter_semibold.ttf`, `inter_bold.ttf`, `sora_medium.ttf`, `sora_semibold.ttf`, `sora_bold.ttf`, `sora_extrabold.ttf`
- Create: `app/src/main/res/font/inter.xml`, `app/src/main/res/font/sora.xml`

**Interfaces:**
- Produces: font families `@font/inter` (weights 400/500/600/700) and `@font/sora` (weights 500/600/700/800), consumed by the theme (Task 5) and type styles (Task 4).

- [ ] **Step 1: Obtain the TTF assets**

Download the static weights (OFL license) and place them in `app/src/main/res/font/` with these **exact lowercase names** (Android font resource names must be lowercase, letters/digits/underscore only):

| Source family | Weight | Target filename |
|---|---|---|
| Inter | Regular 400 | `inter_regular.ttf` |
| Inter | Medium 500 | `inter_medium.ttf` |
| Inter | SemiBold 600 | `inter_semibold.ttf` |
| Inter | Bold 700 | `inter_bold.ttf` |
| Sora | Medium 500 | `sora_medium.ttf` |
| Sora | SemiBold 600 | `sora_semibold.ttf` |
| Sora | Bold 700 | `sora_bold.ttf` |
| Sora | ExtraBold 800 | `sora_extrabold.ttf` |

Get them from Google Fonts ("Download family" → the ZIP contains a `static/` folder with per-weight TTFs): Sora → https://fonts.google.com/specimen/Sora , Inter → https://fonts.google.com/specimen/Inter . Newer Inter ZIPs name files like `Inter_18pt-Regular.ttf`; use the `18pt` (default optical size) static weights and rename to the targets above.

- [ ] **Step 2: Create the Inter font family**

`app/src/main/res/font/inter.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<font-family xmlns:app="http://schemas.android.com/apk/res-auto">
    <font app:fontStyle="normal" app:fontWeight="400" app:font="@font/inter_regular" />
    <font app:fontStyle="normal" app:fontWeight="500" app:font="@font/inter_medium" />
    <font app:fontStyle="normal" app:fontWeight="600" app:font="@font/inter_semibold" />
    <font app:fontStyle="normal" app:fontWeight="700" app:font="@font/inter_bold" />
</font-family>
```

- [ ] **Step 3: Create the Sora font family**

`app/src/main/res/font/sora.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<font-family xmlns:app="http://schemas.android.com/apk/res-auto">
    <font app:fontStyle="normal" app:fontWeight="500" app:font="@font/sora_medium" />
    <font app:fontStyle="normal" app:fontWeight="600" app:font="@font/sora_semibold" />
    <font app:fontStyle="normal" app:fontWeight="700" app:font="@font/sora_bold" />
    <font app:fontStyle="normal" app:fontWeight="800" app:font="@font/sora_extrabold" />
</font-family>
```

- [ ] **Step 4: Build to verify the font resources compile**

Run: `./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`. (A missing/misnamed TTF fails with `resource font/… not found` — fix the filename.)

- [ ] **Step 5: Commit**

```bash
git add app/src/main/res/font/
git commit -m "feat(ui): bundle Sora + Inter font families"
```

---

### Task 2: Color tokens + safety attributes

**Files:**
- Modify: `app/src/main/res/values/colors.xml`
- Create: `app/src/main/res/values/attrs.xml`

**Interfaces:**
- Produces: color resources `@color/ink_900…ink_400`, `@color/blue_500/400/600`, `@color/blue_container`, `@color/green_500`, `@color/green_container`, `@color/amber_500`, `@color/amber_container`, `@color/red_500`, `@color/red_container`, `@color/text_hi/mid/lo`; and theme attrs `?attr/stateSafe`, `?attr/stateSafeContainer`, `?attr/stateCaution`, `?attr/stateCautionContainer`, `?attr/stateAlert`, `?attr/stateAlertContainer`. Consumed by theme (Task 5), styles (Task 6), drawables (Task 7), and all later plans.

- [ ] **Step 1: Append Signal tokens to `colors.xml`**

Replace the entire contents of `app/src/main/res/values/colors.xml` with (existing names retained at bottom for compatibility):

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- ===== Signal primitives — surfaces ===== -->
    <color name="ink_900">#FF0A0F1C</color>
    <color name="ink_800">#FF111A2D</color>
    <color name="ink_700">#FF18233A</color>
    <color name="ink_600">#FF1F2C48</color>
    <color name="ink_500">#FF2A3654</color>
    <color name="ink_400">#FF3A4A70</color>

    <!-- ===== Signal primitives — primary ===== -->
    <color name="blue_500">#FF3D7EFF</color>
    <color name="blue_400">#FF5A93FF</color>
    <color name="blue_600">#FF2E63D6</color>
    <color name="blue_container">#FF16294D</color>

    <!-- ===== Signal primitives — safety states ===== -->
    <color name="green_500">#FF22C55E</color>
    <color name="green_container">#FF10321F</color>
    <color name="amber_500">#FFF59E0B</color>
    <color name="amber_container">#FF3A2A0A</color>
    <color name="red_500">#FFEF4444</color>
    <color name="red_container">#FF3A1414</color>

    <!-- ===== Signal primitives — text ===== -->
    <color name="text_hi">#FFF1F5F9</color>
    <color name="text_mid">#FFA9B6CE</color>
    <color name="text_lo">#FF6B7A99</color>

    <!-- ===== Legacy (retained until Plan 4 cleanup) ===== -->
    <color name="purple_200">#FFBB86FC</color>
    <color name="purple_500">#FF6200EE</color>
    <color name="purple_700">#FF3700B3</color>
    <color name="teal_200">#FF03DAC5</color>
    <color name="teal_700">#FF018786</color>
    <color name="black">#FF000000</color>
    <color name="white">#FFFFFFFF</color>
    <color name="red">#FFF44336</color>
    <color name="green">#FF4CAF50</color>
    <color name="yellow">#FFFFC107</color>
</resources>
```

- [ ] **Step 2: Create `attrs.xml` with safety attributes**

`app/src/main/res/values/attrs.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Safety-state color slots (Material 3 has no caution/safe roles) -->
    <attr name="stateSafe" format="color" />
    <attr name="stateSafeContainer" format="color" />
    <attr name="stateCaution" format="color" />
    <attr name="stateCautionContainer" format="color" />
    <attr name="stateAlert" format="color" />
    <attr name="stateAlertContainer" format="color" />
</resources>
```

- [ ] **Step 3: Build to verify**

Run: `./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
git add app/src/main/res/values/colors.xml app/src/main/res/values/attrs.xml
git commit -m "feat(ui): add Signal color tokens and safety-state attributes"
```

---

### Task 3: Spacing, radius, and shape tokens

**Files:**
- Create: `app/src/main/res/values/dimens.xml`
- Create: `app/src/main/res/values/styles.xml` (shape appearances only in this task; component styles appended in Task 6)

**Interfaces:**
- Produces: dimens `@dimen/space_xs…space_3xl`, `@dimen/radius_sm…radius_xl`, `@dimen/touch_min`; shape styles `ShapeAppearance.EyedTrack.Small/Medium/Large`. Consumed by theme (Task 5) and component styles (Task 6).

- [ ] **Step 1: Create `dimens.xml`**

`app/src/main/res/values/dimens.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- 8pt spacing scale -->
    <dimen name="space_xs">4dp</dimen>
    <dimen name="space_sm">8dp</dimen>
    <dimen name="space_md">12dp</dimen>
    <dimen name="space_lg">16dp</dimen>
    <dimen name="space_xl">20dp</dimen>
    <dimen name="space_2xl">24dp</dimen>
    <dimen name="space_3xl">32dp</dimen>

    <!-- radius scale -->
    <dimen name="radius_sm">8dp</dimen>
    <dimen name="radius_md">12dp</dimen>
    <dimen name="radius_lg">16dp</dimen>
    <dimen name="radius_xl">20dp</dimen>

    <!-- component sizing -->
    <dimen name="touch_min">48dp</dimen>
    <dimen name="button_height">52dp</dimen>
</resources>
```

- [ ] **Step 2: Create `styles.xml` with shape appearances**

`app/src/main/res/values/styles.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>

    <!-- ===== Shape appearances ===== -->
    <style name="ShapeAppearance.EyedTrack.Small" parent="ShapeAppearance.Material3.SmallComponent">
        <item name="cornerFamily">rounded</item>
        <item name="cornerSize">@dimen/radius_sm</item>
    </style>

    <style name="ShapeAppearance.EyedTrack.Medium" parent="ShapeAppearance.Material3.MediumComponent">
        <item name="cornerFamily">rounded</item>
        <item name="cornerSize">@dimen/radius_md</item>
    </style>

    <style name="ShapeAppearance.EyedTrack.Large" parent="ShapeAppearance.Material3.LargeComponent">
        <item name="cornerFamily">rounded</item>
        <item name="cornerSize">@dimen/radius_lg</item>
    </style>

    <!-- Widget.EyedTrack.* component styles are appended in Task 6 -->
</resources>
```

- [ ] **Step 3: Build to verify**

Run: `./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 4: Commit**

```bash
git add app/src/main/res/values/dimens.xml app/src/main/res/values/styles.xml
git commit -m "feat(ui): add spacing, radius, and shape tokens"
```

---

### Task 4: Typography styles

**Files:**
- Create: `app/src/main/res/values/type.xml`

**Interfaces:**
- Consumes: `@font/sora`, `@font/inter` (Task 1).
- Produces: `TextAppearance.EyedTrack.Display`, `.Headline`, `.TitleLarge`, `.TitleMedium`, `.BodyLarge`, `.BodyMedium`, `.LabelLarge`, `.LabelSmall`. Consumed by the theme (Task 5).

- [ ] **Step 1: Create `type.xml`**

`app/src/main/res/values/type.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Display — Sora 800 / 28sp -->
    <style name="TextAppearance.EyedTrack.Display" parent="TextAppearance.Material3.DisplaySmall">
        <item name="fontFamily">@font/sora</item>
        <item name="android:fontFamily">@font/sora</item>
        <item name="android:textFontWeight">800</item>
        <item name="android:textSize">28sp</item>
    </style>

    <!-- Headline / H1 — Sora 700 / 24sp -->
    <style name="TextAppearance.EyedTrack.Headline" parent="TextAppearance.Material3.HeadlineSmall">
        <item name="fontFamily">@font/sora</item>
        <item name="android:fontFamily">@font/sora</item>
        <item name="android:textFontWeight">700</item>
        <item name="android:textSize">24sp</item>
    </style>

    <!-- Title Large / H2 — Sora 600 / 20sp -->
    <style name="TextAppearance.EyedTrack.TitleLarge" parent="TextAppearance.Material3.TitleLarge">
        <item name="fontFamily">@font/sora</item>
        <item name="android:fontFamily">@font/sora</item>
        <item name="android:textFontWeight">600</item>
        <item name="android:textSize">20sp</item>
    </style>

    <!-- Title Medium — Inter 600 / 16sp -->
    <style name="TextAppearance.EyedTrack.TitleMedium" parent="TextAppearance.Material3.TitleMedium">
        <item name="fontFamily">@font/inter</item>
        <item name="android:fontFamily">@font/inter</item>
        <item name="android:textFontWeight">600</item>
        <item name="android:textSize">16sp</item>
    </style>

    <!-- Body Large — Inter 400 / 15sp -->
    <style name="TextAppearance.EyedTrack.BodyLarge" parent="TextAppearance.Material3.BodyLarge">
        <item name="fontFamily">@font/inter</item>
        <item name="android:fontFamily">@font/inter</item>
        <item name="android:textFontWeight">400</item>
        <item name="android:textSize">15sp</item>
    </style>

    <!-- Body Medium — Inter 400 / 13sp -->
    <style name="TextAppearance.EyedTrack.BodyMedium" parent="TextAppearance.Material3.BodyMedium">
        <item name="fontFamily">@font/inter</item>
        <item name="android:fontFamily">@font/inter</item>
        <item name="android:textFontWeight">400</item>
        <item name="android:textSize">13sp</item>
    </style>

    <!-- Label Large — Inter 600 / 12sp -->
    <style name="TextAppearance.EyedTrack.LabelLarge" parent="TextAppearance.Material3.LabelLarge">
        <item name="fontFamily">@font/inter</item>
        <item name="android:fontFamily">@font/inter</item>
        <item name="android:textFontWeight">600</item>
        <item name="android:textSize">12sp</item>
    </style>

    <!-- Label Small / Caption — Inter 500 / 11sp -->
    <style name="TextAppearance.EyedTrack.LabelSmall" parent="TextAppearance.Material3.LabelSmall">
        <item name="fontFamily">@font/inter</item>
        <item name="android:fontFamily">@font/inter</item>
        <item name="android:textFontWeight">500</item>
        <item name="android:textSize">11sp</item>
    </style>
</resources>
```

- [ ] **Step 2: Build to verify**

Run: `./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 3: Commit**

```bash
git add app/src/main/res/values/type.xml
git commit -m "feat(ui): add Sora/Inter type scale text appearances"
```

---

### Task 5: Material 3 dark theme

**Files:**
- Modify: `app/src/main/res/values/themes.xml`
- Modify: `app/src/main/res/values-night/themes.xml`

**Interfaces:**
- Consumes: all color tokens (Task 2), safety attrs (Task 2), dimens/shapes (Task 3), type styles (Task 4), fonts (Task 1), and component styles `@style/Widget.EyedTrack.Button` / `@style/Widget.EyedTrack.BottomNav` (Task 6 — forward reference; Task 6 must land before a device run, but the theme compiles once those styles exist, so **do Task 6 before Step 2's build if implementing strictly in order… however to keep tasks independent, this task references them and Task 6 defines them; run the build gate at the end of Task 6**).
- Produces: `Theme.EyeDTrack` (Material 3 dark) applied app-wide via the manifest.

> **Ordering note:** Task 5 and Task 6 are mutually referential (theme sets default widget styles; styles use theme attrs). Implement Task 5 Steps 1 & 3 (write both theme files), then Task 6, then run the shared build gate at Task 6 Step 3. That is the single reviewable "theme + components" boundary.

- [ ] **Step 1: Rewrite `values/themes.xml`**

Replace the entire contents of `app/src/main/res/values/themes.xml` with:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:tools="http://schemas.android.com/tools">

    <style name="Theme.EyeDTrack" parent="Theme.Material3.DayNight.NoActionBar">
        <!-- Primary -->
        <item name="colorPrimary">@color/blue_500</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorPrimaryContainer">@color/blue_container</item>
        <item name="colorOnPrimaryContainer">@color/blue_400</item>
        <item name="colorSecondary">@color/blue_400</item>
        <item name="colorOnSecondary">@color/white</item>

        <!-- Surfaces / background -->
        <item name="android:colorBackground">@color/ink_900</item>
        <item name="colorSurface">@color/ink_800</item>
        <item name="colorSurfaceContainerLow">@color/ink_800</item>
        <item name="colorSurfaceContainer">@color/ink_700</item>
        <item name="colorSurfaceContainerHigh">@color/ink_600</item>
        <item name="colorOnSurface">@color/text_hi</item>
        <item name="colorOnSurfaceVariant">@color/text_mid</item>
        <item name="colorOutline">@color/ink_500</item>
        <item name="colorOutlineVariant">@color/ink_400</item>

        <!-- Error -->
        <item name="colorError">@color/red_500</item>
        <item name="colorOnError">@color/white</item>

        <!-- Custom safety-state slots -->
        <item name="stateSafe">@color/green_500</item>
        <item name="stateSafeContainer">@color/green_container</item>
        <item name="stateCaution">@color/amber_500</item>
        <item name="stateCautionContainer">@color/amber_container</item>
        <item name="stateAlert">@color/red_500</item>
        <item name="stateAlertContainer">@color/red_container</item>

        <!-- Shapes -->
        <item name="shapeAppearanceSmallComponent">@style/ShapeAppearance.EyedTrack.Small</item>
        <item name="shapeAppearanceMediumComponent">@style/ShapeAppearance.EyedTrack.Medium</item>
        <item name="shapeAppearanceLargeComponent">@style/ShapeAppearance.EyedTrack.Large</item>

        <!-- Typography -->
        <item name="android:fontFamily">@font/inter</item>
        <item name="fontFamily">@font/inter</item>
        <item name="textAppearanceDisplaySmall">@style/TextAppearance.EyedTrack.Display</item>
        <item name="textAppearanceHeadlineSmall">@style/TextAppearance.EyedTrack.Headline</item>
        <item name="textAppearanceTitleLarge">@style/TextAppearance.EyedTrack.TitleLarge</item>
        <item name="textAppearanceTitleMedium">@style/TextAppearance.EyedTrack.TitleMedium</item>
        <item name="textAppearanceBodyLarge">@style/TextAppearance.EyedTrack.BodyLarge</item>
        <item name="textAppearanceBodyMedium">@style/TextAppearance.EyedTrack.BodyMedium</item>
        <item name="textAppearanceLabelLarge">@style/TextAppearance.EyedTrack.LabelLarge</item>
        <item name="textAppearanceLabelSmall">@style/TextAppearance.EyedTrack.LabelSmall</item>

        <!-- Default component styles -->
        <item name="materialButtonStyle">@style/Widget.EyedTrack.Button</item>
        <item name="bottomNavigationStyle">@style/Widget.EyedTrack.BottomNav</item>

        <!-- System bars -->
        <item name="android:statusBarColor">@color/ink_900</item>
        <item name="android:navigationBarColor">@color/ink_900</item>
        <item name="android:windowLightStatusBar">false</item>
        <item name="android:windowLightNavigationBar">false</item>
    </style>

    <!-- Alert dialog styling (preserved, retargeted to Material 3) -->
    <style name="CustomAlertDialog" parent="ThemeOverlay.Material3.MaterialAlertDialog">
        <item name="buttonBarPositiveButtonStyle">@style/PositiveButtonStyle</item>
        <item name="buttonBarNegativeButtonStyle">@style/NegativeButtonStyle</item>
    </style>

    <style name="PositiveButtonStyle" parent="Widget.Material3.Button.TextButton.Dialog">
        <item name="android:textColor">@color/blue_400</item>
    </style>

    <style name="NegativeButtonStyle" parent="Widget.Material3.Button.TextButton.Dialog">
        <item name="android:textColor">@color/text_lo</item>
    </style>
</resources>
```

- [ ] **Step 2: (deferred build)** — build gate runs at the end of Task 6, since `Theme.EyeDTrack` references `Widget.EyedTrack.Button`/`Widget.EyedTrack.BottomNav` defined there.

- [ ] **Step 3: Mirror the dark theme in `values-night/themes.xml`**

Replace the entire contents of `app/src/main/res/values-night/themes.xml` with the **identical** theme body (dark-first, single theme):

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:tools="http://schemas.android.com/tools">

    <style name="Theme.EyeDTrack" parent="Theme.Material3.DayNight.NoActionBar">
        <item name="colorPrimary">@color/blue_500</item>
        <item name="colorOnPrimary">@color/white</item>
        <item name="colorPrimaryContainer">@color/blue_container</item>
        <item name="colorOnPrimaryContainer">@color/blue_400</item>
        <item name="colorSecondary">@color/blue_400</item>
        <item name="colorOnSecondary">@color/white</item>
        <item name="android:colorBackground">@color/ink_900</item>
        <item name="colorSurface">@color/ink_800</item>
        <item name="colorSurfaceContainerLow">@color/ink_800</item>
        <item name="colorSurfaceContainer">@color/ink_700</item>
        <item name="colorSurfaceContainerHigh">@color/ink_600</item>
        <item name="colorOnSurface">@color/text_hi</item>
        <item name="colorOnSurfaceVariant">@color/text_mid</item>
        <item name="colorOutline">@color/ink_500</item>
        <item name="colorOutlineVariant">@color/ink_400</item>
        <item name="colorError">@color/red_500</item>
        <item name="colorOnError">@color/white</item>
        <item name="stateSafe">@color/green_500</item>
        <item name="stateSafeContainer">@color/green_container</item>
        <item name="stateCaution">@color/amber_500</item>
        <item name="stateCautionContainer">@color/amber_container</item>
        <item name="stateAlert">@color/red_500</item>
        <item name="stateAlertContainer">@color/red_container</item>
        <item name="shapeAppearanceSmallComponent">@style/ShapeAppearance.EyedTrack.Small</item>
        <item name="shapeAppearanceMediumComponent">@style/ShapeAppearance.EyedTrack.Medium</item>
        <item name="shapeAppearanceLargeComponent">@style/ShapeAppearance.EyedTrack.Large</item>
        <item name="android:fontFamily">@font/inter</item>
        <item name="fontFamily">@font/inter</item>
        <item name="textAppearanceDisplaySmall">@style/TextAppearance.EyedTrack.Display</item>
        <item name="textAppearanceHeadlineSmall">@style/TextAppearance.EyedTrack.Headline</item>
        <item name="textAppearanceTitleLarge">@style/TextAppearance.EyedTrack.TitleLarge</item>
        <item name="textAppearanceTitleMedium">@style/TextAppearance.EyedTrack.TitleMedium</item>
        <item name="textAppearanceBodyLarge">@style/TextAppearance.EyedTrack.BodyLarge</item>
        <item name="textAppearanceBodyMedium">@style/TextAppearance.EyedTrack.BodyMedium</item>
        <item name="textAppearanceLabelLarge">@style/TextAppearance.EyedTrack.LabelLarge</item>
        <item name="textAppearanceLabelSmall">@style/TextAppearance.EyedTrack.LabelSmall</item>
        <item name="materialButtonStyle">@style/Widget.EyedTrack.Button</item>
        <item name="bottomNavigationStyle">@style/Widget.EyedTrack.BottomNav</item>
        <item name="android:statusBarColor">@color/ink_900</item>
        <item name="android:navigationBarColor">@color/ink_900</item>
        <item name="android:windowLightStatusBar">false</item>
        <item name="android:windowLightNavigationBar">false</item>
    </style>
</resources>
```

- [ ] **Step 4: Commit** (after Task 6's build gate passes — see Task 6 Step 4)

---

### Task 6: Component styles + status-pill drawables

**Files:**
- Modify: `app/src/main/res/values/styles.xml` (append `Widget.EyedTrack.*`)
- Create: `app/src/main/res/drawable/pill_safe.xml`, `pill_caution.xml`, `pill_alert.xml`, `pill_idle.xml`

**Interfaces:**
- Consumes: theme attrs + tokens (Tasks 2, 5), dimens/shapes (Task 3), type styles (Task 4).
- Produces: `Widget.EyedTrack.Button`, `.Button.Secondary`, `.Button.Text`, `.Button.Danger`, `.TextField`, `.Card`, `.BottomNav`, `.Switch`, `.Slider`; drawables `@drawable/pill_safe/caution/alert/idle`. Consumed by every screen in Plans 2–4.

- [ ] **Step 1: Append component styles to `styles.xml`**

Insert these styles into `app/src/main/res/values/styles.xml` before the closing `</resources>`:

```xml
    <!-- ===== Buttons ===== -->
    <style name="Widget.EyedTrack.Button" parent="Widget.Material3.Button">
        <item name="android:minHeight">@dimen/button_height</item>
        <item name="cornerRadius">@dimen/radius_md</item>
        <item name="backgroundTint">?attr/colorPrimary</item>
        <item name="android:textColor">?attr/colorOnPrimary</item>
        <item name="android:textAppearance">@style/TextAppearance.EyedTrack.LabelLarge</item>
        <item name="android:textAllCaps">false</item>
    </style>

    <style name="Widget.EyedTrack.Button.Secondary" parent="Widget.Material3.Button.OutlinedButton">
        <item name="android:minHeight">@dimen/button_height</item>
        <item name="cornerRadius">@dimen/radius_md</item>
        <item name="strokeColor">?attr/colorOutlineVariant</item>
        <item name="android:textColor">@color/blue_400</item>
        <item name="android:textAllCaps">false</item>
    </style>

    <style name="Widget.EyedTrack.Button.Text" parent="Widget.Material3.Button.TextButton">
        <item name="android:textColor">@color/blue_400</item>
        <item name="android:textAllCaps">false</item>
    </style>

    <style name="Widget.EyedTrack.Button.Danger" parent="Widget.EyedTrack.Button">
        <item name="backgroundTint">?attr/colorError</item>
        <item name="android:textColor">?attr/colorOnError</item>
    </style>

    <!-- ===== Text field ===== -->
    <style name="Widget.EyedTrack.TextField" parent="Widget.Material3.TextInputLayout.OutlinedBox">
        <item name="boxBackgroundColor">@color/ink_700</item>
        <item name="boxStrokeColor">@color/blue_500</item>
        <item name="boxCornerRadiusTopStart">@dimen/radius_md</item>
        <item name="boxCornerRadiusTopEnd">@dimen/radius_md</item>
        <item name="boxCornerRadiusBottomStart">@dimen/radius_md</item>
        <item name="boxCornerRadiusBottomEnd">@dimen/radius_md</item>
        <item name="hintTextColor">@color/text_mid</item>
    </style>

    <!-- ===== Card ===== -->
    <style name="Widget.EyedTrack.Card" parent="Widget.Material3.CardView.Elevated">
        <item name="cardBackgroundColor">?attr/colorSurface</item>
        <item name="strokeColor">?attr/colorOutline</item>
        <item name="strokeWidth">1dp</item>
        <item name="cardCornerRadius">@dimen/radius_lg</item>
        <item name="cardElevation">0dp</item>
        <item name="contentPadding">@dimen/space_lg</item>
    </style>

    <!-- ===== Bottom navigation ===== -->
    <style name="Widget.EyedTrack.BottomNav" parent="Widget.Material3.BottomNavigationView">
        <item name="backgroundTint">?attr/colorSurface</item>
        <item name="itemActiveIndicatorStyle">@style/Widget.EyedTrack.BottomNav.Indicator</item>
        <item name="itemTextAppearanceActive">@style/TextAppearance.EyedTrack.LabelSmall</item>
        <item name="itemTextAppearanceInactive">@style/TextAppearance.EyedTrack.LabelSmall</item>
    </style>

    <style name="Widget.EyedTrack.BottomNav.Indicator" parent="Widget.Material3.BottomNavigationView.ActiveIndicator">
        <item name="android:color">@color/blue_container</item>
    </style>

    <!-- ===== Switch ===== -->
    <style name="Widget.EyedTrack.Switch" parent="Widget.Material3.CompoundButton.MaterialSwitch" />

    <!-- ===== Slider ===== -->
    <style name="Widget.EyedTrack.Slider" parent="Widget.Material3.Slider" />
```

- [ ] **Step 2: Create the four status-pill drawables**

`app/src/main/res/drawable/pill_safe.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/green_container" />
    <corners android:radius="999dp" />
</shape>
```

`app/src/main/res/drawable/pill_caution.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/amber_container" />
    <corners android:radius="999dp" />
</shape>
```

`app/src/main/res/drawable/pill_alert.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/red_container" />
    <corners android:radius="999dp" />
</shape>
```

`app/src/main/res/drawable/pill_idle.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="@color/ink_700" />
    <corners android:radius="999dp" />
</shape>
```

- [ ] **Step 3: Build to verify the whole theme + component layer compiles**

Run: `./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`. This is the shared gate for Tasks 5 and 6. If it fails with `resource style/Widget.EyedTrack.* not found`, a style name is misspelled relative to the theme's `materialButtonStyle`/`bottomNavigationStyle` references.

- [ ] **Step 4: Commit the theme + components together**

```bash
git add app/src/main/res/values/themes.xml app/src/main/res/values-night/themes.xml app/src/main/res/values/styles.xml app/src/main/res/drawable/pill_safe.xml app/src/main/res/drawable/pill_caution.xml app/src/main/res/drawable/pill_alert.xml app/src/main/res/drawable/pill_idle.xml
git commit -m "feat(ui): Material 3 dark theme + EyedTrack component styles"
```

- [ ] **Step 5: Manual smoke check (device/emulator)**

Install and launch: `./gradlew :app:installDebug` then open the app. Expected: existing screens now render on a dark background with the new status-bar color; default buttons appear electric-blue with rounded corners; text renders in Inter. (Layouts are still the old structure — that's expected; screens are redesigned in Plan 2+.)

---

### Task 7: Core vector icons

**Files:**
- Create: `app/src/main/res/drawable/ic_nav_dashboard.xml`, `ic_nav_monitor.xml`, `ic_nav_history.xml`, `ic_nav_account.xml`, `ic_logo_eye.xml`, `ic_chevron_right.xml`

**Interfaces:**
- Produces: `@drawable/ic_nav_dashboard`, `@drawable/ic_nav_monitor`, `@drawable/ic_nav_history`, `@drawable/ic_nav_account`, `@drawable/ic_logo_eye`, `@drawable/ic_chevron_right`. Consumed by the bottom-nav menu and screens in Plans 2–4. All are line icons (stroke, transparent fill) tinted at usage via `itemIconTint` / `app:tint`.

- [ ] **Step 1: Dashboard icon**

`app/src/main/res/drawable/ic_nav_dashboard.xml`:

```xml
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="@color/text_hi" android:strokeWidth="1.9"
        android:fillColor="#00000000"
        android:pathData="M4,4h6v6h-6z M14,4h6v6h-6z M4,14h6v6h-6z M14,14h6v6h-6z" />
</vector>
```

- [ ] **Step 2: Monitor (eye) icon**

`app/src/main/res/drawable/ic_nav_monitor.xml`:

```xml
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="@color/text_hi" android:strokeWidth="1.9"
        android:fillColor="#00000000"
        android:pathData="M2,12 C4.5,8 8,5 12,5 C16,5 19.5,8 22,12 C19.5,16 16,19 12,19 C8,19 4.5,16 2,12 Z" />
    <path android:strokeColor="@color/text_hi" android:strokeWidth="1.9"
        android:fillColor="#00000000"
        android:pathData="M9,12 a3,3 0 1,0 6,0 a3,3 0 1,0 -6,0" />
</vector>
```

- [ ] **Step 3: History (clock) icon**

`app/src/main/res/drawable/ic_nav_history.xml`:

```xml
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="@color/text_hi" android:strokeWidth="1.9"
        android:fillColor="#00000000"
        android:pathData="M3,12 a9,9 0 1,0 18,0 a9,9 0 1,0 -18,0" />
    <path android:strokeColor="@color/text_hi" android:strokeWidth="1.9"
        android:fillColor="#00000000" android:strokeLineCap="round"
        android:pathData="M12,7 v5 l3,2" />
</vector>
```

- [ ] **Step 4: Account (person) icon**

`app/src/main/res/drawable/ic_nav_account.xml`:

```xml
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="@color/text_hi" android:strokeWidth="1.9"
        android:fillColor="#00000000"
        android:pathData="M8,8 a4,4 0 1,0 8,0 a4,4 0 1,0 -8,0" />
    <path android:strokeColor="@color/text_hi" android:strokeWidth="1.9"
        android:fillColor="#00000000" android:strokeLineCap="round"
        android:pathData="M4,21 C4,17 7.5,15 12,15 C16.5,15 20,17 20,21" />
</vector>
```

- [ ] **Step 5: Logo eye mark**

`app/src/main/res/drawable/ic_logo_eye.xml`:

```xml
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="30dp" android:height="30dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="@color/white" android:strokeWidth="2"
        android:fillColor="#00000000"
        android:pathData="M2,12 C4.5,8 8,5 12,5 C16,5 19.5,8 22,12 C19.5,16 16,19 12,19 C8,19 4.5,16 2,12 Z" />
    <path android:strokeColor="@color/white" android:strokeWidth="2"
        android:fillColor="#00000000"
        android:pathData="M9,12 a3,3 0 1,0 6,0 a3,3 0 1,0 -6,0" />
</vector>
```

- [ ] **Step 6: Chevron-right icon**

`app/src/main/res/drawable/ic_chevron_right.xml`:

```xml
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="@color/text_lo" android:strokeWidth="2"
        android:fillColor="#00000000"
        android:strokeLineCap="round" android:strokeLineJoin="round"
        android:pathData="M9,6 l6,6 -6,6" />
</vector>
```

- [ ] **Step 7: Build to verify**

Run: `./gradlew :app:assembleDebug`
Expected: `BUILD SUCCESSFUL`. (A malformed `pathData` fails at merge/build with a vector parse error.)

- [ ] **Step 8: Commit**

```bash
git add app/src/main/res/drawable/ic_nav_dashboard.xml app/src/main/res/drawable/ic_nav_monitor.xml app/src/main/res/drawable/ic_nav_history.xml app/src/main/res/drawable/ic_nav_account.xml app/src/main/res/drawable/ic_logo_eye.xml app/src/main/res/drawable/ic_chevron_right.xml
git commit -m "feat(ui): add core Signal nav/logo/chevron vector icons"
```

---

## Self-Review

**1. Spec coverage (Plan 1 slice = spec §3 design system + §4 components + phase 1):**
- §3.1 color tokens → Task 2 ✓ · §3.2 typography (fonts + scale) → Tasks 1, 4 ✓ · §3.3 spacing/radius/shape → Task 3 ✓ · §3.4 theme (Material 3 dark, system bars, dark-first mirror) → Task 5 ✓
- §4 components (buttons, text field, card, status pill, bottom nav, switch, slider) → Task 6 ✓; metric stat / alert row / trend chart are per-screen composites built in Plan 2 (noted, not foundation styles) ✓; nav/logo/chevron icons → Task 7 ✓
- Deferred to later plans by design: navigation shell, screens, merges/consolidation (Plans 2–4), legacy-color cleanup (Plan 4). No foundation requirement is unaddressed.

**2. Placeholder scan:** No "TBD/TODO/handle appropriately". The font-asset acquisition (Task 1 Step 1) is an explicit, named download with exact target filenames — not a placeholder.

**3. Type/name consistency:** Style ids referenced by the theme (`Widget.EyedTrack.Button`, `Widget.EyedTrack.BottomNav`) match their definitions in Task 6. Color names in `themes.xml` (`ink_*`, `blue_*`, `green_*`, `amber_*`, `red_*`, `text_*`) match `colors.xml` (Task 2). Text-appearance ids in `themes.xml` match `type.xml` (Task 4). Font family refs `@font/inter` / `@font/sora` match Task 1. The Task 5⇄Task 6 mutual reference is called out with an explicit ordering note and a single shared build gate.

---

## Execution Handoff

Handoff options are presented after this plan is reviewed (see the message accompanying this file).

# EyedTrack UI/UX Overhaul — Plan 3: Auth + Account Sub-Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the remaining interactive Activities onto the Signal design system — Login, Sign-up, the splash/loading screen, Profile, "Notifications & Sounds" (the real Sounds settings), and User Management — while preserving each Activity's existing logic and view IDs.

**Architecture:** These stay **Activities** (launched from `AccountFragment` and the auth flow), not fragments. Each task rewrites the Activity's XML layout with Signal tokens/components and makes a **minimal, explicitly-listed** edit to the Activity: drop the obsolete hand-built bottom nav + its listeners, drop `FLAG_FULLSCREEN`, add a simple top toolbar with a back button (`finish()`), and switch `AlertDialog` → `MaterialAlertDialogBuilder`. **All view IDs the Activity reads are preserved**, so the business logic (validation, PreferenceManager calls, RecyclerView wiring) is untouched.

**Tech Stack:** Kotlin, XML/Views, Material 3 (`material:1.11.0`), the Signal foundation (Plan 1), Plan 2's fragments already shipped.

## Global Constraints

_Every task's requirements implicitly include this section._

- **UI stack:** XML/Views only. No Compose. `compileSdk 34`, `minSdk 30`, Material `1.11.0`.
- **Build toolchain:** before any Gradle command export `JAVA_HOME="/c/Users/user/android-build/jdk/jdk-17.0.19+10"`; SDK via `local.properties`.
- **Build/verify:** `export JAVA_HOME=...; ./gradlew :app:assembleDebug --console=plain` → `BUILD SUCCESSFUL`.
- **Design system — Signal only.** Backgrounds `?android:attr/colorBackground` (ink_900); cards `@style/Widget.EyedTrack.Card`; buttons `@style/Widget.EyedTrack.Button` (+ `.Secondary`/`.Text`/`.Danger`); text fields `@style/Widget.EyedTrack.TextField` (`TextInputLayout` OutlinedBox); switches `@style/Widget.EyedTrack.Switch` (`MaterialSwitch`); slider `@style/Widget.EyedTrack.Slider`; text via `?attr/textAppearance*` (EyedTrack scale) + `?attr/colorOnSurface`/`colorOnSurfaceVariant`; icons `@drawable/ic_*`. **NO hardcoded hex** and **NO legacy `@color/purple_*`/`teal_*`**.
- **PRESERVE all view IDs an Activity reads** (each task lists them). Do NOT rename them.
- **Reuse logic verbatim:** `PreferenceManager.*`, validation rules, RecyclerView adapters, dialogs' actions. Only adapt Activity chrome (nav/fullscreen/dialog-builder) as each task specifies.
- **No new features:** the Sounds screen redesigns the THREE existing controls only (system-volume toggle, alert-volume slider, vibrate toggle) — do NOT add per-behavior alert toggles.
- **These screens are launched from `AccountFragment`/auth** — each gets a top toolbar with a back arrow that calls `finish()`. Drop the obsolete hand-built bottom nav (`home_icon`/`profile_icon`/`settings_icon` LinearLayouts) and any `scaleImageButton(...)` call on them.
- **Commit policy:** NO per-task commits; ONE commit at the end. Branch `feat/uiux-overhaul-signal`.

**Reusable pieces from earlier plans:** `@drawable/ic_logo_eye`, `ic_chevron_right`, `ic_nav_account`, `pill_*`, `bg_stat_tile`/`bg_icon_tile`, `@style/Widget.EyedTrack.*`. A shared **`@layout/include_top_bar`** is created in Task 1 and `<include>`d by later screens.

---

## File Structure

**Create:**
- `res/layout/include_top_bar.xml` — reusable toolbar (back arrow `id=btn_back` + title `id=top_bar_title`).
- `res/drawable/ic_arrow_back.xml` — back chevron/arrow vector.

**Modify (layout rewrite + minimal Activity edit) per task:**
- Login: `res/layout/activity_login.xml` + `LoginActivity.kt`
- Sign-up: `res/layout/signup_page.xml` + `SignUpActivity.kt`
- Splash: `res/layout/loading_screen.xml` (+ `LoadingScreenActivity.kt` only if it reads an ID that changes)
- Profile: `res/layout/profile_page.xml` + `ProfileActivity.kt`
- Sounds: `res/layout/sounds_page.xml` + `SoundsActivity.kt`
- User Management: `res/layout/activity_user_management.xml`, `res/layout/item_user.xml` + `UserManagementActivity.kt`

**Verification note:** UI screens; the gate is `assembleDebug` + visual/behavioral check on device where available. Preserve IDs so no logic breaks; the build (which compiles every Activity) catches any missed ID rename.

---

### Task 1: Shared top bar + Login redesign

**Files:**
- Create: `res/layout/include_top_bar.xml`, `res/drawable/ic_arrow_back.xml`
- Modify: `res/layout/activity_login.xml`, `app/src/main/java/com/example/eyedtrack/LoginActivity.kt`

**IDs LoginActivity reads (PRESERVE):** `rootLayout`, `editTextEmail`, `editTextPassword`, `buttonSignIn`, `textForgotPassword`, `textSignUp`, `checkBoxRememberMe`, `togglePasswordVisibility`.

- [ ] **Step 1: `ic_arrow_back.xml`**

```xml
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:strokeColor="@color/text_hi" android:strokeWidth="2" android:fillColor="#00000000"
        android:strokeLineCap="round" android:strokeLineJoin="round"
        android:pathData="M15,5 l-7,7 7,7" />
</vector>
```

- [ ] **Step 2: `include_top_bar.xml`** (reused by later screens)

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="wrap_content"
    android:orientation="horizontal" android:gravity="center_vertical"
    android:paddingHorizontal="@dimen/space_sm" android:paddingVertical="@dimen/space_sm"
    android:background="?android:attr/colorBackground">
    <ImageView android:id="@+id/btn_back" android:layout_width="@dimen/touch_min"
        android:layout_height="@dimen/touch_min" android:padding="@dimen/space_md"
        android:src="@drawable/ic_arrow_back" android:background="?attr/selectableItemBackgroundBorderless"
        android:contentDescription="Back" />
    <TextView android:id="@+id/top_bar_title" android:layout_width="wrap_content"
        android:layout_height="wrap_content" android:layout_marginStart="@dimen/space_xs"
        android:textAppearance="?attr/textAppearanceTitleLarge" android:textColor="?attr/colorOnSurface" />
</LinearLayout>
```

- [ ] **Step 3: `activity_login.xml`** — Signal auth screen (no toolbar here; it's a root screen). Full rewrite:

```xml
<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:id="@+id/rootLayout"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:background="?android:attr/colorBackground" android:fillViewport="true">

    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="vertical" android:gravity="center_horizontal"
        android:padding="@dimen/space_2xl">

        <FrameLayout android:layout_width="72dp" android:layout_height="72dp"
            android:layout_marginTop="@dimen/space_3xl" android:background="@drawable/bg_icon_tile">
            <ImageView android:layout_width="40dp" android:layout_height="40dp"
                android:layout_gravity="center" android:src="@drawable/ic_logo_eye"
                android:contentDescription="EyedTrack" />
        </FrameLayout>

        <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:layout_marginTop="@dimen/space_lg" android:text="EyedTrack"
            android:textAppearance="?attr/textAppearanceDisplaySmall" android:textColor="?attr/colorOnSurface" />
        <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
            android:layout_marginTop="@dimen/space_xs" android:gravity="center"
            android:text="Your companion for drowsy-free journeys"
            android:textAppearance="?attr/textAppearanceBodyMedium" android:textColor="?attr/colorOnSurfaceVariant" />

        <com.google.android.material.textfield.TextInputLayout
            style="@style/Widget.EyedTrack.TextField"
            android:layout_width="match_parent" android:layout_height="wrap_content"
            android:layout_marginTop="@dimen/space_2xl" android:hint="Email or phone">
            <com.google.android.material.textfield.TextInputEditText
                android:id="@+id/editTextEmail" android:layout_width="match_parent"
                android:layout_height="wrap_content" android:inputType="textEmailAddress" />
        </com.google.android.material.textfield.TextInputLayout>

        <com.google.android.material.textfield.TextInputLayout
            android:id="@+id/togglePasswordVisibility"
            style="@style/Widget.EyedTrack.TextField"
            android:layout_width="match_parent" android:layout_height="wrap_content"
            android:layout_marginTop="@dimen/space_md" android:hint="Password"
            app:endIconMode="password_toggle">
            <com.google.android.material.textfield.TextInputEditText
                android:id="@+id/editTextPassword" android:layout_width="match_parent"
                android:layout_height="wrap_content" android:inputType="textPassword" />
        </com.google.android.material.textfield.TextInputLayout>

        <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
            android:layout_marginTop="@dimen/space_md" android:gravity="center_vertical">
            <com.google.android.material.checkbox.MaterialCheckBox android:id="@+id/checkBoxRememberMe"
                android:layout_width="wrap_content" android:layout_height="wrap_content"
                android:text="Remember me" android:textColor="?attr/colorOnSurfaceVariant" />
            <TextView android:id="@+id/textForgotPassword" android:layout_width="0dp"
                android:layout_weight="1" android:layout_height="wrap_content" android:gravity="end"
                android:text="Forgot password?" android:textColor="@color/blue_400"
                android:textAppearance="?attr/textAppearanceLabelLarge" />
        </LinearLayout>

        <com.google.android.material.button.MaterialButton android:id="@+id/buttonSignIn"
            style="@style/Widget.EyedTrack.Button" android:layout_width="match_parent"
            android:layout_height="wrap_content" android:layout_marginTop="@dimen/space_xl"
            android:text="Sign in" />

        <LinearLayout android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:layout_marginTop="@dimen/space_2xl" android:gravity="center">
            <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
                android:text="Don't have an account? " android:textColor="?attr/colorOnSurfaceVariant"
                android:textAppearance="?attr/textAppearanceBodyMedium" />
            <TextView android:id="@+id/textSignUp" android:layout_width="wrap_content"
                android:layout_height="wrap_content" android:text="Sign up now"
                android:textColor="@color/blue_400" android:textAppearance="?attr/textAppearanceLabelLarge" />
        </LinearLayout>
    </LinearLayout>
</ScrollView>
```

- [ ] **Step 4: `LoginActivity.kt` minimal edits.** The `togglePasswordVisibility` ID now belongs to the password `TextInputLayout` (built-in toggle via `endIconMode`), so the OLD custom-toggle block is obsolete.
  - Change the `editTextEmail`/`editTextPassword` lookups from `EditText` to `com.google.android.material.textfield.TextInputEditText` (or keep `findViewById<EditText>` — `TextInputEditText` IS an `EditText`, so **no change needed**).
  - **DELETE** the `togglePasswordButton` block: the `val togglePasswordButton = findViewById<ImageView>(R.id.togglePasswordVisibility)` line and its entire `setOnClickListener { … }` (the built-in toggle replaces it). Remove the now-unused `InputType`/`ImageView` imports if the IDE flags them.
  - Remove the `window.setFlags(FLAG_FULLSCREEN…)` call.
  - Everything else (remember-me autofill, EMAIL extra, `validateLogin` → `setLoggedIn` → `MainActivity`, sign-up nav, `setupUI(rootLayout)`) stays **unchanged** — all referenced IDs still exist.

- [ ] **Step 5: Build.** `export JAVA_HOME=…; ./gradlew :app:assembleDebug --console=plain` → `BUILD SUCCESSFUL`. On device: Login renders dark with the eye logo, the password field's built-in eye toggles visibility, remember-me + sign-in still work.

---

### Task 2: Sign-up redesign

**Files:** Modify `res/layout/signup_page.xml`, `app/src/main/java/com/example/eyedtrack/SignUpActivity.kt`.

**IDs SignUpActivity reads (PRESERVE):** `firstNameInput`, `lastNameInput`, `mobileNumberInput`, `emailInput`, `passwordInput`, `signinClickableText`, `signupButton`.

- [ ] **Step 1: `signup_page.xml`** — the layout already uses `TextInputLayout`; restyle to Signal. Change the root `ScrollView` background to `?android:attr/colorBackground`; replace the eight hardcoded `#001F54`/`#5B6B8C`/`#0A1A33`/`#FFFFFF`/`#808080` colors with Signal tokens; change every `TextInputLayout` `style` from `@style/Widget.MaterialComponents.TextInputLayout.OutlinedBox` to `@style/Widget.EyedTrack.TextField` (drop the per-field `boxStrokeColor`/`hintTextColor`/`boxCornerRadius*` overrides — the style supplies them); keep the `app:startIconDrawable`/`endIconMode`. Add an eye-logo header (same `FrameLayout`+`ic_logo_eye` block as Login) above `signupTitle`. Title → `?attr/textAppearanceDisplaySmall`/`colorOnSurface`; subtitle → `bodyMedium`/`colorOnSurfaceVariant`. `signupButton` → `style="@style/Widget.EyedTrack.Button"` (drop the hardcoded backgroundTint/textColor/cornerRadius). `signinClickableText` text color → `@color/blue_400`. **Keep every `android:id` exactly.**

- [ ] **Step 2: `SignUpActivity.kt` minimal edit.** Remove the `window.setFlags(FLAG_FULLSCREEN…)`. Switch the confirmation `AlertDialog.Builder(this)` to `com.google.android.material.dialog.MaterialAlertDialogBuilder(this)` so it inherits the dark theme. All validation + `saveUserCredentials` + nav logic is **unchanged**.

- [ ] **Step 3: Build + verify** — `assembleDebug` green; Sign-up renders dark/Signal; validation (11-digit 09 mobile, @gmail.com email) and the confirm dialog still work.

---

### Task 3: Splash / loading screen redesign

**Files:** Modify `res/layout/loading_screen.xml` (and `LoadingScreenActivity.kt` ONLY if it reads a view ID that you change).

- [ ] **Step 1: Read `LoadingScreenActivity.kt`** and note any `findViewById` IDs it uses. Preserve those IDs.
- [ ] **Step 2: `loading_screen.xml`** — a centered dark splash: `?android:attr/colorBackground` root; centered `ic_logo_eye` (56dp) in a `bg_icon_tile` tile; the "EyedTrack" wordmark (`?attr/textAppearanceDisplaySmall`/`colorOnSurface`) + tagline (`bodyMedium`/`colorOnSurfaceVariant`); a small indeterminate `com.google.android.material.progressindicator.CircularProgressIndicator` (or keep the existing `ProgressBar` id if the Activity references it) tinted `?attr/colorPrimary`. Preserve any ID the Activity reads. No hardcoded hex.
- [ ] **Step 3: Build + verify** — `assembleDebug` green; splash shows dark brand screen, then routes (T&C / Main / Login per the Plan 2 logic) after its existing delay.

---

### Task 4: Profile redesign

**Files:** Modify `res/layout/profile_page.xml`, `app/src/main/java/com/example/eyedtrack/ProfileActivity.kt`.

**IDs ProfileActivity reads (PRESERVE):** `profile_name`, `fullname`, `email`, `phone_number`, `logout`. (The Activity also reads `profile_icon`, `settings_icon`, `home_icon` for the OLD nav — these are removed; see Step 2.)

- [ ] **Step 1: `profile_page.xml`** — full rewrite as a Signal sub-screen: a vertical root (`?android:attr/colorBackground`) with `<include layout="@layout/include_top_bar" android:id="@+id/top_bar" />` at the top; a profile header `MaterialCardView` (avatar tile with initial + `profile_name` `?attr/textAppearanceTitleLarge`); an "Account details" `MaterialCardView` containing three labeled read-only rows — **Name** (`fullname`), **Email** (`email`), **Mobile** (`phone_number`) — each a horizontal row (label `?attr/colorOnSurfaceVariant` + value `?attr/colorOnSurface`, a `?attr/colorOutline` divider between). Keep those three as the same widget type they are today (`EditText`, disabled by the Activity) OR plain `TextView`s — **but if you change `EditText`→`TextView`, verify the Activity's `.isEnabled = false` calls still compile (they do on both)**. A **Logout** `MaterialButton` `style="@style/Widget.EyedTrack.Button.Danger"` `android:id="@+id/logout"` at the bottom. Remove the old hand-built bottom nav entirely. Keep all five preserved IDs.
- [ ] **Step 2: `ProfileActivity.kt` minimal edits.**
  - Remove `window.setFlags(FLAG_FULLSCREEN…)`.
  - Remove the `scaleImageButton(findViewById(R.id.profile_icon))` call and the `scaleImageButton` function.
  - Remove the `btnGoToSettings`/`btnGoToHomePage` lookups (`settings_icon`/`home_icon`) and their listeners (obsolete nav).
  - Wire the new top bar back button: `findViewById<View>(R.id.top_bar).findViewById<ImageView>(R.id.btn_back).setOnClickListener { finish() }` and set `top_bar_title` text to "Profile".
  - Keep the login gate, user-data binding (`profile_name`/`fullname`/`email`/`phone_number`), the `.isEnabled = false` lines, and the logout dialog (switch it to `MaterialAlertDialogBuilder`, keep `performLogout()`).
- [ ] **Step 3: Build + verify** — `assembleDebug` green; Profile shows dark card layout with the user's data, back button returns to Account, logout works.

---

### Task 5: Notifications & Sounds redesign

**Files:** Modify `res/layout/sounds_page.xml`, `app/src/main/java/com/example/eyedtrack/SoundsActivity.kt`.

**IDs SoundsActivity reads (PRESERVE):** `systemVolumeSwitch`, `volumeSeekBar`, `volumeLabel`, `vibrateSwitch`. (It also reads `back_button` + old nav `home_icon`/`profile_icon`/`settings_icon` — replace per Step 2.)

- [ ] **Step 1: `sounds_page.xml`** — full rewrite as a Signal sub-screen: root (`?android:attr/colorBackground`) with `<include layout="@layout/include_top_bar" android:id="@+id/top_bar" />` (title set to "Notifications & sounds" in code); a "Sound" section label; a `MaterialCardView` (`Widget.EyedTrack.Card`) containing:
  - a **Use system volume** row: label + `com.google.android.material.materialswitch.MaterialSwitch android:id="@+id/systemVolumeSwitch"` (`style="@style/Widget.EyedTrack.Switch"`);
  - an **Alert volume** label `android:id="@+id/volumeLabel"` + a slider. **Keep it a `SeekBar android:id="@+id/volumeSeekBar"`** (the Activity calls `.setOnSeekBarChangeListener`, `.progress`, `.isEnabled` — a Material `Slider` has a different API and would require rewriting the Activity, which is out of scope). Restyle the SeekBar via theme tint (it inherits `?attr/colorPrimary`).
  - a **Vibrate on alert** row: label + `MaterialSwitch android:id="@+id/vibrateSwitch"`.
  Then an info `MaterialCardView` with the system-volume explanatory text (`?attr/colorOnSurfaceVariant`). Remove the old header LinearLayout and the hand-built bottom nav. NO hardcoded hex (the old `#ADD8E6`/`#060644`/`#666666` go).
- [ ] **Step 2: `SoundsActivity.kt` minimal edits.** Remove `FLAG_FULLSCREEN`. Remove the `back_button` + `btnGoToSettings`/`btnGoToProfile`/`btnGoToHomePage` (`home_icon`/`profile_icon`/`settings_icon`) lookups and listeners. Wire the top bar: `findViewById<View>(R.id.top_bar)...R.id.btn_back` → `finish()`, and set `top_bar_title` = "Notifications & sounds". `initializeViews()`/`setupVolumeControls()`/`loadSettings()`/`syncWithSystemVolume()` and all persistence are **unchanged** (the 3 control IDs are preserved). Note: `systemVolumeSwitch`/`vibrateSwitch` are now `MaterialSwitch` — the Activity declares them as `Switch`; change those two field types to `com.google.android.material.materialswitch.MaterialSwitch` (which extends `Switch`/`CompoundButton`, so `setOnCheckedChangeListener`/`isChecked` are unchanged).
- [ ] **Step 3: Build + verify** — `assembleDebug` green; screen shows two Signal switches + the volume slider, settings persist, system-volume sync still works.

---

### Task 6: User Management redesign

**Files:** Modify `res/layout/activity_user_management.xml`, `res/layout/item_user.xml`, `app/src/main/java/com/example/eyedtrack/UserManagementActivity.kt`.

**IDs read (PRESERVE):** activity — `recyclerViewUsers`, `btnRefresh`, `txtUserCount`; `item_user` — `txtName`, `txtEmail`, `txtMobile`, `btnDelete`.

- [ ] **Step 1: `activity_user_management.xml`** — rewrite as Signal: root (`?android:attr/colorBackground`) with `<include layout="@layout/include_top_bar" android:id="@+id/top_bar" />` (title "User management"); a row with `txtUserCount` (`?attr/colorOnSurfaceVariant`) + a `btnRefresh` `MaterialButton style="@style/Widget.EyedTrack.Button.Secondary"`; the `recyclerViewUsers` RecyclerView (`layout_weight=1`, transparent bg); a footer note (`?attr/colorOnSurfaceVariant`). Keep the three IDs.
- [ ] **Step 2: `item_user.xml`** — rewrite as a Signal row: `MaterialCardView` (`Widget.EyedTrack.Card`) → name (`txtName`, `?attr/textAppearanceTitleMedium`/`colorOnSurface`), email (`txtEmail`) + mobile (`txtMobile`) (`bodyMedium`/`colorOnSurfaceVariant`), and a `btnDelete` `MaterialButton style="@style/Widget.EyedTrack.Button.Danger"`. Keep the four IDs.
- [ ] **Step 3: `UserManagementActivity.kt` minimal edits.** Remove `FLAG_FULLSCREEN`. Wire the top bar back button → `finish()` and set `top_bar_title` = "User management". Switch the delete-confirmation `AlertDialog.Builder` → `MaterialAlertDialogBuilder`. The `UserAdapter`, `refreshUsersList`, `confirmDeleteUser`, and `PreferenceManager` calls are **unchanged** (IDs preserved).
- [ ] **Step 4: Build + verify** — `assembleDebug` green; the list shows Signal user cards, refresh + delete-with-confirmation still work.

---

## Self-Review

**1. Spec coverage (spec §6 auth + Account sub-screens):** Login → Task 1 ✓; Sign-up → Task 2 ✓; Splash → Task 3 ✓; Profile → Task 4 ✓; Notifications & Sounds (real Sounds controls) → Task 5 ✓; User Management → Task 6 ✓. The shared top bar (Task 1) is reused by Tasks 4-6. Deferred to Plan 4 (per spec §5.2): the legal/info doc screens (Data & Privacy, Help, FAQs, About, EULA, DPA) + a shared doc template + retiring the legacy Activities (HomePage/LiveFeed/AlertHistory/Settings) + the final accessibility pass. `SettingsActivity` is NOT redesigned — it's a nav hub already replaced by the Account tab (retired in Plan 4).

**2. Placeholder scan:** Each task lists the exact IDs to preserve and the exact minimal Activity edits (delete these lines, switch this dialog builder). Full layout XML is given for Login (Task 1); the others give a precise structure + tokens + preserved IDs + the specific hardcoded colors to replace — no "restyle appropriately" hand-waving.

**3. Type/name consistency:** Preserved-ID lists match what each Activity's `findViewById` reads (verified against the current source). `include_top_bar.xml` exposes `btn_back` + `top_bar_title`, referenced identically in Tasks 4-6. `MaterialSwitch`/`TextInputEditText` are `CompoundButton`/`EditText` subclasses, so the Activities' existing calls compile unchanged (noted where the field type must change).

---

## Execution Handoff

Same as Plans 1-2: subagent-driven, one implementer + task review per task (Tasks 1, 4, 5 touch Activity logic — review those carefully; Tasks 2, 3, 6 are lighter and can take controller-side review), final Opus whole-branch review, then the SINGLE Plan 3 commit. Device-verify auth + settings persistence before merging.

# EyedTrack UI/UX Overhaul — Plan 2: Navigation Shell + Core Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragmented per-Activity navigation with a single `MainActivity` host + Material 3 `BottomNavigationView` + AndroidX Navigation, and deliver the four core tab Fragments (Dashboard, Monitor, History, Account) rebuilt on the Signal design system — with the CameraX monitoring logic moved into `MonitorFragment`.

**Architecture:** One host Activity (`MainActivity`) with a `NavHostFragment` and a 4-item bottom nav bound to a nav graph. The Live Feed and Alert History screens are ported from Activities into `MonitorFragment` / `HistoryFragment` (reusing the existing `CameraService`, `CameraViewModel`, `AlertLogLoader`, `AlertHistoryAdapter`, `VoiceAlertManager`). `DashboardFragment` and `AccountFragment` are new, wired to existing data sources (`AlertLogLoader`, `PreferenceManager`). The old Activities remain in the manifest for now (secondary screens still launch as Activities from Account); they are retired in Plan 4.

**Tech Stack:** Kotlin, XML/Views, Material 3 (`com.google.android.material:material:1.11.0`), AndroidX Navigation 2.7.7, CameraX (existing), view binding (already enabled).

## Global Constraints

_Every task's requirements implicitly include this section._

- **UI stack:** XML/Views only. No Compose.
- **SDK:** `compileSdk 34`, `minSdk 30`, `targetSdk 34`. Material `1.11.0`.
- **Build toolchain (no JDK on PATH):** before any Gradle command export `JAVA_HOME="/c/Users/user/android-build/jdk/jdk-17.0.19+10"` (Temurin 17); SDK via `local.properties`.
- **Build/verify:** `export JAVA_HOME="/c/Users/user/android-build/jdk/jdk-17.0.19+10"; ./gradlew :app:assembleDebug --console=plain`. Green = `BUILD SUCCESSFUL`, exit 0. For UI behavior, also `./gradlew :app:installDebug` and launch on a device/emulator when one is available.
- **Design system:** use ONLY Signal tokens/styles from Plan 1 — `?attr/colorPrimary`, `?attr/colorSurface`, `@color/ink_*`, `@color/blue_*`, `?attr/stateSafe|stateCaution|stateAlert` (+ containers), `@style/Widget.EyedTrack.*`, `@style/TextAppearance.EyedTrack.*`, `@drawable/pill_*`, `@drawable/ic_nav_*`, `@dimen/space_*`/`radius_*`. Do NOT hardcode hex colors or reintroduce legacy `@color/purple_*`/`teal_*`.
- **No backend/ML changes.** Reuse existing API/data classes verbatim (`ApiService`, `ProcessingResponse`, `Metrics`, `AlertHistoryItem`, `AlertLogLoader`, `PreferenceManager`).
- **Dashboard aggregates ONLY existing data** (alert history + live status). Do NOT invent "trips" or "drive-time" tracking — that data does not exist.
- **Package:** `com.example.eyedtrack`. Fragments in `com.example.eyedtrack.ui` (new subpackage).
- **Commit policy:** NO per-task commits — accumulate in the working tree; ONE commit at the end (controller commits after final review). Branch: `feat/uiux-overhaul-signal`.
- **Reuse, don't rewrite:** when porting an Activity to a Fragment, carry over its working logic (connection check, permission flow, camera start/stop, voice alerts, auto-refresh) adapting only Activity APIs → Fragment APIs. Do not redesign behavior.

---

## File Structure

**Create:**
- `app/src/main/res/menu/bottom_nav_menu.xml` — 4 nav items.
- `app/src/main/res/navigation/nav_main.xml` — nav graph (start = dashboard).
- `app/src/main/java/com/example/eyedtrack/MainActivity.kt` + `res/layout/activity_main.xml` — host.
- `app/src/main/java/com/example/eyedtrack/ui/DashboardFragment.kt` + `res/layout/fragment_dashboard.xml`
- `.../ui/MonitorFragment.kt` + `res/layout/fragment_monitor.xml`
- `.../ui/HistoryFragment.kt` + `res/layout/fragment_history.xml`
- `.../ui/AccountFragment.kt` + `res/layout/fragment_account.xml`
- `res/layout/item_alert.xml` — new Signal-styled alert row (replaces `alert_history_item.xml` usage).
- `res/drawable/bg_stat_tile.xml`, `res/drawable/ic_play.xml`, `res/drawable/ic_stop.xml`, `res/drawable/ic_logout.xml`, `res/drawable/ic_shield.xml`, `res/drawable/ic_bell.xml`, `res/drawable/ic_people.xml`, `res/drawable/ic_help.xml` — small icons used by the fragments.

**Modify:**
- `app/build.gradle.kts` — add Navigation dependencies.
- `app/src/main/AndroidManifest.xml` — register `MainActivity`.
- `app/src/main/java/com/example/eyedtrack/adapter/AlertHistoryAdapter.kt` — bind to `item_alert.xml` + Signal styling.
- `app/src/main/java/com/example/eyedtrack/LoadingScreenActivity.kt` and `LoginActivity.kt` — route to `MainActivity` instead of `HomePageActivity`.

---

### Task 1: Navigation shell (host + bottom nav + 4 stub fragments)

**Files:**
- Modify: `app/build.gradle.kts`
- Create: `res/menu/bottom_nav_menu.xml`, `res/navigation/nav_main.xml`, `MainActivity.kt`, `res/layout/activity_main.xml`, 4 fragment classes under `ui/` + 4 fragment layouts (stub content)
- Modify: `AndroidManifest.xml`, `LoadingScreenActivity.kt`, `LoginActivity.kt`

**Interfaces:**
- Produces: `MainActivity` (host), nav destinations with IDs `dashboardFragment`, `monitorFragment`, `historyFragment`, `accountFragment`; the four `Fragment` classes in `com.example.eyedtrack.ui`. Later tasks fill each fragment's content.

- [ ] **Step 1: Add Navigation dependencies**

In `app/build.gradle.kts`, inside `dependencies { … }`, add:

```kotlin
    implementation("androidx.navigation:navigation-fragment-ktx:2.7.7")
    implementation("androidx.navigation:navigation-ui-ktx:2.7.7")
```

- [ ] **Step 2: Bottom-nav menu**

`app/src/main/res/menu/bottom_nav_menu.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<menu xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:id="@+id/dashboardFragment" android:icon="@drawable/ic_nav_dashboard" android:title="Dashboard" />
    <item android:id="@+id/monitorFragment"   android:icon="@drawable/ic_nav_monitor"   android:title="Monitor" />
    <item android:id="@+id/historyFragment"    android:icon="@drawable/ic_nav_history"    android:title="History" />
    <item android:id="@+id/accountFragment"    android:icon="@drawable/ic_nav_account"    android:title="Account" />
</menu>
```

- [ ] **Step 3: Nav graph**

`app/src/main/res/navigation/nav_main.xml` (destination IDs MUST equal the menu item IDs so `setupWithNavController` maps them):

```xml
<?xml version="1.0" encoding="utf-8"?>
<navigation xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:id="@+id/nav_main"
    app:startDestination="@id/dashboardFragment">

    <fragment android:id="@+id/dashboardFragment"
        android:name="com.example.eyedtrack.ui.DashboardFragment"
        android:label="Dashboard" />
    <fragment android:id="@+id/monitorFragment"
        android:name="com.example.eyedtrack.ui.MonitorFragment"
        android:label="Monitor" />
    <fragment android:id="@+id/historyFragment"
        android:name="com.example.eyedtrack.ui.HistoryFragment"
        android:label="History" />
    <fragment android:id="@+id/accountFragment"
        android:name="com.example.eyedtrack.ui.AccountFragment"
        android:label="Account" />
</navigation>
```

- [ ] **Step 4: Host layout**

`app/src/main/res/layout/activity_main.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="?android:attr/colorBackground">

    <androidx.fragment.app.FragmentContainerView
        android:id="@+id/nav_host"
        android:name="androidx.navigation.fragment.NavHostFragment"
        android:layout_width="0dp"
        android:layout_height="0dp"
        app:defaultNavHost="true"
        app:navGraph="@navigation/nav_main"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintBottom_toTopOf="@id/bottom_nav" />

    <com.google.android.material.bottomnavigation.BottomNavigationView
        android:id="@+id/bottom_nav"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        app:menu="@menu/bottom_nav_menu"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent" />
</androidx.constraintlayout.widget.ConstraintLayout>
```

(The `BottomNavigationView` inherits `Widget.EyedTrack.BottomNav` via the theme's `bottomNavigationStyle` default — no per-view style needed.)

- [ ] **Step 5: MainActivity host**

`app/src/main/java/com/example/eyedtrack/MainActivity.kt`:

```kotlin
package com.example.eyedtrack

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.navigation.fragment.NavHostFragment
import androidx.navigation.ui.setupWithNavController
import com.example.eyedtrack.databinding.ActivityMainBinding

// Single host for the four bottom-nav tabs.
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Gate: require login (moved out of the old HomePageActivity).
        if (!PreferenceManager.isLoggedIn(this)) {
            startActivity(android.content.Intent(this, LoginActivity::class.java))
            finish()
            return
        }

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val navHost = supportFragmentManager
            .findFragmentById(R.id.nav_host) as NavHostFragment
        binding.bottomNav.setupWithNavController(navHost.navController)
    }
}
```

- [ ] **Step 6: Four stub fragments**

Create `com.example.eyedtrack.ui.DashboardFragment`, `MonitorFragment`, `HistoryFragment`, `AccountFragment`. Each is a minimal stub for now (content filled in Tasks 2–5). Example — `app/src/main/java/com/example/eyedtrack/ui/DashboardFragment.kt`:

```kotlin
package com.example.eyedtrack.ui

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.example.eyedtrack.R

class DashboardFragment : Fragment() {
    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?
    ): View = inflater.inflate(R.layout.fragment_dashboard, container, false)
}
```

Create `MonitorFragment`, `HistoryFragment`, `AccountFragment` identically, each inflating `R.layout.fragment_monitor` / `fragment_history` / `fragment_account` respectively.

- [ ] **Step 7: Four stub layouts**

Create `fragment_dashboard.xml`, `fragment_monitor.xml`, `fragment_history.xml`, `fragment_account.xml`. Stub each with a centered title so the shell is verifiable — e.g. `fragment_dashboard.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:background="?android:attr/colorBackground">
    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:layout_gravity="center" android:text="Dashboard"
        android:textAppearance="?attr/textAppearanceHeadlineSmall"
        android:textColor="?attr/colorOnSurface" />
</FrameLayout>
```

Repeat for the other three (change the text). These bodies are replaced in Tasks 2–5.

- [ ] **Step 8: Register MainActivity + route the launcher to it**

In `AndroidManifest.xml`, add inside `<application>` (near HomePageActivity):

```xml
        <!-- Host activity for the bottom-nav tabs -->
        <activity android:name=".MainActivity" android:exported="false" />
```

Then point post-login navigation at `MainActivity`:
- In `LoadingScreenActivity.kt`: find where it navigates after the splash. If it currently targets `HomePageActivity`, change that target to `MainActivity`; if it routes by login state, use `MainActivity` for the logged-in branch and `LoginActivity` otherwise. Preserve existing splash timing.
- In `LoginActivity.kt`: find the successful-login navigation (`startActivity(Intent(this, HomePageActivity::class.java))`) and change the target to `MainActivity::class.java`. Leave all other login logic unchanged.

(Do NOT delete `HomePageActivity` or the other Activities — they are retired in Plan 4.)

- [ ] **Step 9: Build + launch verify**

Run: `export JAVA_HOME="/c/Users/user/android-build/jdk/jdk-17.0.19+10"; ./gradlew :app:assembleDebug --console=plain`
Expected: `BUILD SUCCESSFUL`.
Then, if a device/emulator is available: `./gradlew :app:installDebug`, launch, log in — expected: a dark 4-tab bottom bar (Dashboard/Monitor/History/Account); tapping tabs swaps the stub fragments; the active tab shows the blue_400 tint + pill indicator.

---

### Task 2: MonitorFragment (port the CameraX live feed)

**Files:**
- Rewrite: `app/src/main/java/com/example/eyedtrack/ui/MonitorFragment.kt`
- Rewrite: `app/src/main/res/layout/fragment_monitor.xml`

**Interfaces:**
- Consumes: `CameraService(context, lifecycleOwner, previewView, onFrameCaptured, onError)`, `CameraViewModel` (`processFrame`, `onCameraStarted`, `onCameraStopped`, `getProcessingState()`), `ApiClient`, `VoiceAlertManager`, `AlertLogLoader.readLatestBehaviorFlags()` — all reused unchanged.
- Produces: a self-contained Monitor tab that runs the camera and monitoring.

**Port source:** `LiveFeedActivity.kt` (read it). Carry over verbatim, adapting Activity→Fragment: `checkServerConnection()`/`showRetryDialog()`, `toggleMonitoring()`/`startMonitoring()`/`stopMonitoring()`, `onCameraError()`, the camera-permission flow, `startBehaviorChecking()`/`checkBehaviorFlags()`, and the `ProcessingState` observer. Adaptations required:
- `by viewModels()` works in a Fragment (fragment-ktx) — keep it.
- `CameraService(context = requireContext(), lifecycleOwner = viewLifecycleOwner, previewView = binding.previewView, …)`.
- Replace `this` (LifecycleOwner) in `observe(this)` with `viewLifecycleOwner`.
- Replace `registerForActivityResult(...)` at the Activity — register it as a Fragment property (Fragments support `registerForActivityResult`).
- Move window flags: call `requireActivity().window.addFlags(FLAG_KEEP_SCREEN_ON)` in `onResume` and clear in `onPause` (do NOT set `FLAG_FULLSCREEN` — the host shows the bottom nav).
- Camera lifecycle: start nothing automatically; bind camera in `startMonitoring()`. In `onPause()` call `cameraService.stopCamera()` if initialized; in `onDestroyView()` stop camera, cancel jobs/handlers, `voiceAlertManager.shutdown()`, and null the binding.
- Remove the old hand-built bottom-nav click handlers and the header back button (the host bottom nav replaces them).
- Dialogs: use `MaterialAlertDialogBuilder(requireContext())` so they inherit the dark theme.

- [ ] **Step 1: `fragment_monitor.xml`** — Signal-styled monitor screen:

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:orientation="vertical" android:padding="@dimen/space_lg"
    android:background="?android:attr/colorBackground">

    <com.google.android.material.card.MaterialCardView
        style="@style/Widget.EyedTrack.Card"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:layout_marginBottom="@dimen/space_md">
        <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
            android:orientation="horizontal" android:gravity="center_vertical">
            <LinearLayout android:layout_width="0dp" android:layout_weight="1"
                android:layout_height="wrap_content" android:orientation="vertical">
                <TextView android:id="@+id/status_headline" android:layout_width="wrap_content"
                    android:layout_height="wrap_content" android:text="Not monitoring"
                    android:textAppearance="?attr/textAppearanceTitleLarge"
                    android:textColor="?attr/colorOnSurface" />
                <TextView android:id="@+id/status_sub" android:layout_width="wrap_content"
                    android:layout_height="wrap_content" android:text="Tap start to begin"
                    android:textAppearance="?attr/textAppearanceBodyMedium"
                    android:textColor="?attr/colorOnSurfaceVariant" />
            </LinearLayout>
            <TextView android:id="@+id/status_pill" android:layout_width="wrap_content"
                android:layout_height="wrap_content" android:background="@drawable/pill_idle"
                android:paddingHorizontal="@dimen/space_md" android:paddingVertical="@dimen/space_xs"
                android:text="IDLE" android:textAppearance="?attr/textAppearanceLabelLarge"
                android:textColor="?attr/colorOnSurfaceVariant" />
        </LinearLayout>
    </com.google.android.material.card.MaterialCardView>

    <androidx.camera.view.PreviewView
        android:id="@+id/previewView"
        android:layout_width="match_parent" android:layout_height="0dp"
        android:layout_weight="1" app:scaleType="fitCenter"
        android:background="@color/ink_900" />

    <com.google.android.material.button.MaterialButton
        android:id="@+id/btn_toggle_monitoring"
        style="@style/Widget.EyedTrack.Button"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:layout_marginTop="@dimen/space_lg" android:text="Start Monitoring" />
</LinearLayout>
```

- [ ] **Step 2: `MonitorFragment.kt`** — port the logic. Skeleton (fill the carried-over method bodies from `LiveFeedActivity`):

```kotlin
package com.example.eyedtrack.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import com.example.eyedtrack.api.ApiClient
import com.example.eyedtrack.camera.CameraService
import com.example.eyedtrack.databinding.FragmentMonitorBinding
import com.example.eyedtrack.utils.AlertLogLoader
import com.example.eyedtrack.utils.VoiceAlertManager
import com.example.eyedtrack.viewmodel.CameraViewModel
import com.example.eyedtrack.viewmodel.ProcessingState
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.*

class MonitorFragment : Fragment() {

    private var _binding: FragmentMonitorBinding? = null
    private val binding get() = _binding!!
    private val viewModel: CameraViewModel by viewModels()

    private lateinit var cameraService: CameraService
    private lateinit var voiceAlertManager: VoiceAlertManager
    private lateinit var alertLogLoader: AlertLogLoader
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private val handler = Handler(Looper.getMainLooper())
    private var isConnected = false
    private var isMonitoring = false
    private var connectionJob: Job? = null
    private val CHECK_INTERVAL = 1000L

    private val requestPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startMonitoring()
        }

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, s: Bundle?): View {
        _binding = FragmentMonitorBinding.inflate(i, c, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding.previewView.implementationMode = PreviewView.ImplementationMode.PERFORMANCE
        voiceAlertManager = VoiceAlertManager(requireContext())
        alertLogLoader = AlertLogLoader(requireContext())
        ApiClient.initialize(requireContext().applicationContext)

        viewModel.getProcessingState().observe(viewLifecycleOwner) { state ->
            if (state is ProcessingState.Success) {
                val b = state.response.behaviors
                voiceAlertManager.processAlerts(
                    isDrowsy = b.contains("drowsy"),
                    isYawning = b.contains("yawning"),
                    isDistracted = b.contains("distracted"))
                setStatusSafe()
            } else if (state is ProcessingState.Error) {
                setStatusError(state.message)
            }
        }

        binding.btnToggleMonitoring.setOnClickListener { toggleMonitoring() }
        checkServerConnection() // carried over from LiveFeedActivity, adapted
    }

    // Carry over (adapted): checkServerConnection, showRetryDialog (use MaterialAlertDialogBuilder),
    // toggleMonitoring, startMonitoring (cameraService = CameraService(requireContext(),
    // viewLifecycleOwner, binding.previewView, viewModel::processFrame, ::onCameraError)),
    // stopMonitoring, onCameraError, startBehaviorChecking, checkBehaviorFlags,
    // checkCameraPermission/requestCameraPermission.

    private fun setStatusSafe() {
        binding.statusHeadline.text = "Awake"
        binding.statusSub.text = "Monitoring active · all clear"
        binding.statusPill.setBackgroundResource(com.example.eyedtrack.R.drawable.pill_safe)
        binding.statusPill.text = "LIVE"
    }
    private fun setStatusError(msg: String) {
        binding.statusHeadline.text = "Error"
        binding.statusSub.text = msg
        binding.statusPill.setBackgroundResource(com.example.eyedtrack.R.drawable.pill_alert)
        binding.statusPill.text = "ERROR"
    }

    override fun onResume() {
        super.onResume()
        requireActivity().window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }
    override fun onPause() {
        super.onPause()
        requireActivity().window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        connectionJob?.cancel()
        if (::cameraService.isInitialized) cameraService.stopCamera()
        isMonitoring = false
    }
    override fun onDestroyView() {
        handler.removeCallbacksAndMessages(null)
        scope.cancel()
        if (::cameraService.isInitialized) cameraService.stopCamera()
        if (::voiceAlertManager.isInitialized) voiceAlertManager.shutdown()
        _binding = null
        super.onDestroyView()
    }

    private fun checkCameraPermission() = ContextCompat.checkSelfPermission(
        requireContext(), Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
}
```

- [ ] **Step 3: Build + monitor verify**

Build (`assembleDebug`). Expected `BUILD SUCCESSFUL`. On device: open Monitor tab with the backend running — camera preview shows, "Start Monitoring" starts the feed and status flips to a green **Awake** pill; leaving the tab (`onPause`) stops the camera. (Guard with `if backend unavailable` the retry dialog still appears.)

---

### Task 3: HistoryFragment (port alert history + Signal list)

**Files:**
- Rewrite: `ui/HistoryFragment.kt`, `res/layout/fragment_history.xml`
- Create: `res/layout/item_alert.xml`
- Modify: `adapter/AlertHistoryAdapter.kt`

**Interfaces:**
- Consumes: `AlertLogLoader.loadAlertLogs(max)` → `List<AlertHistoryItem>` (fields `date`, `time`, `alertType`, `confidence: Int`, `reason`, `behaviorOutput`); `AlertHistoryAdapter`.
- Produces: History tab with a 7-day trend row + grouped alert list.

**Port source:** `AlertHistoryActivity.kt` — carry over `loadAlertLogs()`/`refreshAlertHistory()` and the swipe-to-refresh + auto-refresh (10s) logic, adapting to Fragment lifecycle (use `viewLifecycleOwner.lifecycleScope`, stop auto-refresh in `onPause`). Drop the storage-permission dialogs' Activity chrome but keep the permission check (`AlertLogLoader` also reads the API, which needs no storage permission — keep the flow but the API path is primary).

- [ ] **Step 1: `item_alert.xml`** — Signal alert row (replaces the old `alert_history_item.xml`):

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="wrap_content"
    android:orientation="horizontal" android:gravity="center_vertical"
    android:paddingVertical="@dimen/space_md" android:paddingHorizontal="@dimen/space_xs">
    <View android:id="@+id/severity_dot" android:layout_width="10dp" android:layout_height="10dp"
        android:layout_marginEnd="@dimen/space_md" android:background="@drawable/pill_alert" />
    <LinearLayout android:layout_width="0dp" android:layout_weight="1"
        android:layout_height="wrap_content" android:orientation="vertical">
        <TextView android:id="@+id/alert_type" android:layout_width="wrap_content"
            android:layout_height="wrap_content" android:textAppearance="?attr/textAppearanceTitleMedium"
            android:textColor="?attr/colorOnSurface" tools:ignore="MissingDefaultResource" />
        <TextView android:id="@+id/alert_reason" android:layout_width="match_parent"
            android:layout_height="wrap_content" android:maxLines="1" android:ellipsize="end"
            android:textAppearance="?attr/textAppearanceBodyMedium"
            android:textColor="?attr/colorOnSurfaceVariant" />
    </LinearLayout>
    <TextView android:id="@+id/alert_time" android:layout_width="wrap_content"
        android:layout_height="wrap_content" android:textAppearance="?attr/textAppearanceLabelLarge"
        android:textColor="?attr/colorOnSurfaceVariant" />
</LinearLayout>
```

(Add `xmlns:tools` to the root or drop the `tools:ignore`.)

- [ ] **Step 2: Update `AlertHistoryAdapter`** — bind to `item_alert.xml`, remove hardcoded hex; set the severity dot tint by alert type (drowsy/multiple → `pill_alert`, else → `pill_caution`), show `alertType`, a trimmed `reason`, and `time`. Replace the ViewHolder field lookups with the new IDs (`alert_type`, `alert_reason`, `alert_time`, `severity_dot`). Keep `updateAlerts(newAlerts)`.

```kotlin
override fun onBindViewHolder(holder: AlertViewHolder, position: Int) {
    val item = alertItems[position]
    holder.alertType.text = item.alertType
    holder.alertReason.text = item.reason.substringBefore(" (") // drop the metrics tail
    holder.alertTime.text = item.time
    val severe = item.alertType.contains("Drows", true) || item.alertType.contains("Multiple", true)
    holder.severityDot.setBackgroundResource(if (severe) R.drawable.pill_alert else R.drawable.pill_caution)
}
```

- [ ] **Step 3: `fragment_history.xml`** — toolbar title, 7-day trend row (7 weighted bars in a horizontal LinearLayout, heights set in code), a `SwipeRefreshLayout` wrapping a `RecyclerView`, and an empty-state `TextView`. Use `?attr/colorSurface` cards and Signal text appearances. (Full layout: title `TextView` textAppearanceHeadlineSmall; a `MaterialCardView` holding a horizontal `LinearLayout id=trend_row` height 64dp; `SwipeRefreshLayout id=swipe_refresh` → `RecyclerView id=alerts_recycler`; `TextView id=empty_text` "No alerts yet".)

- [ ] **Step 4: `HistoryFragment.kt`** — set up the `RecyclerView` (LinearLayoutManager + `AlertHistoryAdapter`), call `loadAlertLogs(100)` on `onViewCreated` and on swipe-refresh, populate the trend row by bucketing `alertItems` into the last 7 days (`date` string compare) and setting each bar's `layoutParams.height` proportional to that day's count (min 4dp). Start/stop the 10s auto-refresh in `onResume`/`onPause`. Use `viewLifecycleOwner.lifecycleScope`.

- [ ] **Step 5: Build + verify** — `assembleDebug` green; History tab lists alerts (or the empty state), swipe refreshes, trend bars reflect per-day counts.

---

### Task 4: DashboardFragment

**Files:** Rewrite `ui/DashboardFragment.kt`, `res/layout/fragment_dashboard.xml`. Create `res/drawable/ic_play.xml` (reuse a triangle path).

**Interfaces:**
- Consumes: `PreferenceManager.getUserData()` (greeting), `AlertLogLoader.loadAlertLogs()` (recent alerts + today count), the host `NavController` (to switch to the Monitor tab).
- Produces: the landing Dashboard.

- [ ] **Step 1: `fragment_dashboard.xml`** — a vertical `ScrollView` with: a greeting `TextView` ("Good evening, <firstName>"), a `MaterialCardView` (`Widget.EyedTrack.Card`) containing an idle status pill + a full-width **Start Monitoring** `MaterialButton` (`Widget.EyedTrack.Button` + `app:icon="@drawable/ic_play"`), a "Today" section with **two** stat tiles only — **Alerts today** and **Total alerts** (NOT trips/drive-time; that data doesn't exist) — and a "Recent alerts" `MaterialCardView` holding up to 3 rows (reuse `item_alert.xml` inflated manually or a small nested RecyclerView). All text via Signal text appearances; stat tiles use a `?attr/colorSurfaceContainer` background (`bg_stat_tile.xml`, a rounded `@dimen/radius_md` shape filled `?attr/colorSurfaceContainer`).

- [ ] **Step 2: `DashboardFragment.kt`** — in `onViewCreated`: set greeting from `PreferenceManager.getUserData(requireContext())["firstName"]` (fallback "Driver"); load alerts via `viewLifecycleOwner.lifecycleScope` + `AlertLogLoader(requireContext()).loadAlertLogs(20)`, compute today's count (`date == today`) and total, bind the two stat tiles, and inflate up to 3 recent `item_alert` rows into the recent-alerts container. Wire **Start Monitoring** to switch tabs:

```kotlin
btnStart.setOnClickListener {
    androidx.navigation.fragment.findNavController(this)
        .navigate(com.example.eyedtrack.R.id.monitorFragment)
}
```

- [ ] **Step 3: Build + verify** — `assembleDebug` green; Dashboard shows greeting, the two real stats, recent alerts, and Start Monitoring jumps to the Monitor tab (bottom-nav selection follows).

---

### Task 5: AccountFragment (hub)

**Files:** Rewrite `ui/AccountFragment.kt`, `res/layout/fragment_account.xml`. Create small icons `ic_bell.xml`, `ic_people.xml`, `ic_shield.xml`, `ic_help.xml`, `ic_logout.xml` (simple stroke vectors like the Plan 1 icons).

**Interfaces:**
- Consumes: `PreferenceManager.getUserData()` (name/email), and launches existing Activities via `Intent` (`ProfileActivity`, `SettingsActivity`, `SoundsActivity`, `UserManagementActivity`, `DataPrivacyActivity`, `HelpActivity`), plus `LoginActivity` for sign-out.
- Produces: the Account hub.

- [ ] **Step 1: `fragment_account.xml`** — a `ScrollView` with: a profile `MaterialCardView` (avatar tile with the user's initial, name via `textAppearanceTitleLarge`, email via `bodyMedium`); a grouped card of rows (each a horizontal `LinearLayout`: leading icon tile `?attr/colorPrimaryContainer`, title, trailing `@drawable/ic_chevron_right`) for **Profile**, **Notifications & sounds**, **User management**; a second grouped card for **Data & privacy**, **Help & legal**; and a **Sign out** `TextView` in `?attr/colorError`. IDs: `row_profile`, `row_sounds`, `row_users`, `row_privacy`, `row_help`, `btn_sign_out`, `profile_name`, `profile_email`, `profile_initial`.

- [ ] **Step 2: `AccountFragment.kt`** — bind name/email/initial from `PreferenceManager.getUserData()`; set click listeners:
  - `row_profile` → `ProfileActivity`; `row_sounds` → `SoundsActivity`; `row_users` → `UserManagementActivity`; `row_privacy` → `DataPrivacyActivity`; `row_help` → `HelpActivity` (these consolidate under Account per the IA; the full Help & Legal sub-list is Plan 4).
  - `btn_sign_out`: `PreferenceManager.setLoggedIn(requireContext(), false)`, then `startActivity(Intent(requireContext(), LoginActivity::class.java).addFlags(FLAG_ACTIVITY_NEW_TASK or FLAG_ACTIVITY_CLEAR_TASK))` and `requireActivity().finish()`.

- [ ] **Step 3: Build + verify** — `assembleDebug` green; Account shows profile + rows that open the right screens; Sign out returns to Login and clears the session.

---

## Self-Review

**1. Spec coverage (spec §5 IA + core-tab screens §6):** 4-tab bottom nav + host → Task 1 ✓; Monitor (camera) → Task 2 ✓; History (list + trend) → Task 3 ✓; Dashboard → Task 4 ✓; Account hub consolidating secondary screens → Task 5 ✓. Login gate moved off HomePageActivity → Task 1 Step 5/8 ✓. Legacy Activities retained for Plan 4 cleanup (per spec §5.2) ✓. Auth screens + Account sub-screen redesigns + legal consolidation are explicitly Plans 3–4 (not here).

**2. Placeholder scan:** Port tasks (2, 3) reference the exact source Activities and name every method to carry over and every Activity→Fragment adaptation, rather than "TODO port logic." Layouts that are large (history/dashboard/account) are specified by structure + exact IDs + the Signal styles/tokens to use; the implementer has an unambiguous spec. No "add error handling"/"TBD".

**3. Type/name consistency:** menu item IDs = nav destination IDs (`dashboardFragment`/`monitorFragment`/`historyFragment`/`accountFragment`) so `setupWithNavController` maps them. `AlertHistoryItem` fields used (`alertType`, `reason`, `time`, `date`, `confidence`) match the model. `CameraService` constructor arg order matches its definition. View-binding class names (`ActivityMainBinding`, `FragmentMonitorBinding`) match the layout file names.

---

## Execution Handoff

Same as Plan 1: subagent-driven, one implementer + task review per task, final whole-branch review, then the SINGLE commit (per the user's commit-at-end policy). Task 2 (camera → fragment) is the highest-risk task — dispatch it on a standard model, not the cheapest, and device-verify the camera before proceeding.

package com.example.eyedtrack

import android.content.Intent
import android.os.Bundle
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.ImageView
import androidx.appcompat.app.AppCompatActivity
import androidx.viewpager2.widget.ViewPager2
import com.google.android.material.tabs.TabLayout
import com.google.android.material.tabs.TabLayoutMediator

class HelpActivity : AppCompatActivity() {

    private lateinit var viewPager: ViewPager2
    private lateinit var tabLayout: TabLayout
    private lateinit var adapter: HelpAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // full-screen
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )
        setContentView(R.layout.help)

        viewPager = findViewById(R.id.viewPager)
        tabLayout = findViewById(R.id.tabLayout)

        // if inside a ScrollView
        viewPager.isNestedScrollingEnabled = false

        // slide titles
        val titles = listOf(
            "Installation & Setup",
            "Using the System",
            "Troubleshoot & Support"
        )

        // slide sections
        val pageSections = listOf(
            listOf(
                "Mount the Camera"    to "Place EyeDTrack camera on your dashboard or windshield for a clear view of the driver’s face.",
                "Power On the Device" to "Ensure the system is connected to a power source and turn it on.",
                "Connect to the App"  to "Open the EyeDTrack app on your device and follow the on-screen instructions to pair it with the system."
            ),
            listOf(
                "Start Driving"       to "The system will automatically begin monitoring when the vehicle is in motion.",
                "Real-Time Monitoring" to "EyeDTrack analyzes your attention and drowsiness continuously.",
                "Alerts & Notification" to "If inattention is detected, the system will provide audio alerts to keep you focused."
            ),
            listOf(
                "Camera not Detecting?" to "Ensure the camera lens is clean and properly positioned.",
                "App not Connecting?"   to "Reconnect your internet and restart the app.",
                ""                      to "" // unused third section
            )
        )

        adapter = HelpAdapter(titles, pageSections)
        viewPager.adapter = adapter

        // 1) hide the default tab indicator (underline)
        tabLayout.setSelectedTabIndicatorHeight(0)

        // 2) attach mediator, give each tab an unselected‐dot icon
        TabLayoutMediator(tabLayout, viewPager) { tab, _ ->
            tab.setIcon(R.drawable.dot_unselected)
        }.attach()

        // 3) listen for page changes to swap in the selected dot
        viewPager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                super.onPageSelected(position)
                for (i in 0 until tabLayout.tabCount) {
                    val t = tabLayout.getTabAt(i)
                    t?.icon = if (i == position) {
                        getDrawable(R.drawable.dot_selected)
                    } else {
                        getDrawable(R.drawable.dot_unselected)
                    }
                }
            }
        })

        // 4) optional: allow tapping the dots to navigate
        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                viewPager.currentItem = tab.position
            }
            override fun onTabUnselected(tab: TabLayout.Tab) {}
            override fun onTabReselected(tab: TabLayout.Tab) {}
        })

        // bottom bar / header nav
        findViewById<ImageView>(R.id.back_button).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.home_icon).setOnClickListener {
            startActivity(Intent(this, HomePageActivity::class.java))
        }
        findViewById<ImageButton>(R.id.profile_icon).setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
        }
        findViewById<ImageButton>(R.id.settings_icon).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
    }
}

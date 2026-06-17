package com.example.eyedtrack

import android.animation.ObjectAnimator
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageButton
import android.widget.ImageView
import androidx.appcompat.app.AppCompatActivity
import android.util.Log
import android.view.Menu
import android.view.MenuItem

class SettingsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 1) Inflate your layout first
        setContentView(R.layout.settings_page)

        // 2) Fullscreen mode
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        // 3) Wire up ALL your views here, after setContentView
        val btnGoToProfile = findViewById<ImageButton>(R.id.profile_icon)
        val btnGoToHome    = findViewById<ImageButton>(R.id.home_icon)
        val btnHelp        = findViewById<Button>(R.id.help)
        val btnSounds      = findViewById<Button>(R.id.sounds)
        val btnDataPrivacy = findViewById<Button>(R.id.data_and_privacy)
        val btnFAQs        = findViewById<Button>(R.id.faqs)
        val btnAboutUs     = findViewById<Button>(R.id.about_us)
        val btnEULA        = findViewById<Button>(R.id.eula_button)
        val btnDPA         = findViewById<Button>(R.id.dpa_button)

        // 4) Optional: scale your icons
        scaleImageButton(findViewById(R.id.settings_icon))

        // 5) Now set click-listeners
        btnGoToProfile.setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
        }
        btnGoToHome.setOnClickListener {
            startActivity(Intent(this, HomePageActivity::class.java))
        }

        // This one will now actually be non-null and fire
        btnHelp.setOnClickListener {
            Log.d("SettingsActivity","Help CLICKED")
            startActivity(Intent(this, HelpActivity::class.java))
        }

        btnSounds.setOnClickListener {
            startActivity(Intent(this, SoundsActivity::class.java))
        }
        btnDataPrivacy.setOnClickListener {
            startActivity(Intent(this, DataPrivacyActivity::class.java))
        }
        btnFAQs.setOnClickListener {
            startActivity(Intent(this, FAQsActivity::class.java))
        }
        btnAboutUs.setOnClickListener {
            startActivity(Intent(this, AboutUsActivity::class.java))
        }
        btnEULA.setOnClickListener {
            startActivity(Intent(this, EulaActivity::class.java))
        }
        btnDPA.setOnClickListener {
            startActivity(Intent(this, DPAActivity::class.java))
        }
        
        // Add a secret tap counter to access debug screen
        var tapCount = 0
        val maxTaps = 5
        
        findViewById<ImageButton>(R.id.settings_icon).setOnLongClickListener {
            tapCount++
            if (tapCount >= maxTaps) {
                tapCount = 0
                startActivity(Intent(this, DebugPreferencesActivity::class.java))
            }
            true
        }
    }
    
    // Add debug menu options
    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Debug Preferences")
        return true
    }
    
    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        when (item.itemId) {
            1 -> {
                startActivity(Intent(this, DebugPreferencesActivity::class.java))
                return true
            }
        }
        return super.onOptionsItemSelected(item)
    }

    private fun scaleImageButton(button: View) {
        val scaleX = ObjectAnimator.ofFloat(button, "scaleX", 1.5f)
        val scaleY = ObjectAnimator.ofFloat(button, "scaleY", 1.5f)
        scaleX.duration = 300
        scaleY.duration = 300
        scaleX.start()
        scaleY.start()
    }
}

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

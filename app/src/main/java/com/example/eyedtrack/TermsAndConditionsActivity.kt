package com.example.eyedtrack

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import androidx.appcompat.app.AppCompatActivity

// Activity for displaying Terms and Conditions to the user.
class TermsAndConditionsActivity : AppCompatActivity() {

    // Called when the activity is created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.terms_and_conditions) // Set the layout resource for this activity.

        // Initialize buttons.
        val btnAccept = findViewById<Button>(R.id.btnAccept)
        val btnReject = findViewById<Button>(R.id.btnReject)

        // Handle acceptance of terms: save acceptance and proceed to LoginActivity.
        btnAccept.setOnClickListener {
            PreferenceManager.setAccepted(this, true)
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
        }

        // Handle rejection of terms: save rejection and close the app.
        btnReject.setOnClickListener {
            PreferenceManager.setAccepted(this, false)
            finishAffinity()
        }
    }
}
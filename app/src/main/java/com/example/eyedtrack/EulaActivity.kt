package com.example.eyedtrack

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

// Activity that displays the End User License Agreement (EULA) content.
class EulaActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.eula)

        // Wire top bar: back button and title.
        val topBar = findViewById<android.view.View>(R.id.top_bar)
        topBar.findViewById<android.widget.ImageView>(R.id.btn_back).setOnClickListener { finish() }
        topBar.findViewById<android.widget.TextView>(R.id.top_bar_title).text = "EULA"

        // Display the EULA content from string resources.
        val eulaTextView = findViewById<TextView>(R.id.eula_text)
        eulaTextView.text = getString(R.string.eula_content)
    }
}

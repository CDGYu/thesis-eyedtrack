package com.example.eyedtrack

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

// Activity that displays the Data Processing Agreement (DPA) content.
class DPAActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.dpa)

        // Wire top bar: back button and title.
        val topBar = findViewById<android.view.View>(R.id.top_bar)
        topBar.findViewById<android.widget.ImageView>(R.id.btn_back).setOnClickListener { finish() }
        topBar.findViewById<android.widget.TextView>(R.id.top_bar_title).text = "Data Processing Agreement"

        // Display the DPA content from string resources.
        val dpaTextView = findViewById<TextView>(R.id.dpa_text)
        dpaTextView.text = getString(R.string.dpa_content)
    }
}

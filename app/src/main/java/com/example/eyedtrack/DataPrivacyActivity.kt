package com.example.eyedtrack

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity

// Activity that displays the Data Privacy screen.
class DataPrivacyActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.data_privacy)

        // Wire top bar: back button and title.
        val topBar = findViewById<android.view.View>(R.id.top_bar)
        topBar.findViewById<android.widget.ImageView>(R.id.btn_back).setOnClickListener { finish() }
        topBar.findViewById<android.widget.TextView>(R.id.top_bar_title).text = "Data & privacy"
    }
}

package com.example.eyedtrack

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

// Activity that displays the Frequently Asked Questions (FAQs) screen.
class FAQsActivity : AppCompatActivity() {

    // Called when the activity is first created.
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        // Set the layout resource for this activity.
        setContentView(R.layout.faqs)

        // Initialize the back button to close the activity.
        val backButton = findViewById<ImageView>(R.id.back_button)

        // Initialize navigation buttons.
        val btnGoToSettings = findViewById<ImageButton>(R.id.settings_icon)
        val btnGoToProfileActivity = findViewById<ImageButton>(R.id.profile_icon)
        val btnGoToHomePageActivity = findViewById<ImageButton>(R.id.home_icon)

        // Handle back button click to close the activity.
        backButton.setOnClickListener { finish() }

        // Set click listeners for navigation buttons.
        btnGoToProfileActivity.setOnClickListener {
            startActivity(Intent(this, ProfileActivity::class.java))
        }
        btnGoToSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        btnGoToHomePageActivity.setOnClickListener {
            startActivity(Intent(this, HomePageActivity::class.java))
        }

        // Initialize FAQ toggle functionality.
        setupFaqToggle(R.id.question_1, R.id.answer_1, R.id.icon_1)
        setupFaqToggle(R.id.question_2, R.id.answer_2, R.id.icon_2)
        setupFaqToggle(R.id.question_3, R.id.answer_3, R.id.icon_3)
        setupFaqToggle(R.id.question_4, R.id.answer_4, R.id.icon_4)
        setupFaqToggle(R.id.question_5, R.id.answer_5, R.id.icon_5)
        setupFaqToggle(R.id.question_6, R.id.answer_6, R.id.icon_6)
    }

    // Sets up a click listener for a FAQ question and its corresponding icon to toggle the answer visibility.
    private fun setupFaqToggle(questionId: Int, answerId: Int, iconId: Int) {
        val questionTextView = findViewById<TextView>(questionId)
        val answerTextView = findViewById<TextView>(answerId)
        val iconImageView = findViewById<ImageView>(iconId)

        // Toggle answer visibility when the question is clicked.
        questionTextView.setOnClickListener {
            toggleAnswerWithAnimation(answerTextView, iconImageView)
        }

        // Toggle answer visibility when the icon is clicked.
        iconImageView.setOnClickListener {
            toggleAnswerWithAnimation(answerTextView, iconImageView)
        }
    }

    // Toggles the visibility of an answer with a fade animation.
    private fun toggleAnswerWithAnimation(answerTextView: TextView, iconImageView: ImageView) {
        if (answerTextView.visibility == View.GONE) {
            // Expand the answer with fade-in animation.
            answerTextView.apply {
                visibility = View.VISIBLE
                alpha = 0f
                animate()
                    .alpha(1f)
                    .setDuration(200)
                    .withStartAction { requestLayout() } // Ensure proper layout adjustment.
                    .start()
            }
            // Update the icon to indicate expanded state.
            iconImageView.setImageResource(R.drawable.arrow_up)
        } else {
            // Collapse the answer with fade-out animation.
            answerTextView.animate()
                .alpha(0f)
                .setDuration(200)
                .withEndAction {
                    answerTextView.visibility = View.GONE
                    answerTextView.requestLayout() // Adjust layout after hiding.
                }
                .start()
            // Update the icon to indicate collapsed state.
            iconImageView.setImageResource(R.drawable.arrow_down)
        }
    }
}
package com.example.eyedtrack.adapter

import android.graphics.drawable.GradientDrawable
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.example.eyedtrack.R
import com.example.eyedtrack.model.AlertHistoryItem

/**
 * Adapter for displaying alert history items in a RecyclerView
 */
class AlertHistoryAdapter(private var alertItems: List<AlertHistoryItem>) : 
    RecyclerView.Adapter<AlertHistoryAdapter.AlertViewHolder>() {

    class AlertViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val dateText: TextView = itemView.findViewById(R.id.alert_date)
        val timeText: TextView = itemView.findViewById(R.id.alert_time)
        val reasonText: TextView = itemView.findViewById(R.id.alert_reason)
        val behaviorText: TextView = itemView.findViewById(R.id.alert_behavior)
        val alertTypeText: TextView = itemView.findViewById(R.id.alert_type)
        val confidenceText: TextView = itemView.findViewById(R.id.alert_confidence)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AlertViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.alert_history_item, parent, false)
        return AlertViewHolder(view)
    }

    override fun onBindViewHolder(holder: AlertViewHolder, position: Int) {
        val currentItem = alertItems[position]
        
        holder.dateText.text = currentItem.date
        holder.timeText.text = currentItem.time
        holder.reasonText.text = currentItem.reason
        holder.behaviorText.text = currentItem.behaviorOutput
        holder.alertTypeText.text = currentItem.alertType
        holder.confidenceText.text = "${currentItem.confidence}%"
        
        // Create rounded background for confidence badge
        val drawable = GradientDrawable()
        drawable.shape = GradientDrawable.RECTANGLE
        drawable.cornerRadius = 24f // 12dp converted to pixels
        
        // Set confidence color and background based on level
        when {
            currentItem.confidence >= 80 -> {
                holder.confidenceText.setTextColor(0xFFFFFFFF.toInt()) // White text
                drawable.setColor(0xFFFF4444.toInt()) // Red background for high confidence
            }
            currentItem.confidence >= 60 -> {
                holder.confidenceText.setTextColor(0xFFFFFFFF.toInt()) // White text
                drawable.setColor(0xFFFF8800.toInt()) // Orange background for medium confidence
            }
            else -> {
                holder.confidenceText.setTextColor(0xFF000000.toInt()) // Black text
                drawable.setColor(0xFFFFDD00.toInt()) // Yellow background for lower confidence
            }
        }
        
        holder.confidenceText.background = drawable
    }

    override fun getItemCount(): Int = alertItems.size

    fun updateAlerts(newAlerts: List<AlertHistoryItem>) {
        val oldCount = alertItems.size
        val oldLatestTime = if (alertItems.isNotEmpty()) "${alertItems.first().date}T${alertItems.first().time}" else "None"
        
        // Clear old data first, then replace with new data
        alertItems = emptyList()
        
        // Force UI update to clear old items
        notifyDataSetChanged()
        
        // Now set new data
        alertItems = newAlerts.toList() // Create a new list to avoid reference issues
        
        val newCount = alertItems.size
        val newLatestTime = if (alertItems.isNotEmpty()) "${alertItems.first().date}T${alertItems.first().time}" else "None"
        
        // Log the replacement for debugging
        android.util.Log.d("AlertHistoryAdapter", 
            "🔄 Alert data replaced: $oldCount → $newCount items | Latest: $oldLatestTime → $newLatestTime")
        
        // Force complete UI refresh
        notifyDataSetChanged()
        
        // Additional notification for specific changes if needed
        if (newCount > 0) {
            // Ensure the RecyclerView scrolls to the top to show latest alerts
            android.util.Log.d("AlertHistoryAdapter", "📍 Notified adapter of ${newCount} new alerts")
        }
    }
} 
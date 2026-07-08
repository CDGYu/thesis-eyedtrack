package com.example.eyedtrack.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.example.eyedtrack.R
import com.example.eyedtrack.model.AlertHistoryItem

/**
 * Adapter for displaying alert history items in a RecyclerView.
 * Uses Signal-style item_alert layout with severity-dot coloring.
 */
class AlertHistoryAdapter(private var alertItems: List<AlertHistoryItem>) :
    RecyclerView.Adapter<AlertHistoryAdapter.AlertViewHolder>() {

    class AlertViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val alertType: TextView = itemView.findViewById(R.id.alert_type)
        val alertReason: TextView = itemView.findViewById(R.id.alert_reason)
        val alertTime: TextView = itemView.findViewById(R.id.alert_time)
        val severityDot: View = itemView.findViewById(R.id.severity_dot)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AlertViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_alert, parent, false)
        return AlertViewHolder(view)
    }

    override fun onBindViewHolder(holder: AlertViewHolder, position: Int) {
        val item = alertItems[position]
        holder.alertType.text = item.alertType
        holder.alertReason.text = item.reason.substringBefore(" (")
        holder.alertTime.text = item.time
        val severe = item.alertType.contains("Drows", ignoreCase = true) ||
                     item.alertType.contains("Multiple", ignoreCase = true)
        holder.severityDot.setBackgroundResource(
            if (severe) R.drawable.pill_alert else R.drawable.pill_caution
        )
    }

    override fun getItemCount(): Int = alertItems.size

    fun updateAlerts(newAlerts: List<AlertHistoryItem>) {
        alertItems = newAlerts.toList()
        notifyDataSetChanged()
    }
}

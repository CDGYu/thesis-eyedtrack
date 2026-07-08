package com.example.eyedtrack.ui

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.navigation.fragment.findNavController
import com.example.eyedtrack.PreferenceManager
import com.example.eyedtrack.R
import com.example.eyedtrack.databinding.FragmentDashboardBinding
import com.example.eyedtrack.utils.AlertLogLoader
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class DashboardFragment : Fragment() {

    private var _binding: FragmentDashboardBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?
    ): View {
        _binding = FragmentDashboardBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // Greeting — "Good day, <firstName>" with "Driver" fallback
        val firstName = PreferenceManager.getUserData(requireContext())["firstName"]
            ?.takeIf { it.isNotBlank() } ?: "Driver"
        binding.tvGreeting.text = "Good day, $firstName"

        // Start Monitoring button navigates to the Monitor tab
        binding.btnStart.setOnClickListener {
            findNavController().navigate(R.id.monitorFragment)
        }

        loadAlerts()
    }

    private fun loadAlerts() {
        // Capture application context so the IO block doesn't touch fragment state
        val appCtx = requireContext().applicationContext
        viewLifecycleOwner.lifecycleScope.launch {
            val alerts = withContext(Dispatchers.IO) {
                AlertLogLoader(appCtx).loadAlertLogs(200)
            }

            // Guard: view may have been destroyed while IO was in flight
            val b = _binding ?: return@launch

            // Stat tiles
            val today = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
            b.statTodayValue.text = alerts.count { it.date == today }.toString()
            b.statTotalValue.text = alerts.size.toString()

            // Recent alerts — up to 3 rows inflated into recent_container
            b.recentContainer.removeAllViews()
            val rowInflater = LayoutInflater.from(b.recentContainer.context)
            val recent = alerts.take(3)
            if (recent.isEmpty()) {
                val emptyMsg = TextView(b.recentContainer.context).apply {
                    text = "No recent alerts"
                    setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_BodyMedium)
                    setTextColor(ContextCompat.getColor(b.recentContainer.context, R.color.text_mid))
                    val pad = resources.getDimensionPixelSize(R.dimen.space_lg)
                    setPadding(pad, pad, pad, pad)
                }
                b.recentContainer.addView(emptyMsg)
            } else {
                recent.forEach { item ->
                    val row = rowInflater.inflate(R.layout.item_alert, b.recentContainer, false)
                    row.findViewById<TextView>(R.id.alert_type).text = item.alertType
                    row.findViewById<TextView>(R.id.alert_reason).text =
                        item.reason.substringBefore(" (")
                    row.findViewById<TextView>(R.id.alert_time).text = item.time
                    val severe = item.alertType.contains("Drows", ignoreCase = true) ||
                            item.alertType.contains("Multiple", ignoreCase = true)
                    row.findViewById<View>(R.id.severity_dot).setBackgroundResource(
                        if (severe) R.drawable.pill_alert else R.drawable.pill_caution
                    )
                    b.recentContainer.addView(row)
                }
            }
        }
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }
}

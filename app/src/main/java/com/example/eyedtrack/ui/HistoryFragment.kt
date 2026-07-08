package com.example.eyedtrack.ui

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.eyedtrack.R
import com.example.eyedtrack.adapter.AlertHistoryAdapter
import com.example.eyedtrack.databinding.FragmentHistoryBinding
import com.example.eyedtrack.model.AlertHistoryItem
import com.example.eyedtrack.utils.AlertLogLoader
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

class HistoryFragment : Fragment() {

    private var _binding: FragmentHistoryBinding? = null
    private val binding get() = _binding!!

    private lateinit var alertAdapter: AlertHistoryAdapter

    private val autoRefreshHandler = Handler(Looper.getMainLooper())
    private var autoRefreshRunnable: Runnable? = null
    private val AUTO_REFRESH_INTERVAL = 10_000L

    companion object {
        private const val TAG = "HistoryFragment"
    }

    // ─── View lifecycle ───────────────────────────────────────────────────────

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentHistoryBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // RecyclerView
        alertAdapter = AlertHistoryAdapter(emptyList())
        binding.alertsRecycler.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = alertAdapter
        }

        // Swipe-to-refresh
        binding.swipeRefresh.setOnRefreshListener { loadAlertLogs() }

        // Build empty trend bar stubs (populated after first data load)
        buildTrendBars()

        // Initial data load
        loadAlertLogs()
    }

    override fun onResume() {
        super.onResume()
        startAutoRefresh()
    }

    override fun onPause() {
        super.onPause()
        stopAutoRefresh()
    }

    override fun onDestroyView() {
        stopAutoRefresh()
        _binding = null
        super.onDestroyView()
    }

    // ─── Trend bars ───────────────────────────────────────────────────────────

    /** Creates 7 equal-width bar stubs in trend_row, to be sized in updateTrendBars. */
    private fun buildTrendBars() {
        val row = _binding?.trendRow ?: return
        row.removeAllViews()
        val minPx = dpToPx(4)
        repeat(7) {
            val bar = View(requireContext())
            val lp = LinearLayout.LayoutParams(0, minPx, 1f)
            lp.setMargins(dpToPx(2), 0, dpToPx(2), 0)
            bar.layoutParams = lp
            bar.setBackgroundResource(R.drawable.pill_caution)
            row.addView(bar)
        }
    }

    /**
     * Buckets [items] into the last 7 calendar days and sets each bar's height
     * proportional to that day's count (min 4dp, max 56dp).
     */
    private fun updateTrendBars(items: List<AlertHistoryItem>) {
        val row = _binding?.trendRow ?: return
        val maxPx = dpToPx(56)
        val minPx = dpToPx(4)

        val sdf = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        // Index 0 = oldest day (6 days ago), index 6 = today
        val days = (6 downTo 0).map { offset ->
            sdf.format(Date(System.currentTimeMillis() - offset * 86_400_000L))
        }

        val counts = days.map { day -> items.count { it.date == day } }
        val maxCount = counts.maxOrNull()?.takeIf { it > 0 } ?: 1

        for (i in 0 until row.childCount) {
            val bar = row.getChildAt(i)
            val count = counts.getOrElse(i) { 0 }
            val heightPx = if (count == 0) minPx
            else (minPx + (maxPx - minPx) * count.toFloat() / maxCount).roundToInt()

            val lp = bar.layoutParams as LinearLayout.LayoutParams
            lp.height = heightPx
            bar.layoutParams = lp   // triggers requestLayout on the bar

            bar.setBackgroundResource(
                if (count > 0) R.drawable.pill_alert else R.drawable.pill_caution
            )
        }
    }

    // ─── Data loading ─────────────────────────────────────────────────────────

    private fun loadAlertLogs() {
        if (_binding == null) return  // view not attached — skip silently

        viewLifecycleOwner.lifecycleScope.launch {
            try {
                val loader = AlertLogLoader(requireContext())
                val items: List<AlertHistoryItem> = withContext(Dispatchers.IO) {
                    loader.loadAlertLogs(100)
                }

                _binding?.let { b ->
                    if (items.isEmpty()) {
                        b.alertsRecycler.visibility = View.GONE
                        b.emptyText.visibility = View.VISIBLE
                    } else {
                        b.alertsRecycler.visibility = View.VISIBLE
                        b.emptyText.visibility = View.GONE
                        alertAdapter.updateAlerts(items)
                        b.alertsRecycler.scrollToPosition(0)
                    }
                    updateTrendBars(items)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error loading alert logs: ${e.message}", e)
                _binding?.let { b ->
                    b.alertsRecycler.visibility = View.GONE
                    b.emptyText.visibility = View.VISIBLE
                }
            } finally {
                _binding?.swipeRefresh?.isRefreshing = false
            }
        }
    }

    // ─── Auto-refresh ─────────────────────────────────────────────────────────

    private fun startAutoRefresh() {
        stopAutoRefresh()   // clear any leftover runnable before scheduling a new one
        val runnable = object : Runnable {
            override fun run() {
                loadAlertLogs()
                autoRefreshHandler.postDelayed(this, AUTO_REFRESH_INTERVAL)
            }
        }
        autoRefreshRunnable = runnable
        autoRefreshHandler.postDelayed(runnable, AUTO_REFRESH_INTERVAL)
    }

    private fun stopAutoRefresh() {
        autoRefreshRunnable?.let { autoRefreshHandler.removeCallbacks(it) }
        autoRefreshRunnable = null
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private fun dpToPx(dp: Int): Int =
        (dp * resources.displayMetrics.density + 0.5f).toInt()
}

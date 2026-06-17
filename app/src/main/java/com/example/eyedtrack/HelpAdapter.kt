package com.example.eyedtrack

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.widget.ViewPager2

class HelpAdapter(
    private val titles: List<String>,
    private val pageSections: List<List<Pair<String, String>>>
) : RecyclerView.Adapter<HelpAdapter.HelpViewHolder>() {

    inner class HelpViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val title       : TextView = itemView.findViewById(R.id.slider_title)
        val sec1Header  : TextView = itemView.findViewById(R.id.sec1_header)
        val sec1Body    : TextView = itemView.findViewById(R.id.sec1_body)
        val sec2Header  : TextView = itemView.findViewById(R.id.sec2_header)
        val sec2Body    : TextView = itemView.findViewById(R.id.sec2_body)
        val sec3Header  : TextView = itemView.findViewById(R.id.sec3_header)
        val sec3Body    : TextView = itemView.findViewById(R.id.sec3_body)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): HelpViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.help_item, parent, false)
        return HelpViewHolder(view)
    }

    override fun onBindViewHolder(holder: HelpViewHolder, position: Int) {
        // Title
        holder.title.text = titles[position]

        // Fill sections
        val sections = pageSections[position]
        holder.sec1Header.text = sections.getOrNull(0)?.first.orEmpty()
        holder.sec1Body  .text = sections.getOrNull(0)?.second.orEmpty()

        holder.sec2Header.text = sections.getOrNull(1)?.first.orEmpty()
        holder.sec2Body  .text = sections.getOrNull(1)?.second.orEmpty()

        holder.sec3Header.text = sections.getOrNull(2)?.first.orEmpty()
        holder.sec3Body  .text = sections.getOrNull(2)?.second.orEmpty()

        // (No Next button handling here—you swipe)
    }

    override fun getItemCount(): Int = titles.size
}

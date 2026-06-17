package com.example.eyedtrack

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

/**
 * Activity for managing user accounts.
 * Allows viewing and deleting individual users.
 */
class UserManagementActivity : AppCompatActivity() {

    private lateinit var recyclerView: RecyclerView
    private lateinit var adapter: UserAdapter
    private var usersList = listOf<Map<String, String>>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_user_management)

        // Enable fullscreen mode by hiding the status bar.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )

        // Set up RecyclerView
        recyclerView = findViewById(R.id.recyclerViewUsers)
        recyclerView.layoutManager = LinearLayoutManager(this)
        
        // Get list of users
        refreshUsersList()
        
        // Set up refresh button
        val refreshButton = findViewById<Button>(R.id.btnRefresh)
        refreshButton.setOnClickListener {
            refreshUsersList()
        }
    }
    
    private fun refreshUsersList() {
        usersList = PreferenceManager.getAllUsers(this)
        adapter = UserAdapter(usersList) { position ->
            // Handle delete action
            val user = usersList[position]
            confirmDeleteUser(user)
        }
        recyclerView.adapter = adapter
        
        // Update count
        val countTextView = findViewById<TextView>(R.id.txtUserCount)
        countTextView.text = "Total Users: ${usersList.size}"
    }
    
    private fun confirmDeleteUser(user: Map<String, String>) {
        val email = user["email"] ?: return
        val name = "${user["firstName"]} ${user["lastName"]}"
        
        AlertDialog.Builder(this)
            .setTitle("Delete User")
            .setMessage("Are you sure you want to delete the account for $name ($email)?")
            .setPositiveButton("Delete") { _, _ ->
                if (PreferenceManager.deleteUserByEmail(this, email)) {
                    Toast.makeText(this, "User deleted successfully", Toast.LENGTH_SHORT).show()
                    refreshUsersList()
                    
                    // Log the action for terminal access
                    PreferencesDebugger.logAllUsers(this)
                } else {
                    Toast.makeText(this, "Failed to delete user", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }
    
    /**
     * Adapter for the RecyclerView to display users
     */
    inner class UserAdapter(
        private val users: List<Map<String, String>>,
        private val onDeleteClick: (Int) -> Unit
    ) : RecyclerView.Adapter<UserAdapter.UserViewHolder>() {
        
        inner class UserViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            val txtName: TextView = itemView.findViewById(R.id.txtName)
            val txtEmail: TextView = itemView.findViewById(R.id.txtEmail)
            val txtMobile: TextView = itemView.findViewById(R.id.txtMobile)
            val btnDelete: Button = itemView.findViewById(R.id.btnDelete)
            
            init {
                btnDelete.setOnClickListener {
                    onDeleteClick(adapterPosition)
                }
            }
        }
        
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): UserViewHolder {
            val view = LayoutInflater.from(parent.context)
                .inflate(R.layout.item_user, parent, false)
            return UserViewHolder(view)
        }
        
        override fun onBindViewHolder(holder: UserViewHolder, position: Int) {
            val user = users[position]
            holder.txtName.text = "${user["firstName"]} ${user["lastName"]}"
            holder.txtEmail.text = user["email"]
            holder.txtMobile.text = user["mobile"]
        }
        
        override fun getItemCount(): Int = users.size
    }
} 
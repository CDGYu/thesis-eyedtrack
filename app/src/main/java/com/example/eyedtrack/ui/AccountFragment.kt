package com.example.eyedtrack.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import com.example.eyedtrack.DataPrivacyActivity
import com.example.eyedtrack.HelpActivity
import com.example.eyedtrack.LoginActivity
import com.example.eyedtrack.PreferenceManager
import com.example.eyedtrack.ProfileActivity
import com.example.eyedtrack.SoundsActivity
import com.example.eyedtrack.UserManagementActivity
import com.example.eyedtrack.databinding.FragmentAccountBinding

class AccountFragment : Fragment() {

    private var _binding: FragmentAccountBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?
    ): View {
        _binding = FragmentAccountBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // Bind profile data from preferences
        val userData = PreferenceManager.getUserData(requireContext())
        val firstName = userData["firstName"]?.takeIf { it.isNotBlank() } ?: ""
        val lastName  = userData["lastName"]?.takeIf  { it.isNotBlank() } ?: ""
        val email     = userData["email"]    ?: ""

        val fullName = "$firstName $lastName".trim().ifBlank { "Driver" }
        val initial  = firstName.firstOrNull()?.uppercaseChar()?.toString() ?: "D"

        binding.profileName.text    = fullName
        binding.profileEmail.text   = email
        binding.profileInitial.text = initial

        // Row click listeners
        binding.rowProfile.setOnClickListener {
            startActivity(Intent(requireContext(), ProfileActivity::class.java))
        }
        binding.rowSounds.setOnClickListener {
            startActivity(Intent(requireContext(), SoundsActivity::class.java))
        }
        binding.rowUsers.setOnClickListener {
            startActivity(Intent(requireContext(), UserManagementActivity::class.java))
        }
        binding.rowPrivacy.setOnClickListener {
            startActivity(Intent(requireContext(), DataPrivacyActivity::class.java))
        }
        binding.rowHelp.setOnClickListener {
            startActivity(Intent(requireContext(), HelpActivity::class.java))
        }

        // Sign out
        binding.btnSignOut.setOnClickListener {
            PreferenceManager.setLoggedIn(requireContext(), false)
            startActivity(
                Intent(requireContext(), LoginActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                }
            )
            requireActivity().finish()
        }
    }

    override fun onDestroyView() {
        _binding = null
        super.onDestroyView()
    }
}

package com.skn29.watercare.technicianapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import com.skn29.watercare.ui.theme.WaterCareTheme

class TechnicianMainActivity :
    ComponentActivity() {

    override fun onCreate(
        savedInstanceState: Bundle?
    ) {
        super.onCreate(savedInstanceState)

        WindowCompat.setDecorFitsSystemWindows(
            window,
            false
        )

        setContent {
            WaterCareTheme {
                TechnicianHomeApp()
            }
        }
    }
}

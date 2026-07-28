package com.skn29.watercare.technician

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.skn29.watercare.technician.app.navigation.TechnicianNavigation
import com.skn29.watercare.technician.ui.theme.WaterCareTechnicianTheme

class TechnicianMainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            WaterCareTechnicianTheme {
                TechnicianNavigation()
            }
        }
    }
}

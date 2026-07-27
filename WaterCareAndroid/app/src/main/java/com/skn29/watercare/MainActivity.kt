package com.skn29.watercare

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.view.WindowCompat
import com.skn29.watercare.ui.WaterCareApp
import com.skn29.watercare.ui.theme.WaterCareTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContent {
            WaterCareTheme {
                WaterCareApp()
            }
        }
    }
}

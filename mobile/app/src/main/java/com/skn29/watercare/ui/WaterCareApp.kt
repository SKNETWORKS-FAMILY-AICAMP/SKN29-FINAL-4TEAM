package com.skn29.watercare.ui

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.skn29.watercare.ui.customer.CustomerHomeScreen
import com.skn29.watercare.ui.customer.CustomerTrackingScreen
import com.skn29.watercare.ui.customer.ErrorResultScreen
import com.skn29.watercare.ui.customer.QrScanScreen
import com.skn29.watercare.ui.customer.QuestionnaireScreen
import com.skn29.watercare.ui.customer.VisitStatusScreen

@Composable
fun WaterCareApp() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = Routes.CUSTOMER_HOME
    ) {
        composable(Routes.CUSTOMER_HOME) {
            CustomerHomeScreen(
                onQrScan = { navController.navigate(Routes.QR_SCAN) },
                onQuestionnaire = { navController.navigate(Routes.QUESTIONNAIRE) },
                onOpenVisit = { navController.navigate(Routes.VISIT_STATUS) }
            )
        }
        composable(Routes.QR_SCAN) {
            QrScanScreen(
                onBack = navController::popBackStack,
                onErrorFound = { navController.navigate(Routes.ERROR_RESULT) },
                onQuestionnaireRequired = {
                    navController.navigate(Routes.QUESTIONNAIRE) {
                        popUpTo(Routes.QR_SCAN) { inclusive = true }
                    }
                }
            )
        }
        composable(Routes.QUESTIONNAIRE) {
            QuestionnaireScreen(
                onBack = navController::popBackStack,
                onErrorFound = { navController.navigate(Routes.ERROR_RESULT) }
            )
        }
        composable(Routes.ERROR_RESULT) {
            ErrorResultScreen(
                onBack = navController::popBackStack,
                onVisitRequested = {
                    navController.navigate(Routes.VISIT_STATUS) {
                        popUpTo(Routes.CUSTOMER_HOME)
                    }
                }
            )
        }
        composable(Routes.VISIT_STATUS) {
            VisitStatusScreen(
                onBack = navController::popBackStack,
                onTracking = { navController.navigate(Routes.TRACKING) }
            )
        }
        composable(Routes.TRACKING) {
            CustomerTrackingScreen(onBack = navController::popBackStack)
        }
    }
}

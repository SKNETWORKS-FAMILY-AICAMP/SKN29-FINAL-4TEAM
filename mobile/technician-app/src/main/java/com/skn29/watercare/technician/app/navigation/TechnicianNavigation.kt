package com.skn29.watercare.technician.app.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.skn29.watercare.technician.feature.visitdetail.VisitDetailScreen
import com.skn29.watercare.technician.feature.visitresult.VisitResultScreen
import com.skn29.watercare.technician.feature.worklist.TechnicianWorkListScreen

@Composable
fun TechnicianNavigation() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = TechnicianRoute.WORK_LIST
    ) {
        composable(TechnicianRoute.WORK_LIST) {
            TechnicianWorkListScreen(
                onVisitClick = { callId ->
                    navController.navigate(
                        TechnicianRoute.visitDetail(callId)
                    )
                }
            )
        }

        composable(
            route = TechnicianRoute.VISIT_DETAIL,
            arguments = listOf(
                navArgument("visitId") {
                    type = NavType.StringType
                }
            )
        ) { entry ->
            val callId = entry.arguments
                ?.getString("visitId")
                .orEmpty()

            VisitDetailScreen(
                visitId = callId,
                onBack = navController::popBackStack,
                onRegisterResult = {
                    navController.navigate(
                        TechnicianRoute.visitResult(callId)
                    )
                }
            )
        }

        composable(
            route = TechnicianRoute.VISIT_RESULT,
            arguments = listOf(
                navArgument("visitId") {
                    type = NavType.StringType
                }
            )
        ) { entry ->
            val callId = entry.arguments
                ?.getString("visitId")
                .orEmpty()

            VisitResultScreen(
                visitId = callId,
                onBack = navController::popBackStack,
                onCompleted = {
                    navController.popBackStack(
                        TechnicianRoute.WORK_LIST,
                        inclusive = false
                    )
                }
            )
        }
    }
}

package com.skn29.watercare.customer.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.customer.feature.auth.LoginScreen
import com.skn29.watercare.customer.feature.customer.guidance.GuidanceScreen
import com.skn29.watercare.customer.feature.customer.home.CustomerHomeScreen
import com.skn29.watercare.customer.feature.customer.inquirycreated.InquiryCreatedScreen
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeScreen

@Composable
fun CustomerNavigation(runtimeSubscriptionId: String) {
    val navController = rememberNavController()
    NavHost(navController = navController, startDestination = CustomerRoute.LOGIN) {
        composable(CustomerRoute.LOGIN) {
            LoginScreen(
                onAuthenticated = { offline ->
                    navController.navigate(CustomerRoute.home(offline)) {
                        popUpTo(CustomerRoute.LOGIN) { inclusive = true }
                    }
                }
            )
        }
        composable(
            route = CustomerRoute.HOME,
            arguments = listOf(navArgument("offline") {
                type = NavType.BoolType
                defaultValue = false
            }),
        ) { entry ->
            CustomerHomeScreen(
                offlinePreview = entry.arguments?.getBoolean("offline") ?: false,
                onStartIntake = { _ ->
                    val selectedSubscriptionId = runtimeSubscriptionId.ifBlank { "UNCONFIGURED" }
                    navController.navigate(CustomerRoute.intake(selectedSubscriptionId))
                },
                onOpenGuidance = { inquiryId, scenario ->
                    navController.navigate(CustomerRoute.guidance(inquiryId, scenario.name))
                },
                onLogout = {
                    navController.navigate(CustomerRoute.LOGIN) {
                        popUpTo(CustomerRoute.HOME) { inclusive = true }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable(
            route = CustomerRoute.INTAKE,
            arguments = listOf(navArgument("subscriptionId") { type = NavType.StringType }),
        ) { entry ->
            SymptomIntakeScreen(
                subscriptionId = entry.arguments?.getString("subscriptionId").orEmpty(),
                onBack = { navController.popBackStack() },
                onAuthExpired = {
                    navController.navigate(CustomerRoute.LOGIN) {
                        popUpTo(CustomerRoute.HOME) {
                            inclusive = true
                        }
                        launchSingleTop = true
                    }
                },
                onCompleted = { submission ->
                    navController.navigate(
                        CustomerRoute.inquiryCreated(
                            submission.inquiryId,
                            submission.guidanceScenario,
                        )
                    )
                },
            )
        }
        composable(
            route = CustomerRoute.INQUIRY_CREATED,
            arguments = listOf(
                navArgument("inquiryId") { type = NavType.StringType },
                navArgument("scenario") { type = NavType.StringType },
            ),
        ) { entry ->
            val scenario = runCatching {
                MockScenario.valueOf(entry.arguments?.getString("scenario").orEmpty())
            }.getOrDefault(MockScenario.NO_EVIDENCE)
            InquiryCreatedScreen(
                inquiryId = entry.arguments?.getString("inquiryId").orEmpty(),
                previewScenario = scenario,
                onBack = { navController.popBackStack() },
                onOpenMockGuidance = { inquiryId, mockScenario ->
                    navController.navigate(CustomerRoute.guidance(inquiryId, mockScenario.name))
                },
                onDone = {
                    navController.navigate(CustomerRoute.home(false)) {
                        popUpTo(CustomerRoute.HOME) { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable(
            route = CustomerRoute.GUIDANCE,
            arguments = listOf(
                navArgument("inquiryId") { type = NavType.StringType },
                navArgument("scenario") { type = NavType.StringType },
            ),
        ) { entry ->
            val scenario = runCatching {
                MockScenario.valueOf(entry.arguments?.getString("scenario").orEmpty())
            }.getOrDefault(MockScenario.NO_EVIDENCE)
            GuidanceScreen(
                inquiryId = entry.arguments?.getString("inquiryId").orEmpty(),
                scenario = scenario,
                onBack = { navController.popBackStack() },
                onRequestConsultation = {
                    // MOCK_BLOCKED: consultation Runtime route is not available yet.
                },
                onDone = {
                    navController.navigate(CustomerRoute.home(false)) {
                        popUpTo(CustomerRoute.HOME) { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
    }
}

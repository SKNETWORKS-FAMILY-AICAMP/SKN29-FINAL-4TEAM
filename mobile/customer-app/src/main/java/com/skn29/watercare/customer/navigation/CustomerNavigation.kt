package com.skn29.watercare.customer.navigation

import androidx.compose.animation.core.tween
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.fadeOut
import androidx.compose.animation.fadeIn
import androidx.compose.runtime.Composable
import androidx.navigation.NavController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.customer.feature.auth.LoginScreen
import com.skn29.watercare.customer.feature.customer.care.CareHistoryScreen
import com.skn29.watercare.customer.feature.customer.care.CarePrecheckScreen
import com.skn29.watercare.customer.feature.customer.guidance.FollowUpQuestionsScreen
import com.skn29.watercare.customer.feature.customer.guidance.GuidanceScreen
import com.skn29.watercare.customer.feature.customer.home.CustomerHomeScreen
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeScreen

@Composable
fun CustomerNavigation() {
    val navController =
        rememberNavController()

    NavHost(
        navController = navController,
        startDestination = CustomerRoute.LOGIN,
        enterTransition = {
            fadeIn(
                animationSpec = tween(320),
            ) +
                slideInHorizontally(
                    animationSpec = tween(420),
                    initialOffsetX = {
                        (it * 0.72f).toInt()
                    },
                )
        },
        exitTransition = {
            fadeOut(
                animationSpec = tween(220),
            ) +
                slideOutHorizontally(
                    animationSpec = tween(360),
                    targetOffsetX = {
                        -(it * 0.34f).toInt()
                    },
                )
        },
        popEnterTransition = {
            fadeIn(
                animationSpec = tween(300),
            ) +
                slideInHorizontally(
                    animationSpec = tween(400),
                    initialOffsetX = {
                        -(it * 0.58f).toInt()
                    },
                )
        },
        popExitTransition = {
            fadeOut(
                animationSpec = tween(220),
            ) +
                slideOutHorizontally(
                    animationSpec = tween(340),
                    targetOffsetX = {
                        (it * 0.52f).toInt()
                    },
                )
        },
    ) {
        composable(CustomerRoute.LOGIN) {
            LoginScreen(
                onAuthenticated = { offline ->
                    navController.navigate(
                        CustomerRoute.home(offline)
                    ) {
                        popUpTo(CustomerRoute.LOGIN) {
                            inclusive = true
                        }
                    }
                }
            )
        }

        composable(
            route = CustomerRoute.HOME,
            arguments = listOf(
                navArgument("offline") {
                    type = NavType.BoolType
                    defaultValue = false
                }
            ),
        ) { entry ->
            val offlinePreview =
                entry.arguments
                    ?.getBoolean("offline")
                    ?: false

            CustomerHomeScreen(
                offlinePreview = offlinePreview,
                onStartIntake = { subscriptionId ->
                    navController.navigate(
                        CustomerRoute.intake(
                            subscriptionId = subscriptionId,
                            fixturePreview = offlinePreview,
                        )
                    )
                },
                onStartIntakePreset = { subscriptionId, topic, rawText ->
                    navController.navigate(
                        CustomerRoute.intake(
                            subscriptionId = subscriptionId,
                            fixturePreview = offlinePreview,
                            initialTopic = topic.name,
                            initialRawText = rawText,
                        )
                    )
                },
                onOpenFollowUp = { inquiryId, scenario ->
                    navController.navigate(
                        CustomerRoute.followUp(
                            inquiryId = inquiryId,
                            scenario = scenario.name,
                        )
                    )
                },
                onOpenGuidance = {
                        inquiryId,
                        scenario,
                        statusCode,
                        stateVersion,
                        allowedActions,
                    ->
                    navController.navigate(
                        CustomerRoute.guidance(
                            inquiryId = inquiryId,
                            scenario = scenario.name,
                            statusCode = statusCode,
                            stateVersion = stateVersion,
                            allowedActions = allowedActions,
                            fixturePreview = offlinePreview,
                        )
                    )
                },
                onOpenCare = {
                    navController.navigate(
                        CustomerRoute.CARE
                    ) {
                        launchSingleTop = true
                    }
                },
                onLogout = {
                    navController.navigate(
                        CustomerRoute.LOGIN
                    ) {
                        popUpTo(CustomerRoute.HOME) {
                            inclusive = true
                        }
                        launchSingleTop = true
                    }
                },
            )
        }

        composable(
            route = CustomerRoute.CARE,
        ) {
            CareHistoryScreen(
                onBack = {
                    navController.popBackStack()
                },
                onStartPrecheck = { subscriptionId ->
                    navController.navigate(
                        CustomerRoute
                            .carePrecheck(
                                subscriptionId
                            )
                    )
                },
                onAuthExpired = {
                    navController.navigate(
                        CustomerRoute.LOGIN
                    ) {
                        popUpTo(
                            navController
                                .graph
                                .startDestinationId
                        ) {
                            inclusive = true
                        }
                        launchSingleTop = true
                    }
                },
            )
        }

        composable(
            route =
                CustomerRoute.CARE_PRECHECK,
            arguments = listOf(
                navArgument("subscriptionId") {
                    type = NavType.StringType
                }
            ),
        ) { entry ->
            CarePrecheckScreen(
                subscriptionId =
                    entry.arguments
                        ?.getString(
                            "subscriptionId"
                        )
                        .orEmpty(),
                onBack = {
                    navController
                        .popBackStack()
                },
                onAuthExpired = {
                    navController.navigate(
                        CustomerRoute.LOGIN
                    ) {
                        popUpTo(
                            navController
                                .graph
                                .startDestinationId
                        ) {
                            inclusive = true
                        }
                        launchSingleTop = true
                    }
                },
            )
        }

        composable(
            route = CustomerRoute.INTAKE,
            arguments = listOf(
                navArgument("subscriptionId") {
                    type = NavType.StringType
                },
                navArgument("fixturePreview") {
                    type = NavType.BoolType
                    defaultValue = false
                },
                navArgument("initialTopic") {
                    type = NavType.StringType
                    defaultValue = ""
                },
                navArgument("initialRawText") {
                    type = NavType.StringType
                    defaultValue = ""
                },
            ),
        ) { entry ->
            val fixturePreview =
                entry.arguments
                    ?.getBoolean("fixturePreview")
                    ?: false

            val initialTopic =
                entry.arguments
                    ?.getString("initialTopic")
                    ?.takeIf(String::isNotBlank)
                    ?.let { value ->
                        runCatching {
                            SymptomTopic.valueOf(value)
                        }.getOrNull()
                    }

            val initialRawText =
                entry.arguments
                    ?.getString("initialRawText")
                    .orEmpty()

            SymptomIntakeScreen(
                subscriptionId =
                    entry.arguments
                        ?.getString("subscriptionId")
                        .orEmpty(),
                initialTopic = initialTopic,
                initialRawText = initialRawText,
                onBack = {
                    navController.popBackStack()
                },
                onCompleted = { submission ->
                    if (fixturePreview) {
                        navController
                            .navigateReplacingCurrentCustomerStep(
                                route =
                                    CustomerRoute.guidance(
                                        inquiryId =
                                            submission.inquiryId,
                                        scenario =
                                            submission.guidanceScenario,
                                        inquiryCode =
                                            submission.inquiryCode,
                                        statusCode =
                                            submission.statusCode,
                                        stateVersion =
                                            submission.stateVersion,
                                        idempotentReplay =
                                            submission.idempotentReplay,
                                        allowedActions =
                                            submission.allowedActions,
                                        fixturePreview = true,
                                    ),
                                currentDestinationId =
                                    entry.destination.id,
                            )
                    } else {
                        navController.navigate(
                            CustomerRoute.followUp(
                                inquiryId =
                                    submission.inquiryId,
                                scenario =
                                    submission.guidanceScenario,
                                inquiryCode =
                                    submission.inquiryCode,
                                idempotentReplay =
                                    submission.idempotentReplay,
                            )
                        ) {
                            launchSingleTop = true
                        }
                    }
                },
                onAuthExpired = {
                    navController.navigate(
                        CustomerRoute.LOGIN
                    ) {
                        popUpTo(
                            navController
                                .graph
                                .startDestinationId
                        ) {
                            inclusive = true
                        }
                        launchSingleTop = true
                    }
                },
            )
        }

        composable(
            route = CustomerRoute.FOLLOW_UP,
            arguments = listOf(
                navArgument("inquiryId") {
                    type = NavType.StringType
                },
                navArgument("scenario") {
                    type = NavType.StringType
                },
                navArgument("inquiryCode") {
                    type = NavType.StringType
                    defaultValue = ""
                },
                navArgument("idempotentReplay") {
                    type = NavType.BoolType
                    defaultValue = false
                },
            ),
        ) { entry ->
            val inquiryId =
                entry.arguments
                    ?.getString("inquiryId")
                    .orEmpty()

            val scenario =
                runCatching {
                    MockScenario.valueOf(
                        entry.arguments
                            ?.getString("scenario")
                            .orEmpty()
                    )
                }.getOrDefault(
                    MockScenario.NO_EVIDENCE
                )

            val inquiryCode =
                entry.arguments
                    ?.getString("inquiryCode")
                    .orEmpty()

            val idempotentReplay =
                entry.arguments
                    ?.getBoolean("idempotentReplay")
                    ?: false

            FollowUpQuestionsScreen(
                inquiryId = inquiryId,
                onBack = {
                    navController.popBackStack()
                },
                onCancelledStartOver = {
                    subscriptionId ->
                    navController
                        .navigateReplacingCurrentCustomerStep(
                            route =
                                CustomerRoute.intake(
                                    subscriptionId =
                                        subscriptionId,
                                    fixturePreview =
                                        false,
                                ),
                            currentDestinationId =
                                entry.destination.id,
                        )
                },
                onAuthExpired = {
                    navController.navigate(
                        CustomerRoute.LOGIN
                    ) {
                        popUpTo(navController.graph.id) {
                            inclusive = true
                        }
                        launchSingleTop = true
                    }
                },
                onOpenGuidance = { snapshot ->
                    navController
                        .navigateReplacingCurrentCustomerStep(
                            route =
                                CustomerRoute.guidance(
                                    inquiryId = inquiryId,
                                    scenario = scenario.name,
                                    inquiryCode = inquiryCode,
                                    statusCode =
                                        snapshot.statusCode,
                                    stateVersion =
                                        snapshot.stateVersion,
                                    idempotentReplay =
                                        idempotentReplay,
                                    allowedActions =
                                        snapshot.allowedActions,
                                ),
                            currentDestinationId =
                                entry.destination.id,
                        )
                },
            )
        }

        composable(
            route = CustomerRoute.GUIDANCE,
            arguments = listOf(
                navArgument("inquiryId") {
                    type = NavType.StringType
                },
                navArgument("scenario") {
                    type = NavType.StringType
                },
                navArgument("inquiryCode") {
                    type = NavType.StringType
                    defaultValue = ""
                },
                navArgument("statusCode") {
                    type = NavType.StringType
                    defaultValue = ""
                },
                navArgument("stateVersion") {
                    type = NavType.IntType
                    defaultValue = -1
                },
                navArgument("idempotentReplay") {
                    type = NavType.BoolType
                    defaultValue = false
                },
                navArgument("allowedActions") {
                    type = NavType.StringType
                    defaultValue = ""
                },
                navArgument("fixturePreview") {
                    type = NavType.BoolType
                    defaultValue = false
                },
            ),
        ) { entry ->
            val scenario =
                runCatching {
                    MockScenario.valueOf(
                        entry.arguments
                            ?.getString("scenario")
                            .orEmpty()
                    )
                }.getOrDefault(
                    MockScenario.NO_EVIDENCE
                )

            val submittedInquiryCode =
                entry.arguments
                    ?.getString("inquiryCode")
                    .orEmpty()
                    .trim()

            val submittedStatusCode =
                entry.arguments
                    ?.getString("statusCode")
                    .orEmpty()
                    .trim()
                    .takeIf(String::isNotEmpty)

            val submittedStateVersion =
                entry.arguments
                    ?.getInt("stateVersion")
                    ?.takeIf { it >= 0 }

            val submittedAllowedActions =
                entry.arguments
                    ?.getString("allowedActions")
                    .orEmpty()
                    .split(",")
                    .map(String::trim)
                    .filter(String::isNotEmpty)
                    .distinct()
                    .map { code ->
                        AllowedAction(code = code)
                    }

            val submittedIdempotentReplay =
                if (
                    submittedInquiryCode.isNotEmpty()
                ) {
                    entry.arguments
                        ?.getBoolean(
                            "idempotentReplay"
                        )
                        ?: false
                } else {
                    null
                }

            GuidanceScreen(
                inquiryId =
                    entry.arguments
                        ?.getString("inquiryId")
                        .orEmpty(),
                scenario = scenario,
                submittedInquiryCode =
                    submittedInquiryCode,
                submittedStatusCode =
                    submittedStatusCode,
                submittedStateVersion =
                    submittedStateVersion,
                submittedAllowedActions =
                    submittedAllowedActions,
                submittedIdempotentReplay =
                    submittedIdempotentReplay,
                fixturePreview =
                    entry.arguments
                        ?.getBoolean("fixturePreview")
                        ?: false,
                onBack = {
                    navController.popBackStack()
                },
                onAuthExpired = {
                    navController.navigate(
                        CustomerRoute.LOGIN
                    ) {
                        popUpTo(navController.graph.id) {
                            inclusive = true
                        }
                        launchSingleTop = true
                    }
                },
                onDone = {
                    navController.navigate(
                        CustomerRoute.home(false)
                    ) {
                        popUpTo(
                            CustomerRoute.HOME
                        ) {
                            inclusive = false
                        }
                        launchSingleTop = true
                    }
                },
            )
        }
    }
}

internal fun NavController.navigateReplacingCurrentCustomerStep(
    route: String,
    currentDestinationId: Int,
) {
    navigate(route) {
        popUpTo(currentDestinationId) {
            inclusive = true
        }
        launchSingleTop = true
    }
}

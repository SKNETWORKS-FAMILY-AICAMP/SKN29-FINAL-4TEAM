package com.skn29.watercare.customer.navigation

import androidx.activity.compose.setContent
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.lifecycle.Lifecycle
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.pressBack
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

private class BackStackManualScope(
    private val delegate: ComposeTestRule,
    private val scenario: ActivityScenario<ComposeTestActivity>,
) : ComposeTestRule by delegate {
    fun setContent(
        content: @Composable () -> Unit,
    ) {
        if (scenario.state != Lifecycle.State.RESUMED) {
            scenario.moveToState(
                Lifecycle.State.RESUMED
            )
        }

        scenario.onActivity { activity ->
            activity.setContent {
                content()
            }
        }

        delegate.waitForIdle()
    }
}

@RunWith(AndroidJUnit4::class)
@OptIn(ExperimentalTestApi::class)
class CustomerBackStackNavigationTest {
    @get:Rule
    val composeTestRule =
        createEmptyComposeRule()

    private fun runManual(
        block: BackStackManualScope.() -> Unit,
    ) {
        val scenario =
            ActivityScenario.launch(
                ComposeTestActivity::class.java
            )

        try {
            if (
                scenario.state !=
                    Lifecycle.State.RESUMED
            ) {
                scenario.moveToState(
                    Lifecycle.State.RESUMED
                )
            }

            BackStackManualScope(
                delegate = composeTestRule,
                scenario = scenario,
            ).block()
        } finally {
            scenario.close()
        }
    }

    private fun BackStackManualScope.renderGraph(
        onController: (NavHostController) -> Unit,
    ) {
        setContent {
            WaterCareTheme {
                val navController =
                    rememberNavController()

                onController(navController)

                NavHost(
                    navController = navController,
                    startDestination = HOME,
                ) {
                    composable(HOME) {
                        Text("HOME")
                    }

                    composable(INTAKE) {
                        Text("INTAKE")
                    }

                    composable(FOLLOW_UP) {
                        Text("FOLLOW_UP")
                    }

                    composable(GUIDANCE) {
                        Text("GUIDANCE")
                    }
                }
            }
        }
    }

    @Test
    fun completedRemoteIntake_followUpBackReturnsHome() =
        runManual {
            lateinit var navController:
                NavHostController

            renderGraph {
                navController = it
            }

            waitForIdle()

            runOnIdle {
                navController.navigate(INTAKE)
            }

            waitForIdle()

            runOnIdle {
                val currentId =
                    requireNotNull(
                        navController.currentDestination
                    ).id

                navController
                    .navigateReplacingCurrentCustomerStep(
                        route = FOLLOW_UP,
                        currentDestinationId =
                            currentId,
                    )
            }

            waitForIdle()

            runOnIdle {
                assertEquals(
                    FOLLOW_UP,
                    navController
                        .currentDestination
                        ?.route,
                )

                assertTrue(
                    navController.popBackStack()
                )
            }

            waitForIdle()

            runOnIdle {
                assertEquals(
                    HOME,
                    navController
                        .currentDestination
                        ?.route,
                )
            }
        }

    @Test
    fun completedFixtureIntake_systemBackFromGuidanceReturnsHome() =
        runManual {
            lateinit var navController:
                NavHostController

            renderGraph {
                navController = it
            }

            waitForIdle()

            runOnIdle {
                navController.navigate(INTAKE)
            }

            waitForIdle()

            runOnIdle {
                val currentId =
                    requireNotNull(
                        navController.currentDestination
                    ).id

                navController
                    .navigateReplacingCurrentCustomerStep(
                        route = GUIDANCE,
                        currentDestinationId =
                            currentId,
                    )
            }

            waitForIdle()

            runOnIdle {
                assertEquals(
                    GUIDANCE,
                    navController
                        .currentDestination
                        ?.route,
                )
            }

            pressBack()

            waitForIdle()

            runOnIdle {
                assertEquals(
                    HOME,
                    navController
                        .currentDestination
                        ?.route,
                )
            }
        }

    @Test
    fun followUpToGuidance_replacesFollowUpAndBackReturnsHome() =
        runManual {
            lateinit var navController:
                NavHostController

            renderGraph {
                navController = it
            }

            waitForIdle()

            runOnIdle {
                navController.navigate(FOLLOW_UP)
            }

            waitForIdle()

            runOnIdle {
                val currentId =
                    requireNotNull(
                        navController.currentDestination
                    ).id

                navController
                    .navigateReplacingCurrentCustomerStep(
                        route = GUIDANCE,
                        currentDestinationId =
                            currentId,
                    )
            }

            waitForIdle()

            runOnIdle {
                assertEquals(
                    GUIDANCE,
                    navController
                        .currentDestination
                        ?.route,
                )

                assertTrue(
                    navController.popBackStack()
                )
            }

            waitForIdle()

            runOnIdle {
                assertEquals(
                    HOME,
                    navController
                        .currentDestination
                        ?.route,
                )
            }
        }

    companion object {
        private const val HOME = "home"
        private const val INTAKE = "intake"
        private const val FOLLOW_UP = "follow-up"
        private const val GUIDANCE = "guidance"
    }
}
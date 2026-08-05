package com.skn29.watercare.customer.testing

import androidx.activity.ComponentActivity

/**
 * Compose 계측 테스트가 자체 setContent를 호출하기 위한 빈 Activity Host.
 * 실제 애플리케이션 진입점에는 포함되지 않고 debug 변형에서만 사용한다.
 */
class ComposeTestActivity : ComponentActivity()

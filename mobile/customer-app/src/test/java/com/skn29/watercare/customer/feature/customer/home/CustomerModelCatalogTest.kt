package com.skn29.watercare.customer.feature.customer.home

import com.skn29.watercare.customer.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CustomerModelCatalogTest {
    @Test
    fun knownModelCodes_useExactProductImages() {
        val expected = listOf(
            "WPUJAC104DWH" to
                R.drawable.product_wpujac104dwh,
            "WPUIAC425SNW" to
                R.drawable.product_wpuiac425snw,
            "WPUIAC606SNW" to
                R.drawable.product_wpuiac606snw,
        )

        expected.forEach {
                (modelCode, imageRes) ->
            assertEquals(
                imageRes,
                customerModelVisualSpec(
                    modelCode
                ).productImageRes,
            )
        }
    }

    @Test
    fun unknownModel_doesNotUseAnotherProductImage() {
        val unknown =
            customerModelVisualSpec(
                modelCode =
                    "UNKNOWN-MODEL",
                fallbackModelName =
                    "알 수 없는 모델",
            )

        assertNull(
            unknown.productImageRes
        )
    }
}

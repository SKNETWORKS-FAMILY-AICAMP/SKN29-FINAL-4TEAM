package com.skn29.watercare.customer.feature.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp

private val AuthFormShape =
    RoundedCornerShape(22.dp)

private val AuthFieldShape =
    RoundedCornerShape(14.dp)

@Composable
internal fun Modifier.p1AuthFormContainer(): Modifier {
    val scheme =
        MaterialTheme.colorScheme

    return this
        .fillMaxWidth()

        .clip(AuthFormShape)
        .background(
            scheme.primaryContainer.copy(
                alpha = 0.13f,
            )
        )
        .border(
            width = 1.dp,
            color =
                scheme.primary.copy(
                    alpha = 0.18f,
                ),
            shape = AuthFormShape,
        )
        .padding(
            horizontal = 16.dp,
            vertical = 16.dp,
        )
}

@Composable
internal fun P1AuthField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    singleLine: Boolean = false,
    label: @Composable (() -> Unit)? = null,
    placeholder: @Composable (() -> Unit)? = null,
    supportingText: @Composable (() -> Unit)? = null,
    isError: Boolean = false,
    visualTransformation: VisualTransformation =
        VisualTransformation.None,
    keyboardOptions: KeyboardOptions =
        KeyboardOptions.Default,
) {
    val scheme =
        MaterialTheme.colorScheme

    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier =
            modifier
                .fillMaxWidth()
                .heightIn(
                    min = 60.dp,
                ),
        enabled = enabled,
        singleLine = singleLine,
        label = label,
        placeholder = placeholder,
        supportingText = supportingText,
        isError = isError,
        visualTransformation =
            visualTransformation,
        keyboardOptions =
            keyboardOptions,
        textStyle =
            MaterialTheme.typography.bodyLarge,
        shape = AuthFieldShape,
        colors =
            OutlinedTextFieldDefaults.colors(
                focusedContainerColor =
                    scheme.surface,
                unfocusedContainerColor =
                    scheme.surfaceVariant.copy(
                        alpha = 0.18f,
                    ),
                disabledContainerColor =
                    scheme.surfaceVariant.copy(
                        alpha = 0.34f,
                    ),
                errorContainerColor =
                    scheme.errorContainer.copy(
                        alpha = 0.16f,
                    ),

                focusedBorderColor =
                    scheme.primary,

                unfocusedBorderColor =
                    scheme.primary.copy(
                        alpha = 0.24f,
                    ),

                errorBorderColor =
                    scheme.error,

                cursorColor =
                    scheme.primary,

                focusedLabelColor =
                    scheme.primary,

                unfocusedLabelColor =
                    scheme.onSurfaceVariant,

                focusedPlaceholderColor =
                    scheme.onSurfaceVariant.copy(
                        alpha = 0.62f,
                    ),

                unfocusedPlaceholderColor =
                    scheme.onSurfaceVariant.copy(
                        alpha = 0.54f,
                    ),

                focusedSupportingTextColor =
                    scheme.onSurfaceVariant.copy(
                        alpha = 0.80f,
                    ),

                unfocusedSupportingTextColor =
                    scheme.onSurfaceVariant.copy(
                        alpha = 0.72f,
                    ),
            ),
    )
}

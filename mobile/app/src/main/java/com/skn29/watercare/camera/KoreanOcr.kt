package com.skn29.watercare.camera

import android.content.Context
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions

object KoreanOcr {
    fun recognize(
        context: Context,
        uri: Uri,
        onSuccess: (String) -> Unit,
        onError: (Throwable) -> Unit
    ) {
        runCatching { InputImage.fromFilePath(context, uri) }
            .onFailure(onError)
            .onSuccess { image ->
                val recognizer = TextRecognition.getClient(
                    KoreanTextRecognizerOptions.Builder().build()
                )

                recognizer.process(image)
                    .addOnSuccessListener { result ->
                        onSuccess(result.text.trim())
                    }
                    .addOnFailureListener(onError)
                    .addOnCompleteListener {
                        recognizer.close()
                    }
            }
    }
}

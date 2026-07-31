package com.skn29.watercare.customer.common

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

class VmFactory<T : ViewModel>(private val initializer: () -> T) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <VM : ViewModel> create(modelClass: Class<VM>): VM = initializer() as VM
}

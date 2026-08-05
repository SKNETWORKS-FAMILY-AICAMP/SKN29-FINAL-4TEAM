package com.skn29.watercare.customer.common

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.CreationExtras

class VmFactory<T : ViewModel>(
    private val initializer: (CreationExtras) -> T,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <VM : ViewModel> create(
        modelClass: Class<VM>,
        extras: CreationExtras,
    ): VM = initializer(extras) as VM

    @Suppress("UNCHECKED_CAST")
    override fun <VM : ViewModel> create(modelClass: Class<VM>): VM =
        initializer(CreationExtras.Empty) as VM
}
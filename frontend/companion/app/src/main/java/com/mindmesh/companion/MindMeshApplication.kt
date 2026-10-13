package com.mindmesh.companion

import android.app.Application
import androidx.work.Configuration

class MindMeshApplication : Application(), Configuration.Provider {
    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder().setMinimumLoggingLevel(android.util.Log.INFO).build()
}

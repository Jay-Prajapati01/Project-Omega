package com.mindmesh.companion.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.flow.Flow

@Dao
interface QuickSaveDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(item: QuickSave): Long

    @Query("SELECT * FROM quick_saves WHERE ownerId = :ownerId ORDER BY createdAt DESC")
    fun observe(ownerId: String): Flow<List<QuickSave>>

    @Query("SELECT * FROM quick_saves WHERE state IN (:states) ORDER BY createdAt ASC")
    suspend fun byStates(states: List<String>): List<QuickSave>

    @Query("UPDATE quick_saves SET state = :state, message = :message, updatedAt = :now WHERE id = :id")
    suspend fun setState(id: String, state: String, message: String, now: Long = System.currentTimeMillis())

    @Query("UPDATE quick_saves SET state = :state, message = :message, jobId = :jobId, updatedAt = :now WHERE id = :id")
    suspend fun setAccepted(id: String, state: String, message: String, jobId: String?, now: Long = System.currentTimeMillis())

    @Query("UPDATE quick_saves SET attempts = attempts + 1, updatedAt = :now WHERE id = :id")
    suspend fun bumpAttempts(id: String, now: Long = System.currentTimeMillis())

    @Query("UPDATE quick_saves SET state = 'queued', message = 'Ready to sync — your session is valid again.' WHERE state = 'auth_error'")
    suspend fun requeueAuthErrors()

    @Query("SELECT COUNT(*) FROM quick_saves WHERE ownerId = :ownerId AND state IN (:states)")
    suspend fun count(ownerId: String, states: List<String>): Int
}

@Database(entities = [QuickSave::class], version = 2, exportSchema = false)
abstract class MindMeshDatabase : RoomDatabase() {
    abstract fun quickSaves(): QuickSaveDao

    companion object {
        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE quick_saves ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE quick_saves ADD COLUMN updatedAt INTEGER NOT NULL DEFAULT 0")
            }
        }

        @Volatile
        private var instance: MindMeshDatabase? = null

        fun create(context: Context): MindMeshDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                MindMeshDatabase::class.java,
                "mindmesh.db",
            ).addMigrations(MIGRATION_1_2).build().also { instance = it }
        }
    }
}

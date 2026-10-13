# Android companion

The full native app source is in `frontend/companion/`: Compose UI, Supabase sign-in, local Room save queue, WorkManager sync, backend status, retries, and share-sheet handling are retained. The clone has its own Android application ID (`com.mindmesh.clone.companion`) and callback scheme (`mindmeshclone://auth/callback`) so it can be installed beside the source app.

The share parser accepts YouTube (`youtube.com`, its subdomains, `youtu.be`) and Instagram (`instagram.com` and subdomains) only. Unsupported hosts are rejected before queuing. The backend repeats this validation in `/api/mobile/quick-saves`, so a modified client cannot enqueue arbitrary websites. The companion's upload surface is link-only: document and audio pickers and their API calls were removed.

Share a link from YouTube or Instagram to MindMesh, or paste a supported link into the app. A signed-in user's queued save receives a durable local receipt, syncs with an idempotency key, and polls the backend for processing status. Copy `companion.properties.example` into an untracked `local.properties` file and configure the API and Supabase values before building.

## Companion API

The companion talks to the same FastAPI service as the website. Its production configuration uses the `/api/` base URL; the current phone build points to `http://127.0.0.1:8000/api/` and uses `adb reverse tcp:8000 tcp:8000` over USB. To open the development website in the phone browser at `http://localhost:3000`, also run `adb reverse tcp:3000 tcp:3000`; otherwise `localhost` points to the phone and the browser reports connection refused.

| Method and route | Purpose |
| --- | --- |
| `GET /health` | Public backend reachability check used by the app's connection indicator. |
| `POST /api/mobile/quick-saves` | Accepts `{"url":"https://…"}` for YouTube or Instagram links. Requires the signed-in user's bearer token and an `Idempotency-Key`; returns HTTP 202 with `item_id`, `job_id`, and status. |
| `GET /api/mobile/quick-saves/{job_id}` | Reads queued, processing, completed, or failed status for a previously accepted save. |
| `GET /api/v1/me/entitlements` | Loads the current account's plan and usage limits. |

The app stores the receipt locally before syncing, retries transient connection and server failures through WorkManager, and polls processing status. A completed HTTP 202 means the backend accepted the job, not that extraction and indexing finished. A missing/expired session needs a fresh sign-in; inaccessible or private social posts can still fail at the provider extraction stage.

The debug APK is generated at `app/build/outputs/apk/debug/app-debug.apk` after `./gradlew assembleDebug` (Windows: `gradlew.bat assembleDebug`). The application ID is `com.mindmesh.clone.companion`.

# Manual setup checklist

This guide explains the one-time settings needed after cloning. The local clone already has copies of the source project's Supabase settings in ignored local files. Those files contain credentials and are excluded from Git. The clone's website and phone app point to the clone's local backend.

## 1. Start local services

The backend is configured for local development and uses:

- FastAPI at `http://localhost:8000`
- Qdrant's embedded local mode, persisted under `backend/data/qdrant`
- Ollama at `http://localhost:11434`

Start Ollama before processing content. The copied Ollama configuration uses `qwen2.5:3b` for chat and `nomic-embed-text` for embeddings; both are already installed on this computer. Qdrant is embedded in the backend process for this local clone, so no Docker/Qdrant service is needed. YouTube transcription fallback also needs `ffmpeg`; Instagram extraction needs Playwright's browser and Tesseract OCR. Check [Pipelines and tools](pipelines-and-tools.md) for the feature-level dependencies.

From the clone root, use separate terminals:

```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```powershell
cd frontend
npm ci
npm run dev
```

Check `http://localhost:8000/health` and `http://localhost:3000`. The backend creates its local vector collection on first startup.

## 2. Allow the clone website in Supabase Auth

The clone reuses the source project's Supabase Auth project and its configured Google provider. Supabase must allow the clone's local browser callback URLs:

1. Open the Supabase project used by the source app.
2. Go to **Authentication → URL Configuration**.
3. Add `http://localhost:3000/**` and `http://127.0.0.1:3000/**` under **Redirect URLs** and save.
4. Go to **Authentication → Sign In / Providers → Google** and confirm Google is enabled. Keep the existing Google client ID and secret if they are already configured.
5. In Google Cloud Console, confirm the OAuth web client has Supabase's callback URL listed as an authorized redirect URI. Supabase displays the exact callback URL in its Google provider settings; it is usually `https://<project-ref>.supabase.co/auth/v1/callback`.

Email/password sign-in uses the copied Supabase project credentials. Google sign-in works only when the provider is enabled and the redirect URLs above are allowlisted. Do not paste a Google client secret into frontend settings.

## 3. Allow the companion's separate callback

The clone companion uses `mindmeshclone://auth/callback`, distinct from the source app's callback. In **Authentication → URL Configuration**, add that exact URI to **Redirect URLs**. The existing Google provider can then return to the clone app. Email confirmation links also use this URI.

## 4. Connect and install on a physical Android phone

1. Enable **Developer options** and **USB debugging** on the phone.
   On Xiaomi/MIUI, also enable the **Install via USB** developer option if present, and any **USB debugging (Security settings)** toggle the phone requires for app installs.
2. Connect it with a data-capable USB cable, unlock the phone, and accept the **Allow USB debugging** prompt.
3. In PowerShell, run `adb devices -l`. The phone should show `device`, not `unauthorized` or `offline`.
4. From `frontend/companion`, run:

   ```powershell
   .\gradlew.bat testDebugUnitTest assembleDebug
   adb reverse tcp:8000 tcp:8000
   adb reverse tcp:3000 tcp:3000
   adb install -r app\build\outputs\apk\debug\app-debug.apk
   adb shell monkey -p com.mindmesh.clone.companion -c android.intent.category.LAUNCHER 1
   ```

On Xiaomi/MIUI phones, keep the phone unlocked during `adb install`. If the phone shows a USB installation confirmation, tap **Install/Allow** and approve any follow-up security prompt. If ADB reports `Install canceled by user`, the APK build is fine; repeat `adb install -r app\build\outputs\apk\debug\app-debug.apk` after approving the phone prompt. The companion is installed only after `adb shell pm path com.mindmesh.clone.companion` prints an APK path.

The reverse mapping on port 8000 lets the companion reach the computer's backend at `127.0.0.1:8000`. The port 3000 mapping lets the phone browser open `http://localhost:3000` on the computer. Re-run both `adb reverse` commands after reconnecting or rebooting the phone. The clone is installed separately from the original companion.

## 5. If a save stays queued or fails

- Confirm `/health` works from the computer and the companion's backend indicator is online.
- Confirm USB reverse is active with `adb reverse --list`.
- Confirm installation completed with `adb shell pm path com.mindmesh.clone.companion`; if empty, approve MIUI's on-device USB install prompt and reinstall.
- Keep the backend terminal open and inspect its error for the job ID shown in the app.
- A YouTube URL needs an accessible transcript, or working `yt-dlp`, `ffmpeg`, and Whisper fallback.
- An Instagram post must be public and accessible to the configured extraction path. Private or rate-limited posts can fail.
- Confirm Ollama is reachable at port 11434. A successful save receipt only means the job was accepted; it does not mean extraction and indexing completed.

## 6. Keep the clone's data safe

The local `.env` files reuse the source project's Supabase project, so the same Supabase users and tenant memberships are in effect. The clone's local vectors/files use its own `backend/data` directory and local Qdrant service. To make a fully isolated clone, create a separate Supabase project, apply `backend/migrations/`, configure the Google provider there, and replace the Supabase values in `backend/.env`, `frontend/.env.local`, and `frontend/companion/local.properties`.

Never commit `backend/.env`, `frontend/.env.local`, or `frontend/companion/local.properties`. They contain credentials. The repository `.gitignore` excludes them.

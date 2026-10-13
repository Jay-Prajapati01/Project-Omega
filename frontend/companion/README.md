# MindMesh native Android companion

This is a standalone Kotlin + Jetpack Compose Android Studio project. It receives Android `ACTION_SEND` text URLs, stores pending saves in Room, uses WorkManager for network retry, and posts authenticated quick-save receipts through Retrofit/OkHttp.

## Screens and flow

Welcome → Sign in / Create account / Confirm email → Home. The home screen is the share target: a shared link lands in the draft field and the user taps **Save to MindMesh** (nothing uploads automatically). Every save row shows its real state — On device, Sending, Accepted, Processing, Synced, Failed, Backend offline or Needs sign-in — driven only by what the worker recorded in Room, plus a backend health chip backed by the public `GET /api/health`.

Sharing while signed out keeps the link and offers it back after sign-in.

## Build

```powershell
.\gradlew.bat assembleDebug       # app/build/outputs/apk/debug/app-debug.apk
```

For a USB-connected physical phone, use the development update command instead.
It recreates the port tunnel, installs the debug build over the existing app,
and opens it on the phone:

```powershell
.\scripts\install-usb-debug.ps1
```

## Backend requirement

The API answers `503 AUTH_CONFIGURATION_REQUIRED` to companion requests unless the backend runs with `AUTH_ENABLED=true`. That value is set in `backend/.env` (and by `docker-compose.yml`); see `backend/.env.example`. Start it with:

```powershell
cd ..\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Configuration

Create an untracked `local.properties` with `MINDMESH_API_BASE_URL`, `SUPABASE_URL`, and `SUPABASE_PUBLISHABLE_KEY`, then open this directory in Android Studio. Add `mindmeshclone://auth/callback` in Supabase Auth redirect settings before testing authentication. For a physical phone connected over USB, set the API URL to `http://127.0.0.1:8000/api/` and use `scripts/install-usb-debug.ps1`; it creates the required ADB port forwarding. For an Android Emulator, use `http://10.0.2.2:8000/api/` instead. This clone installs as `com.mindmesh.clone.companion`, separately from the source app.

Version 2.0.1 uses Android Emulator host routing by default, and also displays the signed-in account's plan, remaining selected
limits, and whether a shared save uses a connected BYOK provider or MindMesh
managed resources. The theme choice is stored on the device.

Full docs: [`../../docs/companion.md`](../../docs/companion.md) and
[`../../docs/manual-setup.md`](../../docs/manual-setup.md). For product
pipelines, status meanings, and known troubleshooting history, see
[`../../docs/pipelines-and-tools.md`](../../docs/pipelines-and-tools.md)
and [`../../docs/known-issues-and-fixes.md`](../../docs/known-issues-and-fixes.md).

The web analytics consent is browser-based. Companion interactions are not
currently included in the admin analytics totals; the app does not silently
send a second analytics stream. If companion analytics are added later, add an
explicit in-app consent control and disclose the collection in the privacy
notice first.

# Embettered Voice (Expo)

Records audio on your phone and uploads it to the laptop FastAPI `POST /voice` endpoint (same Wi‑Fi). See [../client/CLIENT_README.md](../client/CLIENT_README.md) for server setup.

## Setup

```bash
cd mobile
npm install
npx expo install expo-av expo-status-bar
npx expo start
```

Edit the default base URL in `App.tsx` (`DEFAULT_BASE`) or in the app UI to match your laptop’s LAN IP (e.g. `http://192.168.1.42:8000`).

### iOS simulator / device

Use a physical device or simulator on the same network as the laptop. For simulator, `localhost` may point at the simulator, not the Mac; use the Mac’s LAN IP instead.

### Android

`usesCleartextTraffic` is enabled in `app.json` so `http://` to your laptop works. Some OEMs still block LAN access; disable data saver if uploads fail.

## ElevenLabs TTS (optional)

After a successful `/voice` response, the JSON includes `tts_text`—a short string suitable for read-aloud. You can:

1. Call [ElevenLabs API](https://elevenlabs.io/docs) from a **small backend** you trust with the API key (recommended), then return an audio URL or bytes to the app; or
2. Use their client SDK only if you accept shipping a restricted key in the app (not recommended for production).

Play MP3 in the app with `expo-av` `Audio.Sound.createAsync({ uri })`.

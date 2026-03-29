import { useState, useRef } from "react";
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  Pressable,
  ScrollView,
  ActivityIndicator,
  Alert,
  Platform,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { Audio } from "expo-av";

/** Laptop FastAPI base URL (same Wi‑Fi). No trailing slash. */
const DEFAULT_BASE = "http://192.168.1.1:8000";

export default function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState("");
  const recordingRef = useRef<Audio.Recording | null>(null);

  const appendLog = (line: string) =>
    setLog((prev) => (prev ? `${prev}\n${line}` : line));

  async function startRecording() {
    const perm = await Audio.requestPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permission needed", "Microphone access is required.");
      return;
    }
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
    });
    const rec = new Audio.Recording();
    await rec.prepareToRecordAsync(
      Audio.RecordingOptionsPresets.HIGH_QUALITY
    );
    await rec.startAsync();
    recordingRef.current = rec;
    appendLog("Recording… tap Stop & send when done.");
  }

  async function stopAndUpload() {
    const rec = recordingRef.current;
    if (!rec) {
      Alert.alert("Not recording", "Tap Record first.");
      return;
    }
    setBusy(true);
    try {
      await rec.stopAndUnloadAsync();
      recordingRef.current = null;
      const uri = rec.getURI();
      if (!uri) {
        throw new Error("No recording URI");
      }

      const form = new FormData();
      const ext = uri.split(".").pop() || "m4a";
      const mime =
        ext === "wav"
          ? "audio/wav"
          : ext === "webm"
            ? "audio/webm"
            : "audio/m4a";
      form.append("file", {
        uri,
        name: `recording.${ext}`,
        type: mime,
      } as unknown as Blob);

      const url = `${baseUrl.replace(/\/$/, "")}/voice`;
      const res = await fetch(url, {
        method: "POST",
        body: form,
      });
      const text = await res.text();
      let body: Record<string, unknown>;
      try {
        body = JSON.parse(text) as Record<string, unknown>;
      } catch {
        body = { raw: text };
      }
      if (!res.ok) {
        appendLog(`HTTP ${res.status}: ${text}`);
        Alert.alert("Server error", text.slice(0, 400));
        return;
      }
      appendLog(JSON.stringify(body, null, 2));
      const tts = typeof body.tts_text === "string" ? body.tts_text : "";
      if (tts) {
        appendLog(
          "\n— Use `tts_text` with ElevenLabs (see mobile/README.md) —"
        );
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      appendLog(`Error: ${msg}`);
      Alert.alert("Upload failed", msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.container}>
      <StatusBar style="auto" />
      <Text style={styles.title}>Embettered Voice</Text>
      <Text style={styles.hint}>
        Set your laptop&apos;s LAN URL (FastAPI on port 8000). Same Wi‑Fi only.
      </Text>
      <TextInput
        style={styles.input}
        value={baseUrl}
        onChangeText={setBaseUrl}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        placeholder={DEFAULT_BASE}
      />
      <View style={styles.row}>
        <Pressable
          style={[styles.btn, busy && styles.btnDisabled]}
          onPress={startRecording}
          disabled={busy}
        >
          <Text style={styles.btnText}>Record</Text>
        </Pressable>
        <Pressable
          style={[styles.btn, styles.btnPrimary, busy && styles.btnDisabled]}
          onPress={stopAndUpload}
          disabled={busy}
        >
          {busy ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={[styles.btnText, styles.btnTextLight]}>
              Stop &amp; send
            </Text>
          )}
        </Pressable>
      </View>
      <ScrollView style={styles.logBox}>
        <Text style={styles.logText}>{log || "Response will appear here."}</Text>
      </ScrollView>
      <Text style={styles.footer}>
        ElevenLabs: send `tts_text` from the response to their TTS API (see
        mobile/README.md); play returned audio with expo-av Sound if needed.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 56,
    paddingHorizontal: 20,
    backgroundColor: "#0f1419",
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
    color: "#e6edf3",
    marginBottom: 8,
  },
  hint: {
    fontSize: 14,
    color: "#8b949e",
    marginBottom: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: "#30363d",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: "#e6edf3",
    backgroundColor: "#161b22",
    marginBottom: 16,
  },
  row: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 16,
  },
  btn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 8,
    backgroundColor: "#21262d",
    alignItems: "center",
    justifyContent: "center",
  },
  btnPrimary: {
    backgroundColor: "#238636",
  },
  btnDisabled: {
    opacity: 0.6,
  },
  btnText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#e6edf3",
  },
  btnTextLight: {
    color: "#fff",
  },
  logBox: {
    flex: 1,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#30363d",
    padding: 12,
    backgroundColor: "#161b22",
    marginBottom: 12,
  },
  logText: {
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
    fontSize: 12,
    color: "#7ee787",
  },
  footer: {
    fontSize: 11,
    color: "#6e7681",
    marginBottom: 24,
  },
});

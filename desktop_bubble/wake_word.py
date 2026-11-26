"""
J.A.R.V.I.S. Background Wake-Word Detection Engine (PySide6 + sounddevice + openwakeword)
==========================================================================================
Low-CPU background wake-word detector running in a dedicated QThread.

Features:
- Continuously listens for 'Hey Jarvis' even when the desktop bubble is collapsed.
- Streams live mic RMS amplitude (0.0 to 1.0) to orb.set_audio_level() so the orb pulses with speech.
- Dynamically binds to the exact microphone selected in the web app Settings via QWebChannel.
- Auto-debounces triggers and emits `wake_detected('hey_jarvis')` to expand the popup and capture input.
"""

import sys
import time
import math
import numpy as np
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Slot


def resolve_input_device(label_substring: str = None) -> int:
    """
    Finds a sounddevice input device index by matching against the browser microphone label.
    Falls back cleanly to system default input device if no match is found.
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        try:
            default_in = int(sd.default.device[0])
        except Exception:
            default_in = 0

        if not label_substring or label_substring.strip() == "":
            return default_in if default_in is not None and default_in >= 0 else 0

        target = label_substring.strip().lower()
        # 1. Exact or substring match in device name
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                dname = dev.get("name", "").lower()
                # Check for label inside device name or device name inside label
                if target in dname or dname in target:
                    return idx

        # 2. Tokenized match (e.g. "Realtek", "Microphone", "Headset", "USB")
        tokens = [t for t in target.replace("(", " ").replace(")", " ").split() if len(t) > 3]
        for token in tokens:
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    dname = dev.get("name", "").lower()
                    if token in dname:
                        return idx

        return default_in if default_in is not None and default_in >= 0 else 0
    except Exception as e:
        print(f"[WakeWord] Device resolution notice: {e}")
        return 0


class WakeWordWorker(QThread):
    """
    Background QThread running continuous low-CPU wake-word detection using openWakeWord & sounddevice.
    """
    audio_level = Signal(float)       # Emits live 0.0 - 1.0 RMS amplitude for orb pulsing
    wake_detected = Signal(str)       # Emits 'hey_jarvis' when wake phrase is recognized
    status_changed = Signal(str)      # Emits hardware and model status updates
    error_occurred = Signal(str)      # Emits non-fatal audio warnings

    def __init__(self, mic_label: str = "", threshold: float = 0.5):
        super().__init__()
        self.mic_label = mic_label
        self.threshold = threshold
        self._running = False
        self._pending_mic_label = None
        self._last_trigger_time = 0.0
        self._current_device_idx = None
        self._model = None

    @Slot(str, str)
    def set_microphone(self, label: str, device_id: str = ""):
        """Called via QWebChannel whenever user switches microphone in web app Settings."""
        self._pending_mic_label = label or ""
        print(f"[WakeWord] Target microphone updated from web app: '{label}' (ID: {device_id[:12]}...)")

    def stop(self):
        """Stops the audio loop and shuts down thread cleanly."""
        self._running = False
        self.wait(2000)

    def trigger_wake_word(self, phrase: str = "hey_jarvis"):
        """Programmatically triggers the wake word signal (useful for testing & keyboard triggers)."""
        print(f"[WakeWord] Manual/Simulated wake word trigger: '{phrase}'")
        self.wake_detected.emit(phrase)

    def _init_model(self):
        """Initializes openWakeWord 'hey_jarvis' model if available."""
        try:
            import openwakeword
            from openwakeword.model import Model

            # Attempt to download default models if not found locally
            try:
                import openwakeword.utils
                openwakeword.utils.download_models(["hey_jarvis"])
            except Exception as dl_err:
                pass

            self._model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            self.status_changed.emit("Wake-Word Model Active: 'Hey Jarvis'")
            print("[WakeWord] openWakeWord 'hey_jarvis' model loaded successfully.")
        except Exception as e:
            print(f"[WakeWord] openWakeWord model initialization: {e}")
            self._model = None

    def run(self):
        self._running = True
        self._init_model()

        try:
            import sounddevice as sd
        except ImportError:
            self.error_occurred.emit("sounddevice library not installed. Audio listening disabled.")
            return

        samplerate = 16000
        blocksize = 1280  # 80ms chunks (1280 samples @ 16kHz)

        self._current_device_idx = resolve_input_device(self.mic_label)

        def audio_callback(indata, frames, time_info, status):
            if not self._running:
                return

            try:
                # 1. Compute RMS amplitude for live visual pulsing on orb
                samples = indata[:, 0].astype(np.float32)
                rms = float(np.sqrt(np.mean(samples**2)))
                # Normalize typical speech to 0.0 - 1.0 (ambient noise ~100-300, speech ~2000-12000)
                norm_level = min(1.0, max(0.0, (rms - 120.0) / 9000.0))
                self.audio_level.emit(norm_level)

                # 2. Feed 80ms chunk into openWakeWord model
                if self._model is not None:
                    # openWakeWord expects 16-bit PCM numpy array
                    int16_samples = indata[:, 0]
                    prediction = self._model.predict(int16_samples)

                    # Extract wake word score for "hey_jarvis"
                    highest_score = 0.0
                    for k, v in prediction.items():
                        if "jarvis" in k.lower():
                            highest_score = max(highest_score, float(v))

                    if highest_score >= self.threshold:
                        now = time.time()
                        # 2.5s debounce to avoid repeat triggers for same phrase
                        if now - self._last_trigger_time > 2.5:
                            self._last_trigger_time = now
                            print(f"[WakeWord] TRIGGER DETECTED! 'Hey Jarvis' (Score: {highest_score:.2f})")
                            self.wake_detected.emit("hey_jarvis")
            except Exception as cb_err:
                pass

        stream = None
        try:
            stream = sd.InputStream(
                samplerate=samplerate,
                channels=1,
                dtype='int16',
                blocksize=blocksize,
                device=self._current_device_idx,
                callback=audio_callback
            )
            stream.start()
            self.status_changed.emit(f"Listening on device index {self._current_device_idx}")
            print(f"[WakeWord] Sounddevice stream started on input device {self._current_device_idx}.")

            while self._running:
                # Check for dynamic microphone device change requested from Settings
                if self._pending_mic_label is not None:
                    new_label = self._pending_mic_label
                    self._pending_mic_label = None
                    new_idx = resolve_input_device(new_label)

                    if new_idx != self._current_device_idx:
                        print(f"[WakeWord] Switching audio device from {self._current_device_idx} to {new_idx} ('{new_label}')...")
                        try:
                            stream.stop()
                            stream.close()
                        except Exception:
                            pass

                        self._current_device_idx = new_idx
                        stream = sd.InputStream(
                            samplerate=samplerate,
                            channels=1,
                            dtype='int16',
                            blocksize=blocksize,
                            device=self._current_device_idx,
                            callback=audio_callback
                        )
                        stream.start()
                        self.status_changed.emit(f"Switched microphone to '{new_label}' (Index {new_idx})")

                self.msleep(50)
        except Exception as ex:
            print(f"[WakeWord] Stream error: {ex}")
            self.error_occurred.emit(f"Audio stream error: {ex}")
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            print("[WakeWord] Thread exited cleanly.")

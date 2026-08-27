"""
voice.py
---------
Local, fully offline voice interface for Remy, using push-to-talk.

- listen()  : hold a key down to record from the microphone, release to
              stop. Transcribes locally with Whisper (via faster-whisper,
              GPU-accelerated), returns plain text.
- speak()   : takes Remy's reply text, strips out *action* motions (those
              are cosmetic personality flavor, not meant to be spoken),
              and speaks the rest aloud via pyttsx3 (fully offline).

Uses sounddevice instead of pyaudio - pyaudio needs to be compiled from
source on Windows and frequently fails to build; sounddevice ships
working prebuilt wheels and is simpler to work with for push-to-talk
style recording (start/stop on demand, rather than silence detection).

This file only handles audio in/out - it doesn't know about the LLM,
memory, or conversation history. remy_comm.py's run_voice() glues this
to RemyComm.handle_input(), the same way run_terminal() does with typed
input.
"""

import re
import time
import numpy as np
import sounddevice as sd
import keyboard
import pyttsx3
from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000

# The key you hold down to talk. See keyboard's docs for valid names -
# common options: "space", "caps lock", "f13" (if you have a spare key
# you never use for anything else, that's often the least annoying
# choice since it won't collide with normal typing). Avoided "right ctrl"
# as the default - the keyboard library's handling of modifier keys can
# be unreliable (missed press/release events); "space" is more consistent.
PUSH_TO_TALK_KEY = "space"


# ---------------------------------------------------------------------------
# TEXT-TO-SPEECH
# ---------------------------------------------------------------------------

# NOTE: pyttsx3 has a well-known bug on Windows where reusing the same
# engine instance across multiple say()+runAndWait() calls stops working
# after the first call (the SAPI5 driver's internal loop gets stuck). The
# reliable fix is to create a fresh engine instance every time speak() is
# called, rather than keeping one global instance - slightly less
# efficient, but actually works every time.

# Regex matches *anything wrapped in single asterisks* - Remy's cosmetic
# action motions (e.g. "*hands up*", "*makes checkmark motion in air*").
# These get stripped before speaking, but should still be PRINTED to the
# terminal/log elsewhere so you don't lose that personality flavor entirely.
_ACTION_PATTERN = re.compile(r"\*[^*]+\*")


def strip_actions(text):
    """
    Removes *action* motion markers from text, leaving only what should
    actually be spoken aloud. Also collapses any resulting double spaces
    left behind by the removal.
    """
    without_actions = _ACTION_PATTERN.sub("", text)
    return re.sub(r"\s{2,}", " ", without_actions).strip()


def speak(text):
    """
    Speaks the given text aloud, after stripping *action* markers.
    Blocking call - waits until speech finishes before returning.
    Creates a new pyttsx3 engine instance each call (see note above).

    NOTE: pyttsx3 has no device-selection option - it always plays through
    whatever Windows currently has set as the DEFAULT playback device. To
    hear Remy through your headset specifically, set the headset as your
    Windows default output (Settings > Sound) before running this.
    """
    spoken_text = strip_actions(text)
    if not spoken_text:
        return  # nothing left to say after stripping (e.g. pure-action reply)

    engine = pyttsx3.init()
    engine.say(spoken_text)
    engine.runAndWait()
    engine.stop()


# ---------------------------------------------------------------------------
# SPEECH-TO-TEXT (push-to-talk)
# ---------------------------------------------------------------------------

# "base" is a good starting size for a 6GB card - fast, decent accuracy.
# Options (smallest/fastest to largest/most accurate): tiny, base, small,
# medium, large-v3. Bump up if accuracy isn't good enough; drop down if
# it's too slow.

def _load_whisper_model():
    """
    Tries GPU (CUDA) first, since it's much faster. faster-whisper loads
    CUDA libraries lazily (only on the first actual transcription), so we
    run one silent dummy transcription right here to force that to happen
    now, at startup - if the required NVIDIA libraries (e.g. cublas) are
    missing, we catch it here and fall back to CPU cleanly, instead of
    crashing mid-conversation later.

    To get real GPU speed working properly, install the missing CUDA
    libraries with: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
    """
    try:
        model = WhisperModel("base", device="cuda", compute_type="float16")
        dummy_audio = np.zeros(SAMPLE_RATE, dtype="float32")
        list(model.transcribe(dummy_audio)[0])  # forces CUDA lib load now
        print("Whisper: running on GPU (CUDA).")
        return model
    except Exception as e:
        print(f"Whisper: GPU unavailable ({e}) - falling back to CPU.")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print("Whisper: running on CPU.")
        return model


_whisper_model = _load_whisper_model()


def list_microphones():
    """
    Returns a list of (index, name) for every INPUT-capable device Windows
    sees - this will include both your headset mic and laptop mic, so you
    can tell them apart and pick the right one.
    """
    devices = sd.query_devices()
    return [(i, d["name"]) for i, d in enumerate(devices) if d["max_input_channels"] > 0]


def choose_microphone():
    """
    Prints all available microphones and lets the user pick one by index.
    Returns the chosen device index, to be passed into listen().
    """
    devices = list_microphones()
    print("Available microphones:")
    for index, name in devices:
        print(f"  {index}: {name}")

    valid_indices = [i for i, _ in devices]
    while True:
        choice = input("Select microphone index: ").strip()
        if choice.isdigit() and int(choice) in valid_indices:
            return int(choice)
        print("Invalid choice, try again.")


def listen(device_index=None, key=PUSH_TO_TALK_KEY):
    """
    Push-to-talk: hold `key` down to record, release to stop. Records from
    the given input device (or system default if device_index is None),
    transcribes locally via Whisper, and returns the resulting text.
    """
    frames = []

    def _callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    print(f"Hold [{key}] to talk...")
    keyboard.wait(key)  # blocks here until the key is pressed down

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device_index,
        callback=_callback,
    )
    stream.start()

    while keyboard.is_pressed(key):
        time.sleep(0.01)  # keep checking until the key is released

    stream.stop()
    stream.close()

    if not frames:
        return ""

    audio_array = np.concatenate(frames, axis=0).flatten()
    segments, _ = _whisper_model.transcribe(audio_array, language="en")
    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip()

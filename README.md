# Remy-Assistant-
A simple companion to help you manage your tasks, ideas and help you do what you want to do by automating the simple things, like moving tools to where you need them or just finding them wherever you last left them.

# File-system:
Remy:

1. remy_comm.py :
central hub —
conversation history, builds system prompt each turn from memory.py, sends via llm_interaction.py, logs each turn, entry point for terminal (and future GUI/voice/robot interfaces)


2. llm_interaction.py:
provider layer — 
PROVIDERS dict (Gemini via native google-genai SDK, Ollama via OpenAI-compatible endpoint), provider selection menu, connection check, send_message()

2. memory.py:
sole gatekeeper to all three databases below —
remy_comm.py never touches a .db file directly

3. core.db:
SQLite — 
core_identity table (behavior/preference/tool rows). Populated with Remy's personality, speech style, and 15 tool proficiencies

4. interactions.db:
SQLite — 
timestamped log (category: movement/call/contact/tool/preference). Auto-created on first run, write-only for now

5. projects.db:
SQLite — 
title/status/tags/detail. Auto-created on first run, currently empty (no projects added yet)

5. .gitignore:
excludes __pycache__, venvs, .env, *.db, IDE folders, OS junk, logs

6. voice.py:
voice layer — local push-to-talk speech pipeline (sounddevice + keyboard for recording, faster-whisper for speech-to-text with automatic GPU→CPU fallback, pyttsx3 for text-to-speech), mic device selection, *action* marker stripping before speech, listen() and speak()

7. README.md               

# execution order:
1. v0.1:
What's built and working

Two files, cleanly separated:

llm_interaction.py — owns everything provider-specific. A PROVIDERS dict holds config for Gemini, Ollama, and a placeholder for a future CLI tool (Antigravity). Handles provider selection at startup, a connection check, and send_message().
remy_comm.py — the interface-agnostic hub. Holds conversation history, exposes one function (handle_input()) that any future front-end (terminal now, GUI/voice/robot later) will call the same way.

Live and confirmed working: Gemini, via Google's native google-genai SDK (Interactions API) — model gemini-3.6-flash, connected, holding a real multi-turn conversation.

Also configured, not yet tested end-to-end: Ollama, still wired via the OpenAI-compatible /v1/chat/completions path — since it's a different provider "type" in the dict, switching to it later is just picking option 2 at the menu.

Decisions made along the way
Ditched OmniRoute —
auth/routing headaches with free community providers weren't worth it. Talking to Gemini directly is simpler and more reliable.
Cloud-first, not local-first — 
VRAM card can't run a genuinely capable model without heavy CPU spillover and locking up your GPU. Gemini's free tier fills that gap for now.
Local isn't abandoned

Memory architecture is designed but not built. The plan: 
core_identity (small, always loaded — behaviors/preferences/tools, only things tagged as tool/preference interactions are allowed to rewrite it), 
an interactions log (categorized: movement, call, contact, tool, preference), 
and projects (tag-based selective retrieval — pulled in by name mention, tag match, or active status, full detail kept with no pruning needed). 
remy_comm.py already has commented-in hooks marking exactly where this plugs in once memory.py exists.

What's next, in likely order
Build memory.py — 
the SQLite schema for the three tables above, plus the retrieval functions remy_comm.py is already stubbed to call.

Wire the system prompt to load from core_identity instead of the hardcoded string currently in remy_comm.py.

2. v0.2:
Whats added,

new python file memory
database files core.db, intractions.db, project.db

memory.py as the single gatekeeper in front of three SQLite databases — remy_comm.py never touches a .db file directly, it only calls functions on memory.

remy_comm.py now rebuilds the system prompt fresh every turn: core + any relevant_projects(user_text) hit, then logs the exchange via log_interaction().

Core identity populated

core.db now holds real content instead of a placeholder:

Ollama connectivity confirmed — qwen2.5:7b direct, same endpoint pattern as before.


Known gaps, carried forward:

The "annoyed at repetition" trait is roleplayed from the prompt, not mechanically tracked — no repeat-detection logic exists yet.

core.db editing is still manual Python calls (add_core_entry, etc.) — no CLI/GUI for it.

projects.db is empty — no real projects added yet.

"tool"/"preference" interaction categories exist in the schema but nothing currently triggers them automatically to rewrite core.db.

3. v0.3:
Core build:

voice.py added — local, fully offline speech pipeline, plugged into remy_comm.py via a new run_voice() loop. Startup now asks terminal or voice mode.

Debugging fixes along the way:

STT input: dropped speech_recognition + pyaudio (pyaudio failed to build on Windows) → switched to sounddevice, which installs cleanly and gave a natural path to push-to-talk.
Push-to-talk: hold a key to record, release to stop — via the keyboard library. Default key moved from Right Ctrl to Space (Ctrl was unreliable with that library).
Mic selection: choose_microphone() lists all input devices at startup so you can pick headset vs. laptop mic explicitly.
GPU/CPU fallback for Whisper: tries GPU first, force-tests it with a silent dummy transcription at startup, and falls back to CPU automatically if CUDA libraries (cublas) are missing — no more mid-conversation crashes.
TTS reliability fix: pyttsx3 only speaking the first reply was a known Windows bug from reusing one engine instance — fixed by creating a fresh engine per speak() call.
Known limitation, not a bug: pyttsx3 has no output-device selection — Remy's voice always plays through whatever Windows' current default playback device is (headset vs. speakers has to be set at the OS level).

Parked for later polish (not blocking): a different/better TTS voice, and improving STT accuracy (either a larger Whisper model or speaking more clearly/deliberately).
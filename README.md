# Remy-Assistant-
A simple companion to help you manage your tasks, ideas and help you do what you want to do by automating the simple things, like moving tools to where you need them or just finding them wherever you last left them.

# File-system:


# execution order:
v0.1:
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
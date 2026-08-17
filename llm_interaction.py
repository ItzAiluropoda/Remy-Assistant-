"""
llm_interaction.py
-------------------
Everything related to talking to an LLM provider:
- Defines available providers (Gemini, Ollama, future CLI tools like Antigravity)
- Lets the user pick a provider at startup
- Runs a connection check and prints status + known limits
- Sends chat requests and returns the reply text

This file does NOT know about memory, GUI, or conversation history -
it only knows how to reach a model and get text back. remy_comm.py is
the layer that connects this to everything else.
"""

import os
import requests

# google-genai is only needed for "genai_sdk" type providers (currently Gemini).
# Imported lazily inside the functions that need it, so this file still runs
# fine even if the package isn't installed and you're only using Ollama.

# ---------------------------------------------------------------------------
# PROVIDERS
# ---------------------------------------------------------------------------
# To add a new provider later (e.g. a CLI tool like Antigravity), add a new
# entry here following the same shape.
#
#   display_name  - shown to the user in the selection menu
#   type          - "api"        normal HTTP request, OpenAI-compatible
#                                 /chat/completions format (e.g. Ollama)
#                   "genai_sdk"  uses Google's native google-genai SDK
#                                 instead of raw HTTP (currently Gemini -
#                                 this bypasses the OpenAI-compatibility
#                                 layer entirely, which is more reliable)
#                   "cli"        future - runs a local command instead of
#                                 an HTTP call, not implemented yet
#   base_url      - API endpoint (only used by "api" type; None otherwise)
#   api_key_env   - name of the environment variable holding the key
#                   (None if no key is needed, e.g. local Ollama)
#   requires_key  - whether this provider needs authentication
#   model         - exact model name/id the provider expects
#   notes         - free text about known limits, shown at connect time

PROVIDERS = {
    "gemini": {
        "display_name": "Gemini (cloud, free tier)",
        "type": "genai_sdk",
        "base_url": None,  # not used - the SDK handles the endpoint internally
        "api_key_env": "GEMINI_API_KEY",
        "requires_key": True,
        "model": "gemini-3.6-flash",
        "notes": "Free tier is rate-limited (check your live quota at aistudio.google.com). "
                 "Requires: pip install google-genai",
    },
    "ollama": {
        "display_name": "Ollama (local)",
        "type": "api",
        "base_url": "http://localhost:11434/v1/chat/completions",
        "api_key_env": None,
        "requires_key": False,
        "model": "qwen2.5:7b",
        "notes": "No rate limits - speed and quality depend on your GPU/VRAM.",
    },
    # Placeholder for a future CLI-based provider (e.g. Antigravity).
    # "cli" type providers aren't implemented yet - connection_check() and
    # send_message() will need a CLI-specific code path when this is built.
    "antigravity": {
        "display_name": "Antigravity CLI (not yet implemented)",
        "type": "cli",
        "base_url": None,
        "api_key_env": None,
        "requires_key": False,
        "model": None,
        "notes": "Placeholder - CLI integration not built yet.",
    },
}


# ---------------------------------------------------------------------------
# PROVIDER SELECTION
# ---------------------------------------------------------------------------

def choose_provider():
    """
    Prints the available providers and lets the user pick one.
    Returns the provider's key (e.g. "gemini") as a string.
    """
    print("Available providers:")
    keys = list(PROVIDERS.keys())
    for i, key in enumerate(keys, start=1):
        info = PROVIDERS[key]
        print(f"  {i}. {info['display_name']}")

    while True:
        choice = input(f"Select a provider (1-{len(keys)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            return keys[int(choice) - 1]
        print("Invalid choice, try again.")


# ---------------------------------------------------------------------------
# CONNECTION CHECK
# ---------------------------------------------------------------------------

def connection_check(provider_key):
    """
    Sends a minimal test request to confirm the provider is reachable and
    authenticated. Prints status + known limits. Returns True/False.
    """
    info = PROVIDERS[provider_key]

    if info["type"] == "cli":
        print(f"'{info['display_name']}' is not implemented yet - pick a different provider.")
        return False

    if info["type"] == "genai_sdk":
        return _genai_sdk_check(info)

    # --- "api" type (requests-based, OpenAI-compatible) ---
    api_key = None
    if info["requires_key"]:
        api_key = os.getenv(info["api_key_env"])
        if not api_key:
            print(f"ERROR: Environment variable {info['api_key_env']} is not set.")
            print(f"Set it before running Remy, e.g.: setx {info['api_key_env']} your-key-here")
            print("(then close and reopen your terminal for it to take effect)")
            return False

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": info["model"],
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }

    try:
        response = requests.post(info["base_url"], headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        print(f"Connected to {info['display_name']} (model: {info['model']})")
        if info["notes"]:
            print(f"Notes: {info['notes']}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Couldn't reach {info['display_name']}. Is it running / are you online?")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: {info['display_name']} rejected the request - {e}")
        return False


def _genai_sdk_check(info):
    """
    Connection check for "genai_sdk" type providers (currently Gemini),
    using Google's native google-genai SDK instead of raw HTTP.
    """
    api_key = os.getenv(info["api_key_env"])
    if not api_key:
        print(f"ERROR: Environment variable {info['api_key_env']} is not set.")
        print(f"Set it before running Remy, e.g.: setx {info['api_key_env']} your-key-here")
        print("(then close and reopen your terminal for it to take effect)")
        return False

    try:
        from google import genai
    except ImportError:
        print("ERROR: google-genai package not installed. Run: pip install google-genai")
        return False

    try:
        # genai.Client() automatically picks up GEMINI_API_KEY from the environment.
        client = genai.Client()
        interaction = client.interactions.create(
            model=info["model"],
            input="ping",
        )
        _ = interaction.output_text  # confirm we actually got a usable reply
        print(f"Connected to {info['display_name']} (model: {info['model']})")
        if info["notes"]:
            print(f"Notes: {info['notes']}")
        return True
    except Exception as e:
        print(f"ERROR: {info['display_name']} connection failed - {e}")
        return False


# ---------------------------------------------------------------------------
# SENDING MESSAGES
# ---------------------------------------------------------------------------

def send_message(provider_key, messages):
    """
    Sends a full conversation (list of {"role": ..., "content": ...} dicts)
    to the chosen provider and returns the model's reply text as a string.
    """
    info = PROVIDERS[provider_key]

    if info["type"] == "cli":
        raise NotImplementedError(f"{info['display_name']} is not implemented yet.")

    if info["type"] == "genai_sdk":
        return _genai_sdk_send(info, messages)

    # --- "api" type (requests-based, OpenAI-compatible) ---
    api_key = os.getenv(info["api_key_env"]) if info["requires_key"] else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": info["model"],
        "messages": messages,
    }

    response = requests.post(info["base_url"], headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _genai_sdk_send(info, messages):
    """
    Sends a conversation to a "genai_sdk" type provider (currently Gemini)
    using Google's native Interactions API, in client-side/stateless mode
    (store=False) - we resend the whole history ourselves each turn, same
    as we do for "api" type providers, so remy_comm.py doesn't need to
    care which type of provider it's talking to.

    NOTE: the Interactions API is in beta - if Google's system-prompt
    handling changes, this is the function to update. For now, any
    "system" role message is folded into the first user turn as plain
    text, since a dedicated system role isn't confirmed for this endpoint yet.
    """
    from google import genai

    client = genai.Client()

    history = []
    system_text = None

    for m in messages:
        if m["role"] == "system":
            system_text = m["content"]
            continue

        step_type = "user_input" if m["role"] == "user" else "model_output"
        text = m["content"]

        # Prepend the system prompt once, to the first real user message.
        if system_text and step_type == "user_input":
            text = f"[Instructions: {system_text}]\n\n{text}"
            system_text = None

        history.append({
            "type": step_type,
            "content": [{"type": "text", "text": text}],
        })

    interaction = client.interactions.create(
        model=info["model"],
        store=False,
        input=history,
    )
    return interaction.output_text

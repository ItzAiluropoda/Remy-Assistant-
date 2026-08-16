"""
Remy - Basic Version
Takes text input, sends it to OmniRoute, prints the response.
This is step 1: just proving the connection works. No memory, no history yet.
"""

import requests

# --- Configuration ---
# Change these two values to match your OmniRoute setup
OMNIROUTE_URL = "http://localhost:20128/v1/chat/completions"  # e.g. "http://localhost:20128/v1/chat/completions"
MODEL_NAME = "auto/gemini"  # e.g. "claude-sonnet-4-5" - copy exactly from OmniRoute dashboard


def ask_remy(user_message):
    """
    Sends a single message to the model via OmniRoute and returns the reply text.
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": user_message}
        ]
    }

    response = requests.post(OMNIROUTE_URL, json=payload)

    # If something went wrong (bad model name, OmniRoute not running, etc.)
    # this will raise an error with details instead of failing silently.
    response.raise_for_status()

    data = response.json()
    reply = data["choices"][0]["message"]["content"]
    return reply


def main():
    print("Remy (basic test) is online. Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() == "exit":
            print("Goodbye.")
            break

        try:
            reply = ask_remy(user_input)
            print(f"Remy: {reply}\n")
        except requests.exceptions.ConnectionError:
            print("ERROR: Couldn't reach OmniRoute. Is it running on localhost:20128?\n")
        except requests.exceptions.HTTPError as e:
            print(f"ERROR: OmniRoute returned an error - {e}\n")


if __name__ == "__main__":
    main()
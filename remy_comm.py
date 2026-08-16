"""
remy_comm.py
-------------
The central communication hub for Remy.

This file sits between:
  - llm_interaction.py   (talks to the actual model - Gemini/Ollama/etc.)
  - INPUT sources:  terminal (now), GUI (later), voice/STT (later), robot sensors (later)
  - OUTPUT sinks:   terminal (now), GUI (later), voice/TTS (later), robot actuators (later)

Nothing in here should know HOW Gemini/Ollama works (that's llm_interaction's
job), and nothing in here should know HOW a GUI window, microphone, or robot
motor works either - those will live in their own files (gui.py, voice.py,
robot.py) and will all call into RemyComm the same way the terminal loop
below does. This file's only job is moving messages back and forth and
holding the current conversation.
"""

import llm_interaction
# import memory  # TODO: uncomment once memory.py exists (see SYSTEM PROMPT section below)

# ---------------------------------------------------------------------------
# SYSTEM PROMPT / CORE IDENTITY
# ---------------------------------------------------------------------------
# FUTURE (once memory.py exists): the system prompt should be BUILT, not
# hardcoded - pulled fresh from memory.py at startup so editing Remy's
# personality/preferences/tools means editing the memory file, not this code.
#
# memory.py will need to expose something like:
#   memory.get_core_identity()
#       -> returns the small "who Remy is" block: behaviors, tone rules,
#          your standing preferences, list of available tools/skills.
#          This is the piece that "tool" and "preference" type interactions
#          are allowed to rewrite.
#   memory.get_relevant_projects(user_text)
#       -> returns any project detail worth injecting THIS turn, based on:
#          a) the project is mentioned by name/title in user_text
#          b) one of the project's tags matches a keyword in user_text
#          c) the project's status == "active"
#          Returns "" (nothing) most of the time - only pulls in project
#          detail when actually relevant, to keep token usage low.
#
# Rough shape once wired up:
#
# def build_system_prompt(user_text=""):
#     core = memory.get_core_identity()
#     project_context = memory.get_relevant_projects(user_text)
#     content = core
#     if project_context:
#         content += "\n\nRelevant project context:\n" + project_context
#     return {"role": "system", "content": content}
#
# For now (no memory.py yet), a static prompt is used so the file can run
# on its own:

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are Remy, a personal desktop assistant. Be concise, direct, "
        "and helpful. You do not have long-term memory yet in this version."
    ),
}


# ---------------------------------------------------------------------------
# CORE CLASS - used by every interface (terminal, GUI, voice, robot)
# ---------------------------------------------------------------------------

class RemyComm:
    """
    Holds the active provider + conversation history for one running session.
    Any input source creates one of these and calls .handle_input() to get
    a reply. This is the single shared entry point - GUI/voice/robot code
    should never call llm_interaction directly, always go through here.
    """

    def __init__(self, provider_key):
        self.provider_key = provider_key
        self.history = [SYSTEM_PROMPT]
        # FUTURE: once memory.py exists, SYSTEM_PROMPT won't be fixed at
        # startup - see handle_input() below, since project relevance
        # depends on what the user actually says each turn.

    def handle_input(self, user_text):
        """
        INPUT:  raw text, from ANY source -
                terminal typing / GUI text box / voice-to-text transcript /
                robot command parser output.
        OUTPUT: Remy's reply as a plain string. The caller decides what to
                do with it - print it, put it in a GUI, feed it to
                text-to-speech, or send it to the robot's actuators.
        """
        # FUTURE (once memory.py exists): rebuild self.history[0] here each
        # turn using build_system_prompt(user_text), so relevant project
        # context (tag/name match, or currently active) gets pulled in only
        # when needed - e.g.:
        #     self.history[0] = build_system_prompt(user_text)
        # Also this is the natural spot to log the turn into memory.py's
        # interactions table (category "call", "tool", "preference", etc.)
        # once that logging function exists.

        self.history.append({"role": "user", "content": user_text})
        reply = llm_interaction.send_message(self.provider_key, self.history)
        self.history.append({"role": "assistant", "content": reply})
        return reply


# ---------------------------------------------------------------------------
# TERMINAL INTERFACE (v1 - active now)
# ---------------------------------------------------------------------------
# Future interfaces (gui.py, voice.py, robot.py) will import RemyComm the
# same way this does, and call remy.handle_input(...) instead of duplicating
# this loop. This function is the ONLY part of the file specific to
# "typing in a terminal" - everything above it is interface-agnostic.

def run_terminal():
    provider_key = llm_interaction.choose_provider()

    if not llm_interaction.connection_check(provider_key):
        print("Connection check failed. Fix the issue above and try again.")
        return

    remy = RemyComm(provider_key)

    print("\nRemy is online. Type 'exit' to quit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            print("Goodbye.")
            break

        try:
            reply = remy.handle_input(user_input)
            print(f"Remy: {reply}\n")
        except Exception as e:
            print(f"ERROR: {e}\n")


# ---------------------------------------------------------------------------
# FUTURE INTERFACE HOOKS (not implemented yet - marking where they'll go)
# ---------------------------------------------------------------------------
# def run_gui():
#     # gui.py owns the window/widgets. For each message the user sends in
#     # the GUI, it will call: reply = remy.handle_input(text_from_textbox)
#     # and display `reply` in the chat window. Same RemyComm class as above.
#
# def run_voice():
#     # voice.py owns the mic (speech-to-text) and speaker (text-to-speech).
#     # Flow: mic audio -> STT -> text -> remy.handle_input(text) -> reply
#     #       -> TTS -> speaker audio.
#
# def run_robot():
#     # robot.py owns sensor input (camera/distance/mic) and actuator output
#     # (movement/speech). Parsed commands get passed into
#     # remy.handle_input(...) the same way; replies get routed to
#     # whichever actuator/response system is relevant.


if __name__ == "__main__":
    run_terminal()

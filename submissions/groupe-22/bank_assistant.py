# /// script
# requires-python = ">=3.10"
# dependencies = ["websockets>=14", "sounddevice", "numpy", "python-dotenv", "weasyprint"]
# ///
"""Voice banking assistant for blind and visually impaired customers.

From "I'm looking for" to "it's done", without looking for anything or clicking: the
customer says what they need, and the assistant understands, explains from the bank's
procedure sheets (bank_docs/), acts (simulation, request), or hands over to a human
with the context. Four procedures: complaint, lost code, loan, wealth management.
Same audio options as realtime_demo.py.

    uv run bank_assistant.py
    uv run bank_assistant.py --push-to-talk  # noisy room: Enter to talk, Enter to send
"""

from functools import partial

import bank_store
from bank_tools import Conversation, instructions, run_tool, tools_for
from realtime_demo import parse_args, run

if __name__ == "__main__":
    # The terminal is the demo customer Camille Martin, logged in, as on the web after
    # the Connexion démo: her accounts, cards and operations (demo_customer.py).
    _, session = bank_store.new_session("camille")
    # One conversation per run: the procedure (démarche) in progress, and the actions
    # waiting for a yes, confirmed only after the customer has spoken (on_event).
    conversation = Conversation(session, "voice")
    run_in_conversation = partial(run_tool, conversation=conversation)
    run(
        parse_args(__doc__),
        instructions(session, "voice"),
        tools_for(session),
        run_in_conversation,
        conversation.on_event,
    )

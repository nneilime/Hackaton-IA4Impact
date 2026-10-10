# /// script
# requires-python = ">=3.10"
# dependencies = ["websockets>=14", "sounddevice", "numpy", "python-dotenv"]
# ///
"""Voice Q&A agent over the documents in docs/, using the OpenAI Realtime API.

Ask a question out loud; the agent looks it up with the list_documents and
read_document tools (see doc_tools.py) and answers. Interrupt it any time by talking,
or by pressing Enter.

    uv run realtime_demo.py              # headphones (full duplex, barge-in)
    uv run realtime_demo.py --speakers   # laptop speakers (mic muted while it talks)
    uv run realtime_demo.py --push-to-talk  # noisy room: Enter to talk, Enter to send
"""

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv

from doc_tools import TOOLS, run_tool

RATE = 24000  # Realtime API audio: 24 kHz, 16-bit, mono PCM
CHUNK = 480  # 20 ms of audio per mic/speaker block
# A stream that hasn't called back for this long is frozen: Bluetooth call audio drops
# now and then ("corrupted SCO packet"), and PipeWire only restarts the headset when a
# stream is reopened. Close frozen streams, never stop() them: that waits 40 s and more.
STALL = 2.0

INSTRUCTIONS = """\
You are a voice assistant that answers questions about a set of documents.
Be concise and precise: every word you say costs the user time.

- To answer, always look the information up: call list_documents, then read_document
  on the documents that look relevant. Never answer from memory or general knowledge.
- Before looking things up, say at most two or three words ("Let me check.") once per
  question, not before every tool call.
- Answer in one or two short sentences. Start with the answer itself: no preamble,
  no restating the question, no summary of your search, no closing offer of help.
- Be precise: give the exact figures, dates, names and terms from the documents
  rather than vague paraphrases. Name the source document in a few words.
- If the documents don't contain the answer, say so in one sentence. If the question
  is ambiguous, ask one short clarifying question instead of guessing.
- Only give more detail when the user asks for it.
- Spoken style: no lists, no markdown.
- Speak in the same language as the user, even if the documents are in another one.
- When the conversation starts, greet the user in one short sentence that says what
  the documents are about.
"""

# Used with --no-tools: a plain voice assistant, to rule out the tools when debugging.
PLAIN_INSTRUCTIONS = (
    "You are a friendly voice assistant. Keep answers short and conversational, "
    "like a real phone call. Speak in the same language as the user."
)


class Player:
    """Plays streamed PCM16 audio and tracks how much of the current item was heard."""

    def __init__(self):
        self.buf = bytearray()
        self.lock = threading.Lock()
        self.item_id = None
        self.played = 0  # samples of item_id handed to the speakers
        self.interrupted = None  # item_id whose late audio deltas must be dropped
        self.last_sound = 0.0
        self.stream = None
        self.open()

    def open(self):
        """(Re)open the speaker stream."""
        self.close()
        self.last_callback = time.monotonic()
        self.stream = sd.OutputStream(
            samplerate=RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK,
            callback=self._callback,
        )
        self.stream.start()

    def close(self):
        if self.stream:
            self.stream.close()

    def stalled(self):
        return time.monotonic() - self.last_callback > STALL

    def _callback(self, outdata, frames, _time, _status):
        self.last_callback = time.monotonic()
        n = frames * 2
        with self.lock:
            chunk = bytes(self.buf[:n])
            del self.buf[:n]
            self.played += len(chunk) // 2
            if chunk:
                self.last_sound = time.monotonic()
        outdata[:] = np.frombuffer(chunk.ljust(n, b"\0"), dtype=np.int16).reshape(-1, 1)

    def add(self, item_id, pcm):
        with self.lock:
            if item_id == self.interrupted:
                return
            if item_id != self.item_id:
                self.item_id, self.played = item_id, 0
            self.buf.extend(pcm)

    def interrupt(self):
        """Drop unplayed audio. Returns (item_id, ms actually played) or None if silent."""
        with self.lock:
            if not self.buf:
                return None
            self.buf.clear()
            self.interrupted = self.item_id
            return self.item_id, self.played * 1000 // RATE

    def is_speaking(self, tail=0.4):
        with self.lock:
            return bool(self.buf) or time.monotonic() - self.last_sound < tail


class NoiseGate:
    """Replaces mic audio quieter than a threshold with silence.

    In a noisy room the voice detection hears the people around you and never decides
    you've stopped talking. Behind the gate, the room turns into silence and only a
    voice close to the mic gets through.
    """

    def __init__(self, dbfs, hold=0.5):
        self.threshold = 32768 * 10 ** (dbfs / 20)
        self.hold = round(hold * RATE / CHUNK)  # blocks kept open after a loud one
        self.open_for = 0

    def __call__(self, pcm):
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if np.sqrt(np.mean(samples**2)) > self.threshold:
            self.open_for = self.hold
        elif self.open_for:
            self.open_for -= 1
        else:
            return bytes(len(pcm))
        return pcm


def pick_audio_device():
    """Raw ALSA hw devices often reject 24 kHz; PipeWire/Pulse resample for us."""
    names = [d["name"] for d in sd.query_devices()]
    return next((n for n in ("pipewire", "pulse", "default") if n in names), None)


def mic_instead_of_bluetooth():
    """If the default mic is a Bluetooth headset's, return a wired one (the laptop's).

    The headset mic only works in call mode, whose audio link fails every few seconds
    on some adapters ("corrupted SCO packet"). Keeping the headset in music mode and
    recording from the laptop mic is reliable, and the headset sounds much better.
    """
    try:
        source = subprocess.run(
            ["pactl", "get-default-source"], capture_output=True, text=True
        ).stdout.strip()
        sources = json.loads(
            subprocess.run(
                ["pactl", "-f", "json", "list", "short", "sources"],
                capture_output=True,
                text=True,
            ).stdout
        )
    except (FileNotFoundError, json.JSONDecodeError):  # no PulseAudio/PipeWire tools
        return None
    if not source.startswith("bluez_input."):
        return None
    return next(
        (s["name"] for s in sources if s["name"].startswith("alsa_input.")), None
    )


def bluetooth_call_mode():
    """Put a Bluetooth headset in call mode (HFP) before any audio stream opens.

    Its mic only works in call mode. Left to PipeWire, the switch happens when the mic
    opens and freezes both streams, so the model never hears you. Some adapters also
    fail on the default mSBC codec ("SCO packet for unknown connection handle"), so use
    CVSD. Returns (card, previous profile) to restore on exit, or None.
    """
    try:
        source = subprocess.run(
            ["pactl", "get-default-source"], capture_output=True, text=True
        ).stdout.strip()
        cards = json.loads(
            subprocess.run(
                ["pactl", "-f", "json", "list", "cards"], capture_output=True, text=True
            ).stdout
        )
    except (FileNotFoundError, json.JSONDecodeError):  # no PulseAudio/PipeWire tools
        return None
    if not source.startswith("bluez_input."):
        return None
    # bluez_input.E8:9E:13:F6:58:17 (or E8_9E_...) belongs to bluez_card.E8_9E_...
    address = source.removeprefix("bluez_input.").split(".")[0].replace(":", "_")
    for card in cards:
        if card["name"] == f"bluez_card.{address}":
            if "headset-head-unit-cvsd" not in card["profiles"]:
                return None
            subprocess.run(
                ["pactl", "set-card-profile", card["name"], "headset-head-unit-cvsd"],
                check=True,
            )
            time.sleep(2)  # let PipeWire create the call-mode mic and speaker
            print("Bluetooth headset switched to call mode (restored on exit).")
            return card["name"], card["active_profile"]
    return None


async def send(ws, event):
    await ws.send(json.dumps(event))


async def stream_mic(ws, player, half_duplex, talking=None, gate=None):
    loop = asyncio.get_running_loop()
    q = asyncio.Queue()

    def callback(indata, _frames, _time, _status):
        loop.call_soon_threadsafe(q.put_nowait, bytes(indata))

    while True:
        mic = sd.RawInputStream(
            samplerate=RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK,
            callback=callback,
        )
        mic.start()
        try:
            while True:
                try:
                    pcm = await asyncio.wait_for(q.get(), STALL)
                except asyncio.TimeoutError:
                    print("\n  [mic froze, reopening it]", flush=True)
                    break
                if talking is not None and not talking.is_set():
                    continue  # push-to-talk: only send audio during your turn
                if half_duplex and player.is_speaking():
                    continue  # don't let the model hear itself through the speakers
                if gate:
                    pcm = gate(pcm)
                await send(
                    ws,
                    {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(pcm).decode(),
                    },
                )
        finally:
            mic.close()


async def show_levels(gate_dbfs):
    """--levels: print the mic level, to choose the --noise-gate threshold."""
    loop = asyncio.get_running_loop()
    q = asyncio.Queue()

    def callback(indata, _frames, _time, _status):
        loop.call_soon_threadsafe(q.put_nowait, bytes(indata))

    with sd.RawInputStream(
        samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK, callback=callback
    ):
        while True:
            loudest = 0.0
            for _ in range(5):  # one line per 100 ms, as loud as the gate sees it
                samples = np.frombuffer(await q.get(), dtype=np.int16)
                rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
                loudest = max(loudest, rms)
            dbfs = 20 * np.log10(max(loudest, 1) / 32768)
            bar = "#" * max(0, round(dbfs) + 60)
            print(f"{dbfs:6.1f} dBFS {bar:<60} {'heard' if dbfs > gate_dbfs else ''}")


async def watch_speakers(player):
    while True:
        await asyncio.sleep(STALL)
        if player.stalled():
            print("\n  [speakers froze, reopening them]", flush=True)
            player.open()


async def stop_playback(ws, player):
    """Stop playback and tell the server what was actually heard, so the
    conversation history matches reality."""
    if cut := player.interrupt():
        item_id, played_ms = cut
        await send(
            ws,
            {
                "type": "conversation.item.truncate",
                "item_id": item_id,
                "content_index": 0,
                "audio_end_ms": played_ms,
            },
        )
        print(" [interrupted]")


def enter_presses():
    """A queue that gets an item each time Enter is pressed."""
    loop = asyncio.get_running_loop()
    enter = asyncio.Queue()

    def on_stdin():
        if sys.stdin.readline():
            enter.put_nowait(None)
        else:  # stdin closed
            loop.remove_reader(sys.stdin)

    loop.add_reader(sys.stdin, on_stdin)
    return enter


async def stop_answer(ws, player):
    """Cut the assistant off: what it's saying and the rest of its answer."""
    await stop_playback(ws, player)
    await send(ws, {"type": "response.cancel"})


async def enter_interrupts(ws, player):
    """Enter cuts the assistant off, greeting included, when talking over it doesn't
    work: behind the noise gate, or with --speakers (mic muted while it talks)."""
    enter = enter_presses()
    while True:
        await enter.get()
        await stop_answer(ws, player)


async def push_to_talk(ws, player, talking):
    """Enter starts your turn, Enter again sends it.

    In a noisy room, voice detection takes the people around you for you: it waits
    for you to finish while they talk, and cancels its answers when they speak up.
    """
    enter = enter_presses()
    while True:
        await enter.get()
        await stop_answer(ws, player)
        await send(ws, {"type": "input_audio_buffer.clear"})
        talking.set()
        print("  [listening... press Enter to send]", flush=True)
        await enter.get()
        talking.clear()
        await send(ws, {"type": "input_audio_buffer.commit"})
        await send(ws, {"type": "response.create"})


async def run_tool_calls(ws, response, run_tool):
    """Run the tools the model asked for, send back the results, and let it answer."""
    calls = [item for item in response["output"] if item["type"] == "function_call"]
    if not calls or response["status"] != "completed":
        return
    for call in calls:
        print(f"\n  [tool] {call['name']}({call['arguments']})")
        await send(
            ws,
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    # in a thread: a recap PDF takes half a second
                    "output": await asyncio.to_thread(
                        run_tool, call["name"], call["arguments"]
                    ),
                },
            },
        )
    await send(ws, {"type": "response.create"})


async def handle_events(ws, player, run_tool, on_event=None):
    speaking_item = None
    async for message in ws:
        event = json.loads(message)
        if on_event:  # e.g. bank_tools.Conversation: the user's turns
            on_event(event)
        match event["type"]:
            case "response.output_audio.delta":
                player.add(event["item_id"], base64.b64decode(event["delta"]))
            case "response.output_audio_transcript.delta":
                if event["item_id"] != speaking_item:
                    speaking_item = event["item_id"]
                    print("\nassistant> ", end="")
                print(event["delta"], end="", flush=True)
            case "response.output_audio_transcript.done":
                print()
            case "input_audio_buffer.speech_started":
                print("\n  [hearing you...]", flush=True)
                await stop_playback(ws, player)
            case "conversation.item.input_audio_transcription.completed":
                print(f"\n  you> {event['transcript'].strip()}")
            case "response.done":
                response = event["response"]
                if response["status"] in ("failed", "incomplete"):  # e.g. rate limit
                    print(
                        f"\n[response {response['status']}] {response.get('status_details')}"
                    )
                # Tool calls are handled once the response is complete: sending
                # response.create while one is still active would be rejected.
                await run_tool_calls(ws, response, run_tool)
            case "error":
                # Enter cancels the current answer whether or not there is one
                if event["error"].get("code") != "response_cancel_not_active":
                    print(f"\n[error] {event['error'].get('message')}")


def session_config(args, instructions, tools):
    if args.no_tools:
        instructions, tools = PLAIN_INSTRUCTIONS, []
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": instructions,
            **({"tools": tools, "tool_choice": "auto"} if tools else {}),
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": RATE},
                    "noise_reduction": {
                        "type": "far_field"
                        if args.speakers or args.laptop_mic
                        else "near_field"
                    },
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    # semantic_vad waits until you've finished your thought, not just a pause
                    "turn_detection": None
                    if args.push_to_talk
                    else {"type": "semantic_vad", "eagerness": args.eagerness},
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": RATE},
                    "voice": args.voice,
                    "speed": args.speed,
                },
            },
        },
    }


async def main(args, instructions, tools, run_tool, on_event=None):
    load_dotenv()
    key = os.environ["OPENAI_API_KEY"]
    if args.mic:
        os.environ["PULSE_SOURCE"] = args.mic  # read by the "pulse" device on open
    sd.default.device = args.device or ("pulse" if args.mic else pick_audio_device())
    if args.levels:
        return await show_levels(args.noise_gate)
    url = f"wss://api.openai.com/v1/realtime?model={args.model}"

    async with websockets.connect(
        url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=None
    ) as ws:
        await send(ws, session_config(args, instructions, tools))
        await send(ws, {"type": "response.create"})  # let the assistant say hi first

        player = Player()
        tasks = [watch_speakers(player), handle_events(ws, player, run_tool, on_event)]
        if args.push_to_talk:
            talking = asyncio.Event()
            tasks += [
                stream_mic(ws, player, args.speakers, talking),
                push_to_talk(ws, player, talking),
            ]
            start = "Press Enter, ask your question, press Enter again."
        else:
            gate = NoiseGate(args.noise_gate)
            tasks += [
                stream_mic(ws, player, args.speakers, gate=gate),
                enter_interrupts(ws, player),
            ]
            start = "Start talking (Enter cuts the assistant off)."
        try:
            print(f"Connected to {args.model}. {start} Ctrl+C to quit.")
            if not args.push_to_talk and args.noise_gate > -90:
                print(
                    f"Noise gate: the model only hears sound above {args.noise_gate:g} dBFS"
                    " (--noise-gate; check your voice with --levels)."
                )
            await asyncio.gather(*tasks)
        finally:
            player.close()


def parse_args(description):
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model", default="gpt-realtime-2.1-mini")
    parser.add_argument(
        "--voice", default="marin", help="e.g. marin, cedar, alloy, verse"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="speaking speed, 0.25 (slow) to 1.5 (fast)",
    )
    parser.add_argument(
        "--eagerness",
        default="low",
        choices=["low", "medium", "high", "auto"],
        help="how quickly the model jumps in after you stop talking",
    )
    parser.add_argument(
        "--speakers",
        action="store_true",
        help="no headphones: mute the mic while the assistant talks to avoid echo",
    )
    parser.add_argument(
        "--noise-gate",
        type=float,
        metavar="DBFS",
        help="mute the mic below this level, so the people around you don't keep it"
        " listening: raise it (e.g. -6) if it stays on [hearing you...], lower it"
        " (e.g. -20) if it doesn't hear you; -90 turns it off (default: -10 with the"
        " laptop mic, off with a headset mic)",
    )
    parser.add_argument(
        "--levels",
        action="store_true",
        help="just show the mic level, to choose --noise-gate: talk and stay silent",
    )
    parser.add_argument(
        "--push-to-talk",
        action="store_true",
        help="noisy room: press Enter to talk and Enter again to send, instead of"
        " voice detection (which hears the people around you as you talking)",
    )
    parser.add_argument(
        "--device", help="sounddevice name/index (see: python -m sounddevice)"
    )
    parser.add_argument(
        "--mic",
        help="PulseAudio/PipeWire source to record from instead of the default one"
        " (see: pactl list short sources)",
    )
    parser.add_argument(
        "--headset-mic",
        action="store_true",
        help="Bluetooth headset: talk into its mic (call mode) instead of the laptop's;"
        " the call audio link drops out on some laptops",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="plain voice assistant without the tools (for debugging)",
    )
    return parser.parse_args()


def run(args, instructions, tools, run_tool, on_event=None):
    """Pick the mic and talk until Ctrl+C. Also used by bank_assistant.py, whose
    on_event gets every server event."""
    args.laptop_mic = False
    restore = None
    if not (args.mic or args.device):
        if args.headset_mic:
            restore = bluetooth_call_mode()
        elif mic := mic_instead_of_bluetooth():
            args.mic, args.laptop_mic = mic, True
            print(f"Bluetooth headset: listening through {mic} (or --headset-mic).")
    if args.noise_gate is None:  # the laptop mic hears the whole room, a headset's doesn't
        args.noise_gate = -10 if args.laptop_mic else -90
    try:
        asyncio.run(main(args, instructions, tools, run_tool, on_event))
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        if restore:  # back to the headset's normal (music) profile
            subprocess.run(["pactl", "set-card-profile", *restore])


if __name__ == "__main__":
    run(parse_args(__doc__), INSTRUCTIONS, TOOLS, run_tool)

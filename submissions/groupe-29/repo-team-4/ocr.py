"""Run LightOnOCR-3 (grounding mode) on every .jpg in a folder through the HF Space.

Usage: python ocr.py <folder> [--out DIR] [--model 4B|1B|0.8B] [--max-tokens N] [--overwrite | --redo-truncated]

For each image, a folder named after the file is created in --out (default: the current directory) with:
  raw.txt        the model output, with the ![label](x1,y1,x2,y2) markers
  result.md      the Markdown transcription
  blocks.json    the layout blocks: label, bbox (0-1000 and pixels), text
  result.json    everything the Space returned (model, status message, sizes, ...) plus the max_tokens used
  annotated.jpg  the image with every block drawn on it

The Space's endpoints read their inputs from Gradio event data, which gradio_client cannot send,
so this talks to the Gradio queue over HTTP directly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageDraw

BASE = "https://lightonai-lightonocr-3-demo.hf.space/gradio_api"
RUN_FN_INDEX = 2  # the "on_run" dependency (lo_run event) in the Space's /config
MAX_TOKENS_LIMIT = 12288  # the highest value the Space's "Max output tokens" slider allows
LEGACY_MAX_TOKENS = 6144  # what results saved before max_tokens was recorded were produced with
COLORS = {"title": "#d62728", "section": "#ff7f0e", "text": "#1f77b4", "list": "#2ca02c", "caption": "#9467bd",
          "footnote": "#8c564b", "table": "#e377c2", "chart": "#17becf", "formula": "#bcbd22", "code": "#7f7f7f",
          "image": "#ff1493", "header": "#555555", "footer": "#555555", "page_number": "#555555"}

load_dotenv()


def client() -> httpx.Client:
    token = os.environ.get("HF_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(headers=headers, timeout=httpx.Timeout(60.0, read=900.0), follow_redirects=True)


def upload(http: httpx.Client, path: Path) -> str:
    with path.open("rb") as f:
        r = http.post(f"{BASE}/upload", files={"files": (path.name, f, "image/jpeg")})
    r.raise_for_status()
    return r.json()[0]


def run(http: httpx.Client, server_path: str, name: str, model: str, max_tokens: int) -> dict:
    """Queue an lo_run event and wait for its final value."""
    session = uuid.uuid4().hex[:11]
    event_data = {"path": server_path, "name": name, "page": 1, "model": model, "mode": "grounding",
                  "temperature": 0.2, "max_tokens": max_tokens, "longest_edge": 2048}
    r = http.post(f"{BASE}/queue/join", json={"data": [], "event_data": event_data, "fn_index": RUN_FN_INDEX,
                                              "trigger_id": 1, "session_hash": session})
    r.raise_for_status()
    with http.stream("GET", f"{BASE}/queue/data", params={"session_hash": session}) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            msg = json.loads(line[5:])
            kind = msg.get("msg")
            if kind == "estimation" and msg.get("rank"):
                print(f"  queued, position {msg['rank']}", flush=True)
            elif kind == "process_completed":
                out = msg.get("output") or {}
                if not msg.get("success", False):
                    raise RuntimeError(out.get("error") or "the Space reported a failure")
                return out["data"][0]
            elif kind == "unexpected_error":
                raise RuntimeError(msg.get("message") or "unexpected error")
    raise RuntimeError("the stream closed before the result arrived")


def tokens_used(value: dict) -> int | None:
    """Read the generated token count from the Space's status message ("... · 6,144 tokens · ...")."""
    m = re.search(r"([\d,]+) tokens", value.get("message", ""))
    return int(m.group(1).replace(",", "")) if m else None


def is_truncated(value: dict) -> bool:
    """True when the model stopped because it hit max_tokens, so the end of the page is missing."""
    used = tokens_used(value)
    return used is not None and used >= value.get("max_tokens", LEGACY_MAX_TOKENS)


def save(image_path: Path, value: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        draw = ImageDraw.Draw(im)
        width = max(2, round(max(w, h) / 600))
        blocks = []
        for b in value.get("blocks", []):
            x1, y1, x2, y2 = b["bbox"]
            x1, x2 = sorted((x1, x2))  # the model occasionally emits a box with swapped corners
            y1, y2 = sorted((y1, y2))
            px = [round(x1 * w / 1000), round(y1 * h / 1000), round(x2 * w / 1000), round(y2 * h / 1000)]
            blocks.append({**b, "bbox_pixels": px})
            color = COLORS.get(b["label"], "#999999")
            draw.rectangle(px, outline=color, width=width)
            draw.text((px[0] + width, px[1] + width), b["label"], fill=color)
        im.save(out / "annotated.jpg", quality=90)

    (out / "raw.txt").write_text(value.get("raw", ""), encoding="utf-8")
    (out / "result.md").write_text(value.get("markdown", ""), encoding="utf-8")
    (out / "blocks.json").write_text(json.dumps({"source": str(image_path), "width": w, "height": h, "blocks": blocks},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "result.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="folder containing the .jpg files")
    parser.add_argument("--model", default="4B", choices=["4B", "1B", "0.8B"])
    parser.add_argument("--out", type=Path, default=Path.cwd(), help="where the per-image folders go")
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS_LIMIT,
                        help=f"output token budget per page (256-{MAX_TOKENS_LIMIT})")
    redo = parser.add_mutually_exclusive_group()
    parser.add_argument("--only", nargs="+", metavar="NAME", help="only these images (file names without .jpg)")
    redo.add_argument("--overwrite", action="store_true", help="redo files that already have a result")
    redo.add_argument("--redo-truncated", action="store_true",
                      help="redo only the existing results that hit their max_tokens limit")
    args = parser.parse_args()

    if not 256 <= args.max_tokens <= MAX_TOKENS_LIMIT:
        parser.error(f"--max-tokens must be between 256 and {MAX_TOKENS_LIMIT}")

    if not args.folder.is_dir():
        parser.error(f"{args.folder} is not a folder")
    images = sorted(p for p in args.folder.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg"))
    if args.only:
        images = [p for p in images if p.stem in args.only]
    if not images:
        print(f"No .jpg files in {args.folder}")
        return 1

    failed, truncated = 0, []
    with client() as http:
        for i, path in enumerate(images, 1):
            out = args.out / path.stem
            existing = out / "result.json"
            if existing.exists() and not args.overwrite:
                if not (args.redo_truncated and is_truncated(json.loads(existing.read_text(encoding="utf-8")))):
                    print(f"[{i}/{len(images)}] {path.name}: already done, skipping")
                    continue
            print(f"[{i}/{len(images)}] {path.name}", flush=True)
            try:
                value = run(http, upload(http, path), path.name, args.model, args.max_tokens)
                if value.get("status") == "error":
                    raise RuntimeError(value.get("message"))
                value["max_tokens"] = args.max_tokens
                save(path, value, out)
                print(f"  {value.get('message', 'done')} -> {out}")
                if is_truncated(value):
                    truncated.append(path.name)
                    print(f"  warning: hit the {args.max_tokens}-token limit, the end of the page is missing",
                          file=sys.stderr)
            except Exception as e:
                failed += 1
                print(f"  failed: {e}", file=sys.stderr)
    print(f"Done: {len(images) - failed} ok, {failed} failed")
    if truncated:
        print(f"Still truncated ({len(truncated)}): {', '.join(truncated)}", file=sys.stderr)
    return 1 if failed or truncated else 0


if __name__ == "__main__":
    sys.exit(main())

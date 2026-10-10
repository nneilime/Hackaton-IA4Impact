"""Tools the voice agent can call to look things up in the docs/ folder."""

import json
from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"
EXTENSIONS = {".md", ".txt"}
MAX_CHARS = 30_000  # long files are cut so one read can't flood the model's context

TOOLS = [
    {
        "type": "function",
        "name": "list_documents",
        "description": (
            "List the available documents with their title. "
            "Call this first to find which documents may answer the question."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "read_document",
        "description": "Read the full text of one document returned by list_documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Document name as returned by list_documents, e.g. faq.md",
                }
            },
            "required": ["name"],
        },
    },
]


def _documents():
    return sorted(
        p for p in DOCS_DIR.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS
    )


def _name(path):
    return path.relative_to(DOCS_DIR).as_posix()


def list_documents():
    docs = []
    for path in _documents():
        text = path.read_text(errors="replace")
        first_line = next((line for line in text.splitlines() if line.strip()), "")
        title = first_line.lstrip("# ").strip() or path.stem
        docs.append({"name": _name(path), "title": title})
    return {"documents": docs}


def read_document(name):
    # Only files listed by list_documents can be read, so "../.env" and friends fail.
    # Matching ignores case and extension: voice models sometimes say "faq" for "faq.md".
    wanted = name.strip().lower()
    for path in _documents():
        doc = _name(path)
        if wanted in (doc.lower(), doc.rsplit(".", 1)[0].lower()):
            text = path.read_text(errors="replace")
            if len(text) > MAX_CHARS:
                text = text[:MAX_CHARS] + "\n\n[document truncated]"
            return {"name": doc, "content": text}
    return {"error": f"No document named {name!r}. Call list_documents to see the names."}


FUNCTIONS = {"list_documents": list_documents, "read_document": read_document}


def run_tool(name, arguments):
    """Run a tool call from the model. Returns the result as a JSON string."""
    try:
        result = FUNCTIONS[name](**json.loads(arguments or "{}"))
    except Exception as e:  # report errors to the model instead of crashing the call
        result = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(result, ensure_ascii=False)

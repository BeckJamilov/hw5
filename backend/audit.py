"""Append-only audit trail for the agent team.

File: output/audit_trail.json, one JSON array of event objects. Events:
    run_start / run_end        -> a whole ticket run (Boss plus everyone it involved)
    agent_start / agent_end    -> one agent's turn: prompt, structured output, token usage
    agent_step                 -> one model response: text and tool calls it asked for
    delegation                 -> agent A handed a task to agent B (or was blocked)
    tool_call / tool_result    -> every MCP tool call with arguments and the returned result
    tool_error / limit_reached / error

Append-only: earlier bytes are never rewritten. A new entry replaces only the closing "]"
of the array and adds a new "]", so the file stays valid JSON across runs. Secrets are never
logged: API keys and long digit runs are masked, and long text is shortened.
"""

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
MAX_TEXT = 4000  # characters kept from any logged string (tool results can be long)

_lock = threading.Lock()
logger = logging.getLogger("campus_customs.audit")

_SECRET = re.compile(r"(?i)\b(api[_ -]?key|token|secret|password|authorization)\b(\s*[:=]\s*)\S+")
_KEYLIKE = re.compile(r"\b(sk|pk)-[A-Za-z0-9_-]{12,}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def redact(value: Any, limit: int = MAX_TEXT) -> Any:
    """Mask secret-looking text and shorten strings; walks dicts and lists."""
    if isinstance(value, str):
        text = _SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}[removed]", value)
        text = _KEYLIKE.sub("[key removed]", text)
        text = _CARD.sub("[number removed]", text)
        return text if len(text) <= limit else text[: limit - 1] + "…"
    if isinstance(value, dict):
        return {k: redact(v, limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, limit) for v in value]
    return value


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_events() -> list[dict[str, Any]]:
    """All audit events, oldest first (read under the same lock that guards writes)."""
    with _lock:
        if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
            return []
        return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def append_event(event: dict[str, Any]) -> None:
    """Append one event to the JSON array without touching earlier entries."""
    entry = json.dumps(redact({"time": _now(), **event}), ensure_ascii=False, default=str)
    with _lock:
        try:
            AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
                with open(AUDIT_PATH, "a", encoding="utf-8") as f:
                    f.write("[\n" + entry + "\n]\n")
                return
            with open(AUDIT_PATH, "r+b") as f:
                # Walk back from the end past whitespace to the closing "]".
                f.seek(0, 2)
                pos = f.tell()
                ch = b""
                while pos > 0:
                    pos -= 1
                    f.seek(pos)
                    ch = f.read(1)
                    if not ch.isspace():
                        break
                if ch != b"]":
                    # Never overwrite a file we don't understand; old records stay intact.
                    logger.error("Audit file does not end with ']'; entry not written")
                    return
                # "[" directly before "]" means an empty array: no comma needed.
                f.seek(0)
                empty = f.read(pos).strip() == b"["
                f.seek(pos)
                f.write(((("\n" if empty else ",\n") + entry + "\n]\n")).encode("utf-8"))
        except OSError:
            logger.exception("Could not write audit entry")

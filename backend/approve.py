"""Human approval desk: the only way a payment or purchase can happen.

Agents can only create approval requests. A person uses this script to review them, then
approve, reject, or execute. It talks to the same campus-customs MCP server, started in the
"human" role, which is the only role where decide_approval_request and
execute_approved_request exist. Every decision is also written to output/audit_trail.json.

    .venv/Scripts/python.exe backend/approve.py list
    .venv/Scripts/python.exe backend/approve.py approve 3 --by "Jane Manager" --note "OK"
    .venv/Scripts/python.exe backend/approve.py reject 3 --by "Jane Manager" --note "Wait"
    .venv/Scripts/python.exe backend/approve.py execute 3 --by "Jane Manager"
"""

import argparse
import asyncio
import json
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from agents import PROJECT_ROOT, SERVER_PATH, WORKING_DB
from audit import append_event


def human_client() -> Client:
    env = {k: v for k, v in os.environ.items() if k != "PORTKEY_API_KEY"}
    env.update(CAMPUS_CUSTOMS_DB=os.getenv("CAMPUS_CUSTOMS_DB", WORKING_DB), CAMPUS_CUSTOMS_ROLE="human")
    return Client(StdioTransport(sys.executable, [str(SERVER_PATH)], env=env, cwd=str(PROJECT_ROOT)))


async def call(tool: str, args: dict) -> dict:
    async with human_client() as client:
        result = await client.call_tool(tool, args)
        return result.structured_content or {"text": str(result.content)}


def confirm(message: str) -> bool:
    return input(f"{message}\nType YES to continue: ").strip() == "YES"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Human approval desk for Campus Customs.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show pending and approved requests")
    for name in ("approve", "reject", "execute"):
        p = sub.add_parser(name)
        p.add_argument("request_id", type=int)
        p.add_argument("--by", required=True, help="your name (must be a person, not an agent)")
        if name != "execute":
            p.add_argument("--note", default="")
    args = parser.parse_args()

    if args.command == "list":
        for status in ("pending_human_approval", "approved"):
            data = await call("list_approval_requests", {"status": status})
            print(f"\n{status}:")
            print(json.dumps(data["approval_requests"], indent=2) if data["approval_requests"] else "  none")
        print("\n" + json.dumps({k: v for k, v in (await call("get_cash_position", {})).items()
                                 if k in ("total_cash", "committed_to_open_requests", "available_cash")}, indent=2))
        return

    if args.command == "execute":
        if not confirm(f"Execute request {args.request_id}? This records a payment and lowers cash."):
            print("Cancelled.")
            return
        tool, tool_args = "execute_approved_request", {"request_id": args.request_id, "executed_by": args.by}
    else:
        if not confirm(f"{args.command.title()} request {args.request_id} as {args.by}?"):
            print("Cancelled.")
            return
        tool = "decide_approval_request"
        tool_args = {"request_id": args.request_id, "decision": args.command, "approver": args.by, "note": args.note}

    base = {"event": "human_action", "agent": None, "human": args.by, "tool": tool, "args": tool_args}
    try:
        result = await call(tool, tool_args)
    except Exception as exc:
        append_event({**base, "status": "refused", "error": str(exc)})
        print(f"Refused: {exc}")
        return
    append_event({**base, "status": "ok", "result": result})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

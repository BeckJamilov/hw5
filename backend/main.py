"""Campus Customs desk API (Problem 7).

FastAPI backend for the future React dashboard (http://localhost:5173). It has no database
code of its own: shop data is read and changed only through the campus-customs MCP server
(mcp_server/server.py), and tickets are worked only by the five-agent team (agents.py).

- Dashboard reads, approvals, and execution use one MCP connection in the "human" role. That
  role is the only one with decide_approval_request / execute_approved_request.
- Agent runs use the team's own MCP connection in the "agent" role, which has no approve or
  pay tools, so agents can never approve or pay their own requests.
- Reset is the one file operation: it replaces data/campus_customs_new.db with a fresh copy of
  data/campus_customs.db. The original is only read, never written.

Run from the project root with the project's .venv:
    .venv/Scripts/python.exe -m uvicorn main:app --app-dir backend --port 8000
"""

import asyncio
import hashlib
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from agents import PROJECT_ROOT, WORKING_DB, AgentTeam, build_mcp_toolset
from approve import human_client
from audit import append_event, new_run_id, read_events

ORIGINAL_DB_PATH = PROJECT_ROOT / os.getenv("CAMPUS_CUSTOMS_ORIGINAL_DB", "data/campus_customs.db")
WORKING_DB_PATH = PROJECT_ROOT / os.getenv("CAMPUS_CUSTOMS_DB", WORKING_DB)
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer service", "customer_service"}
MAX_EVENTS = 500  # most events one /api/events call returns


# ---------------------------------------------------------------- request bodies


class ApproveBody(BaseModel):
    approver: str = Field(min_length=1, max_length=100, description="Name of the person clicking approve")
    note: str = Field(default="", max_length=500)
    confirm: bool = Field(description="Must be true: the human confirmed the payment or purchase")


class RejectBody(BaseModel):
    approver: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=500)


class ResetBody(BaseModel):
    confirm: str = Field(description='Must be exactly "RESET"')


# ---------------------------------------------------------------- app state


class Desk:
    """Shared state: the human MCP connection, the agent team, and run bookkeeping."""

    def __init__(self):
        self.client = None  # fastmcp Client, role "human"
        self.team: AgentTeam | None = None  # built on first run (needs PORTKEY_API_KEY)
        self.team_factory = lambda: AgentTeam(toolset=build_mcp_toolset(str(WORKING_DB_PATH)))
        self.write_lock = asyncio.Lock()  # approvals, rejections, and reset happen one at a time
        self.runs: dict[str, dict[str, Any]] = {}
        self.active_run: str | None = None
        self.tasks: set[asyncio.Task] = set()


desk = Desk()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.environ["CAMPUS_CUSTOMS_DB"] = str(WORKING_DB_PATH)  # human_client() reads this
    async with human_client() as client:
        desk.client = client
        yield
    desk.client = None


app = FastAPI(title="Campus Customs Desk API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


async def mcp(tool: str, args: dict | None = None) -> dict:
    """Call one campus-customs MCP tool. A tool refusal becomes a clear HTTP error."""
    try:
        result = await desk.client.call_tool(tool, args or {})
    except ToolError as exc:
        message = str(exc).split(": ", 1)[-1] if str(exc).startswith("Error calling tool") else str(exc)
        status = 404 if "not found" in message.lower() else 409
        raise HTTPException(status_code=status, detail=message) from exc
    return result.structured_content or {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_agent_name(name: str) -> bool:
    name = name.strip().lower()
    return name in AGENT_NAMES or "agent" in name


async def find_request(request_id: int) -> dict:
    for req in (await mcp("list_approval_requests"))["approval_requests"]:
        if req["id"] == request_id:
            return req
    raise HTTPException(status_code=404, detail=f"Approval request {request_id} not found")


async def sync_ticket_status(ticket_id: int | None, human: str, outcome: str) -> str | None:
    """Keep ticket status accurate after a human acts. A ticket waiting for approval becomes
    'resolved' only when none of its requests still need a human. If the last open request was
    rejected, it goes to 'needs_more_info' so Boss revisits it."""
    if ticket_id is None:
        return None
    details = await mcp("get_ticket_details", {"ticket_id": ticket_id})
    status = details["ticket"]["status"]
    still_open = [r for r in details["approval_requests"] if r["status"] in ("pending_human_approval", "approved")]
    if status != "waiting_for_human_approval" or still_open:
        return status
    any_rejected = any(r["status"] == "rejected" for r in details["approval_requests"])
    decision = "needs_more_info" if outcome == "rejected" or any_rejected else "resolved"
    summary = (
        f"All approval requests for ticket {ticket_id} were handled by {human}; "
        + ("at least one was rejected, so Boss should revisit." if decision == "needs_more_info"
           else "every approved payment/purchase was executed.")
    )
    await mcp("record_ticket_decision", {"ticket_id": ticket_id, "decision": decision,
                                         "summary": summary, "decided_by": human})
    return decision


# ---------------------------------------------------------------- routes: read


@app.get("/api/health")
async def health() -> dict:
    return {"ok": desk.client is not None, "working_db": WORKING_DB_PATH.name, "active_run": desk.active_run}


@app.get("/api/tickets")
async def list_tickets() -> dict:
    """All tickets with status, latest decision, approval counts, and draft count."""
    return await mcp("list_tickets")


@app.get("/api/tickets/{ticket_id}")
async def ticket_details(ticket_id: int) -> dict:
    """One ticket with linked lease/invoice, decisions, approval requests, and drafts."""
    return await mcp("get_ticket_details", {"ticket_id": ticket_id})


@app.get("/api/cash")
async def cash() -> dict:
    """Checking balance plus money promised to open requests and what is still available."""
    data = await mcp("get_cash_position")
    checking = next((a for a in data["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="Checking account not found")
    return {
        "today": data["today"],
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "committed_to_open_requests": data["committed_to_open_requests"],
        "available_cash": data["available_cash"],
        "cash_after_all_open_bills": data["cash_after_all_open_bills"],
    }


@app.get("/api/approvals")
async def approvals(status: str = Query("pending_human_approval"), ticket_id: int | None = None) -> dict:
    """Approval requests; pending ones by default. Use status=all for every request."""
    args: dict[str, Any] = {} if status == "all" else {"status": status}
    if ticket_id is not None:
        args["ticket_id"] = ticket_id
    return await mcp("list_approval_requests", args)


@app.get("/api/events")
async def events(limit: int = Query(50, ge=1, le=MAX_EVENTS), after: int = Query(-1, ge=-1),
                 ticket_id: int | None = None, run_id: str | None = None) -> dict:
    """Recent audit events, newest last. Each has an 'index'; pass after=<last index> to poll
    for only new events."""
    all_events = read_events()
    rows = [{"index": i, **e} for i, e in enumerate(all_events) if i > after]
    if ticket_id is not None:
        rows = [e for e in rows if e.get("ticket_id") == ticket_id]
    if run_id:
        rows = [e for e in rows if e.get("run_id") == run_id]
    return {"total": len(all_events), "events": rows[-limit:]}


@app.get("/api/runs")
async def runs() -> dict:
    """Agent runs started through this API (newest first) and the run in progress, if any."""
    return {"active_run": desk.active_run,
            "runs": sorted(desk.runs.values(), key=lambda r: r["started_at"], reverse=True)}


@app.get("/api/runs/{run_id}")
async def run_status(run_id: str) -> dict:
    if run_id not in desk.runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return desk.runs[run_id]


# ---------------------------------------------------------------- routes: actions


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> dict:
    """Start the agent team on one ticket in the background. One run at a time, so cash checks
    see every earlier request. Follow progress with /api/runs/{run_id} and /api/events."""
    await mcp("get_ticket_details", {"ticket_id": ticket_id})  # 404 if the ticket doesn't exist
    if desk.active_run or desk.write_lock.locked():
        raise HTTPException(status_code=409, detail="Another run or a human action is in progress; try again shortly")
    if desk.team is None:
        try:
            desk.team = desk.team_factory()
        except RuntimeError as exc:  # e.g. PORTKEY_API_KEY missing
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    run_id = new_run_id()
    desk.runs[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running",
                         "started_at": now(), "finished_at": None, "decision": None, "error": None}
    desk.active_run = run_id

    async def work():
        info = desk.runs[run_id]
        try:
            decision = await desk.team.handle_ticket(ticket_id, run_id=run_id)
            info["status"] = "finished" if decision else "stopped_by_limit"
            info["decision"] = decision.model_dump() if decision else None
        except Exception as exc:  # the audit trail has the details
            info["status"], info["error"] = "error", f"{type(exc).__name__}: {exc}"
        finally:
            info["finished_at"] = now()
            desk.active_run = None

    task = asyncio.create_task(work())
    desk.tasks.add(task)
    task.add_done_callback(desk.tasks.discard)
    return desk.runs[run_id]


@app.post("/api/approvals/{request_id}/approve")
async def approve_and_execute(request_id: int, body: ApproveBody) -> dict:
    """The ONLY route that moves money. A human approves a pending request and it is executed
    right away. Before approving it checks: confirmation, a human approver, pending status
    (no duplicates), enough cash, and the vendor/invoice rules."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true")
    approver = body.approver.strip()
    if is_agent_name(approver):
        raise HTTPException(status_code=403, detail="Only a human can approve; agents can't approve requests")
    if desk.active_run:
        raise HTTPException(status_code=409, detail="Wait for the agent run to finish before approving")

    async with desk.write_lock:
        req = await find_request(request_id)
        if req["status"] != "pending_human_approval":
            raise HTTPException(status_code=409, detail=f"Request {request_id} is '{req['status']}', not pending; "
                                                         "it can't be approved or paid again")
        if approver.lower() == req["requested_by"].strip().lower():
            raise HTTPException(status_code=403, detail="A requester can't approve their own request")

        # Cash: the checking balance must cover this request plus anything already approved but unpaid.
        cash_info = await cash()
        approved_unpaid = sum(r["amount"] for r in (await mcp("list_approval_requests", {"status": "approved"}))
                              ["approval_requests"])
        if cash_info["balance"] - approved_unpaid < req["amount"]:
            raise HTTPException(status_code=409, detail=(
                f"Not enough cash: ${req['amount']:,.2f} requested, ${cash_info['balance'] - approved_unpaid:,.2f} "
                "available in checking. Cash can't go negative."))
        if req["kind"] == "invoice_payment":
            open_ids = {i["id"] for i in (await mcp("list_open_invoices"))["open_invoices"]}
            if req["ref_id"] not in open_ids:
                raise HTTPException(status_code=409, detail=f"Invoice {req['ref_id']} is not open; paying it would be a duplicate")
        if req["kind"] == "purchase":
            vendor = next((v for v in (await mcp("list_vendors"))["vendors"] if v["id"] == req["ref_id"]), None)
            if vendor is None or not vendor["can_ship_now"]:
                blockers = [i["id"] for i in (vendor or {}).get("open_invoices", [])]
                raise HTTPException(status_code=409, detail=f"Vendor can't ship while invoices {blockers} are open; pay them first")

        base = {"event": "human_action", "agent": None, "human": approver, "request_id": request_id,
                "ticket_id": req["ticket_id"]}
        decided = await mcp("decide_approval_request", {"request_id": request_id, "decision": "approve",
                                                        "approver": approver, "note": body.note})
        append_event({**base, "action": "approve", "status": "ok", "result": decided})
        try:
            executed = await mcp("execute_approved_request", {"request_id": request_id, "executed_by": approver})
        except HTTPException as exc:
            append_event({**base, "action": "execute", "status": "refused", "error": exc.detail})
            raise HTTPException(status_code=409, detail=f"Approved but not executed: {exc.detail}") from exc
        append_event({**base, "action": "execute", "status": "ok", "result": executed})
        ticket_status = await sync_ticket_status(req["ticket_id"], approver, "executed")
        return {"request": await find_request(request_id), **executed, "ticket_status": ticket_status}


@app.post("/api/approvals/{request_id}/reject")
async def reject(request_id: int, body: RejectBody) -> dict:
    """A human rejects a pending request. No money moves."""
    approver = body.approver.strip()
    if is_agent_name(approver):
        raise HTTPException(status_code=403, detail="Only a human can reject requests")
    if desk.active_run:
        raise HTTPException(status_code=409, detail="Wait for the agent run to finish before rejecting")
    async with desk.write_lock:
        req = await find_request(request_id)
        if req["status"] != "pending_human_approval":
            raise HTTPException(status_code=409, detail=f"Request {request_id} is '{req['status']}', not pending")
        result = await mcp("decide_approval_request", {"request_id": request_id, "decision": "reject",
                                                       "approver": approver, "note": body.note})
        append_event({"event": "human_action", "agent": None, "human": approver, "request_id": request_id,
                      "ticket_id": req["ticket_id"], "action": "reject", "status": "ok", "result": result})
        ticket_status = await sync_ticket_status(req["ticket_id"], approver, "rejected")
        return {**result, "ticket_status": ticket_status}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@app.post("/api/reset")
async def reset(body: ResetBody) -> dict:
    """Replace the working database with a fresh copy of the original. The original file is
    only read, and its checksum is checked before and after the copy."""
    if body.confirm != "RESET":
        raise HTTPException(status_code=400, detail='Send {"confirm": "RESET"} to reset the working database')
    if WORKING_DB_PATH.resolve() == ORIGINAL_DB_PATH.resolve():
        raise HTTPException(status_code=500, detail="Working and original database paths are the same; refusing")
    if not ORIGINAL_DB_PATH.exists():
        raise HTTPException(status_code=500, detail="Original database not found")
    if desk.active_run:
        raise HTTPException(status_code=409, detail="An agent run is in progress; reset after it finishes")

    async with desk.write_lock:
        before = sha256(ORIGINAL_DB_PATH)
        tmp = WORKING_DB_PATH.with_suffix(".db.resetting")
        shutil.copyfile(ORIGINAL_DB_PATH, tmp)  # read the original, write a temp copy
        os.replace(tmp, WORKING_DB_PATH)  # swap in one step; only campus_customs_new.db changes
        if sha256(ORIGINAL_DB_PATH) != before:
            raise HTTPException(status_code=500, detail="Original database changed during reset")
        desk.runs.clear()
        append_event({"event": "reset", "agent": None, "detail": f"{WORKING_DB_PATH.name} replaced with a copy of {ORIGINAL_DB_PATH.name}"})
        return {"reset": True, "working_db": WORKING_DB_PATH.name, "original_unchanged": True,
                "cash": await cash(), "tickets": (await mcp("list_tickets"))["tickets"]}

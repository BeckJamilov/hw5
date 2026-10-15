"""Campus Customs MCP server.

The only way agents read or change shop data. Backed by the working database
data/campus_customs_new.db (never the original campus_customs.db).

Tool groups
- Ticket checks (Problem 3, read-only): check_customer_order, check_rent_notice,
  check_bulk_hoodie_order.
- Lookups (read-only): tickets, inventory, vendors, invoices, leases, cash, discounts,
  approval requests, message drafts.
- Proposals (write, but no money moves): request_invoice_payment, request_rent_payment,
  request_purchase, save_customer_message_draft, record_ticket_decision.
- Human-only (registered only when CAMPUS_CUSTOMS_ROLE=human): decide_approval_request,
  execute_approved_request. Agents connect with role "agent" and never see these tools.

Safety rules enforced here, not just in prompts
- No payment or purchase happens without a human approval recorded by a human.
- Cash can never go negative (checked at request time, at execution time, and by a
  database trigger).
- A vendor with open (unpaid) invoices can't ship new products, so purchases from it
  can't be executed.
- There is no email/send tool. Customer messages are saved as drafts only.
"""

import os
import sqlite3
from calendar import monthrange
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# .mcp.json / the agent backend set CAMPUS_CUSTOMS_DB; default is the working copy, never the original.
DB_PATH = PROJECT_ROOT / os.getenv("CAMPUS_CUSTOMS_DB", "data/campus_customs_new.db")
# "agent" (default, safest) or "human". Human-only tools are registered only for "human".
ROLE = os.getenv("CAMPUS_CUSTOMS_ROLE", "agent").strip().lower()

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer service", "customer_service"}
TICKET_DECISIONS = {"waiting_for_human_approval", "resolved", "needs_more_info", "declined"}
PENDING = "pending_human_approval"
# Requests that still hold cash (not yet rejected, cancelled, or executed).
COMMITTED_STATUSES = (PENDING, "approved")
MAX_TEXT = 2000  # longest free-text field we accept from an agent

mcp = FastMCP("campus-customs")

SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice_payment | rent_payment | purchase
    ticket_id INTEGER,
    ref_id INTEGER,                  -- invoice id / lease id / vendor id (purchase)
    sku TEXT,
    size TEXT,
    qty INTEGER,
    unit_cost REAL,
    amount REAL NOT NULL,
    period_due TEXT,                 -- rent due date this request pays
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending_human_approval | approved | rejected | executed
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    executed_by TEXT,
    executed_at TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES approval_requests(id),
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    amount REAL NOT NULL,
    expected_date TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(id),
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    prepared_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- always draft_not_sent; nothing here sends email
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_decisions (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    decision TEXT NOT NULL,
    summary TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS cash_never_negative
BEFORE UPDATE OF balance ON cash_accounts
WHEN NEW.balance < 0
BEGIN
    SELECT RAISE(ABORT, 'cash balance cannot go negative');
END;
"""


# ---------------------------------------------------------------- helpers


def connect(write: bool = False) -> sqlite3.Connection:
    """Open the working database; read-only unless a tool needs to write."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # After a reset (fresh copy of the original), add the workflow tables back first.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'cash_never_negative'").fetchone() is None:
        conn.close()
        init_schema()
        return connect(write)
    return conn


def init_schema() -> None:
    """Add the workflow tables and the cash trigger to the working database (idempotent)."""
    with closing(sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=rw", uri=True)) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def row_to_dict(row):
    return dict(row) if row is not None else None


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_today(conn) -> str:
    """Business date stored in desk.date_today."""
    return conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def get_ticket_row(conn, ticket_id: int) -> dict:
    if not isinstance(ticket_id, int) or ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")
    ticket = row_to_dict(conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} not found")
    return ticket


def get_ticket(conn, ticket_id: int, expected_type: str) -> dict:
    """Load a ticket and confirm it is the type this tool handles."""
    ticket = get_ticket_row(conn, ticket_id)
    if ticket["type"] != expected_type:
        raise ValueError(
            f"Ticket {ticket_id} is type '{ticket['type']}', expected '{expected_type}'"
        )
    return ticket


def days_between(start: str, end: str) -> int:
    """Whole days from start to end (ISO dates)."""
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def add_days(day: str, n: int) -> str:
    return date.fromordinal(date.fromisoformat(day[:10]).toordinal() + n).isoformat()


def add_one_month(day: str) -> str:
    d = date.fromisoformat(day[:10])
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, monthrange(year, month)[1])).isoformat()


def payments_for(conn, kind: str, ref_id) -> list[dict]:
    """Payments recorded against an invoice ('invoice') or lease ('rent')."""
    if ref_id is None:
        return []
    rows = conn.execute(
        "SELECT * FROM payments WHERE kind = ? AND ref_id = ? ORDER BY paid_at", (kind, ref_id)
    ).fetchall()
    return [dict(r) for r in rows]


def clean_text(value: str, field: str, limit: int = MAX_TEXT) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    if len(value) > limit:
        raise ValueError(f"{field} is too long (max {limit} characters)")
    return value


def cash_summary(conn) -> dict:
    """Cash on hand, cash already promised to open requests, and what is left."""
    accounts = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts")]
    balance = sum(a["balance"] for a in accounts)
    committed = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS s FROM approval_requests "
        f"WHERE status IN ({','.join('?' * len(COMMITTED_STATUSES))})",
        COMMITTED_STATUSES,
    ).fetchone()["s"]
    return {
        "cash_accounts": accounts,
        "total_cash": balance,
        "committed_to_open_requests": committed,
        "available_cash": balance - committed,
    }


def open_invoices_for_vendor(conn, vendor_id: int, today: str) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
            (vendor_id,),
        )
    ]
    for inv in rows:
        inv["days_overdue"] = max(0, days_between(inv["due_date"], today))
    return rows


def vendor_with_status(conn, vendor: dict, today: str) -> dict:
    """Add open invoices and the shop rule result (can_ship_now) to a vendor row."""
    open_invoices = open_invoices_for_vendor(conn, vendor["id"], today)
    vendor["open_invoices"] = open_invoices
    vendor["open_invoice_total"] = sum(inv["amount"] for inv in open_invoices)
    vendor["can_ship_now"] = not open_invoices
    return vendor


def ensure_cash_available(conn, amount: float) -> dict:
    """Reject a new request that would push promised spending past the cash we have."""
    cash = cash_summary(conn)
    if amount > cash["available_cash"] + 1e-9:
        raise ValueError(
            f"Not enough cash: request is ${amount:,.2f} but only ${cash['available_cash']:,.2f} "
            f"is available after ${cash['committed_to_open_requests']:,.2f} already promised to "
            "open requests. Cash can never go negative."
        )
    return cash


def insert_request(conn, **fields) -> dict:
    fields.update(status=PENDING, created_at=now())
    cols = ", ".join(fields)
    cur = conn.execute(
        f"INSERT INTO approval_requests ({cols}) VALUES ({','.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    conn.commit()
    return row_to_dict(
        conn.execute("SELECT * FROM approval_requests WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


def is_agent_name(name: str) -> bool:
    return name.strip().lower() in AGENT_NAMES or "agent" in name.strip().lower()


# ------------------------------------------------- Problem 3 ticket checks


@mcp.tool()
def check_customer_order(ticket_id: int = 101) -> dict:
    """Ticket 101: check a customer order against inventory, the linked unpaid
    vendor invoice, and the vendor's lead time. Read-only."""
    with closing(connect()) as conn:
        today = get_today(conn)
        ticket = get_ticket(conn, ticket_id, "customer_order")

        stock = row_to_dict(
            conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                (ticket["sku"], ticket["size"]),
            ).fetchone()
        )
        other_sizes = [
            dict(r)
            for r in conn.execute(
                "SELECT size, qty, location FROM inventory WHERE sku = ? AND size != ?",
                (ticket["sku"], ticket["size"]),
            )
        ]
        pricing = row_to_dict(
            conn.execute("SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)).fetchone()
        )

        invoice = vendor = None
        if ticket["invoice_id"] is not None:
            invoice = row_to_dict(
                conn.execute(
                    "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
                ).fetchone()
            )
        if invoice is not None:
            vendor = row_to_dict(
                conn.execute(
                    "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)
                ).fetchone()
            )
            invoice["days_overdue"] = max(0, days_between(invoice["due_date"], today))
            invoice["payments"] = payments_for(conn, "invoice", invoice["id"])

        qty_on_hand = stock["qty"] if stock else 0
        return {
            "today": today,
            "ticket": ticket,
            "requested_item": stock,
            "qty_requested": ticket["qty"],
            "qty_on_hand": qty_on_hand,
            "can_fill_from_stock": qty_on_hand >= (ticket["qty"] or 0),
            "other_sizes_same_sku": other_sizes,
            "pricing": pricing,
            "linked_invoice": invoice,
            "vendor": vendor,
        }


@mcp.tool()
def check_rent_notice(ticket_id: int = 102) -> dict:
    """Ticket 102: check a rent notice against the lease (amount, due date),
    current cash balance, and any payments already recorded. Read-only."""
    with closing(connect()) as conn:
        today = get_today(conn)
        ticket = get_ticket(conn, ticket_id, "rent_notice")

        lease = None
        if ticket["lease_id"] is not None:
            lease = row_to_dict(
                conn.execute(
                    "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
                ).fetchone()
            )
        cash = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts")]
        total_cash = sum(a["balance"] for a in cash)

        result = {
            "today": today,
            "ticket": ticket,
            "lease": lease,
            "cash_accounts": cash,
            "total_cash": total_cash,
        }
        if lease is not None:
            result.update(
                {
                    "days_until_due": days_between(today, lease["next_due"]),
                    "landlord_matches_requester": lease["landlord"] == ticket["requester"],
                    "cash_after_rent": total_cash - lease["monthly_rent"],
                    "related_payments": payments_for(conn, "rent", lease["id"]),
                }
            )
        return result


@mcp.tool()
def check_bulk_hoodie_order(ticket_id: int = 103) -> dict:
    """Ticket 103: check a bulk order / discount request against stock,
    selling price, unit cost, and apparel vendor restocking options
    (including open invoices that block shipping). Read-only."""
    with closing(connect()) as conn:
        today = get_today(conn)
        ticket = get_ticket(conn, ticket_id, "price_override")

        stock = row_to_dict(
            conn.execute(
                "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                (ticket["sku"], ticket["size"]),
            ).fetchone()
        )
        all_sizes = [
            dict(r)
            for r in conn.execute(
                "SELECT size, qty, location FROM inventory WHERE sku = ?", (ticket["sku"],)
            )
        ]
        pricing = row_to_dict(
            conn.execute("SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],)).fetchone()
        )
        # Only vendors whose specialty is apparel can restock hoodies.
        # Shop rule: a vendor cannot ship new products while it has open invoices.
        vendors = [
            vendor_with_status(conn, dict(r), today)
            for r in conn.execute(
                "SELECT * FROM vendors WHERE LOWER(specialty) LIKE '%apparel%' "
                "ORDER BY lead_days"
            )
        ]

        qty = ticket["qty"] or 0
        qty_on_hand = stock["qty"] if stock else 0
        result = {
            "today": today,
            "ticket": ticket,
            "requested_item": stock,
            "qty_requested": qty,
            "qty_on_hand": qty_on_hand,
            "shortfall": max(0, qty - qty_on_hand),
            "all_sizes_same_sku": all_sizes,
            "pricing": pricing,
            "restocking_options": vendors,
        }
        if pricing is not None:
            result.update(
                {
                    "margin_per_unit_at_list": pricing["list_price"] - pricing["unit_cost"],
                    "order_revenue_at_list": pricing["list_price"] * qty,
                    "order_cost": pricing["unit_cost"] * qty,
                    "max_discount_pct_before_loss": round(
                        100 * (1 - pricing["unit_cost"] / pricing["list_price"]), 1
                    ),
                }
            )
        return result


# ------------------------------------------------------- read-only lookups


@mcp.tool()
def list_open_tickets() -> dict:
    """List every ticket whose status is not resolved/declined, with today's business date. Read-only."""
    with closing(connect()) as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM tickets WHERE status NOT IN ('resolved', 'declined') ORDER BY id"
            )
        ]
        return {"today": get_today(conn), "open_tickets": rows}


@mcp.tool()
def list_tickets() -> dict:
    """All tickets (open and closed) with status, latest decision, and counts of approval
    requests by status and saved drafts. Read-only."""
    with closing(connect()) as conn:
        tickets = [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY id")]
        for t in tickets:
            counts = {r["status"]: r["n"] for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM approval_requests WHERE ticket_id = ? GROUP BY status",
                (t["id"],))}
            t["approval_counts"] = counts
            t["needs_human"] = counts.get(PENDING, 0) + counts.get("approved", 0) > 0
            t["draft_count"] = conn.execute(
                "SELECT COUNT(*) AS n FROM message_drafts WHERE ticket_id = ?", (t["id"],)).fetchone()["n"]
            t["latest_decision"] = row_to_dict(conn.execute(
                "SELECT * FROM ticket_decisions WHERE ticket_id = ? ORDER BY id DESC LIMIT 1", (t["id"],)).fetchone())
        return {"today": get_today(conn), "tickets": tickets}


@mcp.tool()
def get_ticket_details(ticket_id: int) -> dict:
    """One ticket with its linked lease/invoice and any decisions or drafts already recorded. Read-only."""
    with closing(connect()) as conn:
        ticket = get_ticket_row(conn, ticket_id)
        lease = invoice = None
        if ticket["lease_id"] is not None:
            lease = row_to_dict(conn.execute("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)).fetchone())
        if ticket["invoice_id"] is not None:
            invoice = row_to_dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)).fetchone())
        return {
            "today": get_today(conn),
            "ticket": ticket,
            "linked_lease": lease,
            "linked_invoice": invoice,
            "decisions": [dict(r) for r in conn.execute(
                "SELECT * FROM ticket_decisions WHERE ticket_id = ? ORDER BY id", (ticket_id,))],
            "approval_requests": [dict(r) for r in conn.execute(
                "SELECT * FROM approval_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,))],
            "message_drafts": [dict(r) for r in conn.execute(
                "SELECT * FROM message_drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))],
        }


@mcp.tool()
def get_inventory(sku: str, size: str | None = None) -> dict:
    """Stock on hand for a SKU (optionally one size), plus its price and unit cost. Read-only."""
    sku = clean_text(sku, "sku", 50)
    with closing(connect()) as conn:
        if size:
            rows = conn.execute("SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku,)).fetchall()
        if not rows:
            raise ValueError(f"No inventory found for sku={sku!r} size={size!r}")
        pricing = row_to_dict(conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone())
        return {"items": [dict(r) for r in rows], "pricing": pricing}


@mcp.tool()
def list_vendors(specialty_contains: str | None = None) -> dict:
    """Vendors with lead time, open invoices, and can_ship_now (false if any invoice is open).
    Optionally filter by specialty text, e.g. 'apparel'. Read-only."""
    with closing(connect()) as conn:
        today = get_today(conn)
        if specialty_contains:
            rows = conn.execute(
                "SELECT * FROM vendors WHERE LOWER(specialty) LIKE ? ORDER BY lead_days",
                (f"%{specialty_contains.strip().lower()}%",),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        return {"today": today, "vendors": [vendor_with_status(conn, dict(r), today) for r in rows]}


@mcp.tool()
def list_open_invoices() -> dict:
    """All open (unpaid) vendor invoices with vendor name and days overdue. Read-only."""
    with closing(connect()) as conn:
        today = get_today(conn)
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                "WHERE i.status = 'open' ORDER BY i.due_date"
            )
        ]
        for inv in rows:
            inv["days_overdue"] = max(0, days_between(inv["due_date"], today))
            inv["payments"] = payments_for(conn, "invoice", inv["id"])
        return {"today": today, "open_invoices": rows, "total_open": sum(i["amount"] for i in rows)}


@mcp.tool()
def get_lease(lease_id: int) -> dict:
    """A lease with days until rent is due and rent payments already recorded. Read-only."""
    with closing(connect()) as conn:
        today = get_today(conn)
        lease = row_to_dict(conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone())
        if lease is None:
            raise ValueError(f"Lease {lease_id} not found")
        return {
            "today": today,
            "lease": lease,
            "days_until_due": days_between(today, lease["next_due"]),
            "rent_payments": payments_for(conn, "rent", lease_id),
        }


@mcp.tool()
def get_cash_position() -> dict:
    """Cash on hand, open invoices, upcoming rent, open approval requests, and available cash
    (cash minus money already promised to pending/approved requests). Read-only."""
    with closing(connect()) as conn:
        today = get_today(conn)
        cash = cash_summary(conn)
        invoices = [
            dict(r) for r in conn.execute("SELECT * FROM invoices WHERE status = 'open' ORDER BY due_date")
        ]
        leases = [dict(r) for r in conn.execute("SELECT * FROM leases ORDER BY next_due")]
        for lease in leases:
            lease["days_until_due"] = days_between(today, lease["next_due"])
        open_requests = [
            dict(r)
            for r in conn.execute(
                f"SELECT * FROM approval_requests WHERE status IN "
                f"({','.join('?' * len(COMMITTED_STATUSES))}) ORDER BY id",
                COMMITTED_STATUSES,
            )
        ]
        bills = sum(i["amount"] for i in invoices) + sum(l["monthly_rent"] for l in leases)
        return {
            "today": today,
            **cash,
            "open_invoices": invoices,
            "leases": leases,
            "open_approval_requests": open_requests,
            "cash_after_all_open_bills": cash["total_cash"] - bills,
        }


@mcp.tool()
def check_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Price, revenue, cost, and margin for an order of a SKU at a given discount percent.
    Shop pricing rule: the discounted price must stay above unit cost. Read-only."""
    if not isinstance(qty, int) or qty <= 0:
        raise ValueError("qty must be a positive integer")
    if not 0 <= discount_pct < 100:
        raise ValueError("discount_pct must be between 0 and 100")
    with closing(connect()) as conn:
        pricing = row_to_dict(conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone())
        if pricing is None:
            raise ValueError(f"No pricing for sku {sku!r}")
        unit_price = round(pricing["list_price"] * (1 - discount_pct / 100), 2)
        margin = round(unit_price - pricing["unit_cost"], 2)
        return {
            "pricing": pricing,
            "qty": qty,
            "discount_pct": discount_pct,
            "unit_price_after_discount": unit_price,
            "margin_per_unit": margin,
            "order_revenue": round(unit_price * qty, 2),
            "order_cost": round(pricing["unit_cost"] * qty, 2),
            "order_profit": round(margin * qty, 2),
            "above_cost": margin > 0,
            "max_discount_pct_before_loss": round(100 * (1 - pricing["unit_cost"] / pricing["list_price"]), 1),
        }


@mcp.tool()
def list_approval_requests(status: str | None = None, ticket_id: int | None = None) -> dict:
    """Payment/purchase requests and their human-approval status. Read-only."""
    sql, args = "SELECT * FROM approval_requests WHERE 1=1", []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if ticket_id is not None:
        sql += " AND ticket_id = ?"
        args.append(ticket_id)
    with closing(connect()) as conn:
        return {"approval_requests": [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]}


@mcp.tool()
def list_message_drafts(ticket_id: int | None = None) -> dict:
    """Customer message drafts (never sent). Read-only."""
    with closing(connect()) as conn:
        if ticket_id is None:
            rows = conn.execute("SELECT * FROM message_drafts ORDER BY id")
        else:
            rows = conn.execute("SELECT * FROM message_drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        return {"message_drafts": [dict(r) for r in rows]}


# ------------------------------------------- proposals (no money moves here)


@mcp.tool()
def request_invoice_payment(invoice_id: int, ticket_id: int, reason: str, requested_by: str) -> dict:
    """Prepare a payment of an open vendor invoice FOR HUMAN APPROVAL. Does not pay anything.
    The amount is always the invoice amount. Refused if the invoice isn't open, is already
    requested, or available cash can't cover it."""
    reason = clean_text(reason, "reason")
    requested_by = clean_text(requested_by, "requested_by", 50)
    with closing(connect(write=True)) as conn:
        get_ticket_row(conn, ticket_id)
        inv = row_to_dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone())
        if inv is None:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv["status"] != "open":
            raise ValueError(f"Invoice {invoice_id} is '{inv['status']}', not open; nothing to pay")
        if payments_for(conn, "invoice", invoice_id):
            raise ValueError(f"Invoice {invoice_id} already has a recorded payment")
        dup = conn.execute(
            "SELECT id FROM approval_requests WHERE kind = 'invoice_payment' AND ref_id = ? "
            f"AND status IN ({','.join('?' * len(COMMITTED_STATUSES))})",
            (invoice_id, *COMMITTED_STATUSES),
        ).fetchone()
        if dup:
            raise ValueError(f"Invoice {invoice_id} already has open approval request {dup['id']}")
        cash = ensure_cash_available(conn, inv["amount"])
        req = insert_request(
            conn, kind="invoice_payment", ticket_id=ticket_id, ref_id=invoice_id,
            amount=inv["amount"], reason=reason, requested_by=requested_by,
        )
        return {
            "approval_request": req,
            "available_cash_after_request": cash["available_cash"] - inv["amount"],
            "note": "Nothing has been paid. A human must approve and execute this request.",
        }


@mcp.tool()
def request_rent_payment(lease_id: int, ticket_id: int, amount: float, reason: str, requested_by: str) -> dict:
    """Prepare a rent payment FOR HUMAN APPROVAL. Does not pay anything. The amount must equal
    the lease's monthly_rent, and the same due date can't be requested or paid twice."""
    reason = clean_text(reason, "reason")
    requested_by = clean_text(requested_by, "requested_by", 50)
    with closing(connect(write=True)) as conn:
        ticket = get_ticket_row(conn, ticket_id)
        lease = row_to_dict(conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone())
        if lease is None:
            raise ValueError(f"Lease {lease_id} not found")
        if ticket["lease_id"] not in (None, lease_id):
            raise ValueError(f"Ticket {ticket_id} is linked to lease {ticket['lease_id']}, not {lease_id}")
        if abs(amount - lease["monthly_rent"]) > 0.005:
            raise ValueError(
                f"Amount ${amount:,.2f} does not match lease rent ${lease['monthly_rent']:,.2f}; "
                "only the lease amount can be paid"
            )
        dup = conn.execute(
            "SELECT id, status FROM approval_requests WHERE kind = 'rent_payment' AND ref_id = ? "
            "AND period_due = ? AND status IN ('pending_human_approval', 'approved', 'executed')",
            (lease_id, lease["next_due"]),
        ).fetchone()
        if dup:
            raise ValueError(
                f"Rent due {lease['next_due']} already has request {dup['id']} ({dup['status']})"
            )
        cash = ensure_cash_available(conn, lease["monthly_rent"])
        req = insert_request(
            conn, kind="rent_payment", ticket_id=ticket_id, ref_id=lease_id,
            amount=lease["monthly_rent"], period_due=lease["next_due"],
            reason=reason, requested_by=requested_by,
        )
        return {
            "approval_request": req,
            "available_cash_after_request": cash["available_cash"] - lease["monthly_rent"],
            "note": "Nothing has been paid. A human must approve and execute this request.",
        }


@mcp.tool()
def request_purchase(vendor_id: int, sku: str, size: str, qty: int, ticket_id: int,
                     reason: str, requested_by: str) -> dict:
    """Prepare a restock purchase FOR HUMAN APPROVAL. Does not buy anything. Cost is
    pricing.unit_cost x qty. The vendor's specialty must be apparel for clothing. If the vendor
    has open invoices, the request is saved but marked blocked: it can't be executed until
    those invoices are paid (shop rule)."""
    reason = clean_text(reason, "reason")
    requested_by = clean_text(requested_by, "requested_by", 50)
    if not isinstance(qty, int) or not 0 < qty <= 500:
        raise ValueError("qty must be an integer from 1 to 500")
    with closing(connect(write=True)) as conn:
        today = get_today(conn)
        get_ticket_row(conn, ticket_id)
        vendor = row_to_dict(conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone())
        if vendor is None:
            raise ValueError(f"Vendor {vendor_id} not found")
        item = conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        pricing = row_to_dict(conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone())
        if item is None or pricing is None:
            raise ValueError(f"Unknown product sku={sku!r} size={size!r}")
        if "apparel" not in vendor["specialty"].lower():
            raise ValueError(f"{vendor['name']} supplies '{vendor['specialty']}', not apparel")
        amount = round(pricing["unit_cost"] * qty, 2)
        cash = ensure_cash_available(conn, amount)
        vendor = vendor_with_status(conn, vendor, today)
        req = insert_request(
            conn, kind="purchase", ticket_id=ticket_id, ref_id=vendor_id, sku=sku, size=size,
            qty=qty, unit_cost=pricing["unit_cost"], amount=amount, reason=reason,
            requested_by=requested_by,
        )
        return {
            "approval_request": req,
            "vendor": vendor,
            "blocked_by_open_invoices": not vendor["can_ship_now"],
            "earliest_arrival_if_ordered_today": add_days(today, vendor["lead_days"]),
            "available_cash_after_request": cash["available_cash"] - amount,
            "note": "Nothing has been ordered. A human must approve and execute this request"
            + ("; the vendor's open invoices must be paid first." if not vendor["can_ship_now"] else "."),
        }


@mcp.tool()
def save_customer_message_draft(ticket_id: int, recipient: str, subject: str, body: str,
                                prepared_by: str) -> dict:
    """Save a customer message as a DRAFT for a human to review. Nothing is sent: this server
    has no email or messaging tool."""
    recipient = clean_text(recipient, "recipient", 100)
    subject = clean_text(subject, "subject", 200)
    body = clean_text(body, "body", 4000)
    prepared_by = clean_text(prepared_by, "prepared_by", 50)
    with closing(connect(write=True)) as conn:
        get_ticket_row(conn, ticket_id)
        cur = conn.execute(
            "INSERT INTO message_drafts (ticket_id, recipient, subject, body, prepared_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'draft_not_sent', ?)",
            (ticket_id, recipient, subject, body, prepared_by, now()),
        )
        conn.commit()
        draft = row_to_dict(conn.execute("SELECT * FROM message_drafts WHERE id = ?", (cur.lastrowid,)).fetchone())
        return {"draft": draft, "note": "Saved as a draft only. It has NOT been sent."}


@mcp.tool()
def record_ticket_decision(ticket_id: int, decision: str, summary: str, decided_by: str) -> dict:
    """Boss's final decision for a ticket. decision is one of: waiting_for_human_approval,
    resolved, needs_more_info, declined. Updates tickets.status. Does not move money."""
    if decision not in TICKET_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(TICKET_DECISIONS)}")
    summary = clean_text(summary, "summary")
    decided_by = clean_text(decided_by, "decided_by", 50)
    with closing(connect(write=True)) as conn:
        get_ticket_row(conn, ticket_id)
        if decision == "resolved":
            pending = conn.execute(
                "SELECT COUNT(*) AS n FROM approval_requests WHERE ticket_id = ? AND status IN (?, 'approved')",
                (ticket_id, PENDING),
            ).fetchone()["n"]
            if pending:
                raise ValueError(
                    f"Ticket {ticket_id} has {pending} approval request(s) still waiting on a human; "
                    "use waiting_for_human_approval"
                )
        cur = conn.execute(
            "INSERT INTO ticket_decisions (ticket_id, decision, summary, decided_by, created_at) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, decision, summary, decided_by, now()),
        )
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (decision, ticket_id))
        conn.commit()
        return {
            "decision": row_to_dict(conn.execute("SELECT * FROM ticket_decisions WHERE id = ?", (cur.lastrowid,)).fetchone()),
            "ticket": get_ticket_row(conn, ticket_id),
        }


# ------------------------------------------------------- human-only tools


def decide_approval_request(request_id: int, decision: str, approver: str, note: str = "") -> dict:
    """HUMAN ONLY. Approve or reject a pending payment/purchase request."""
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be 'approve' or 'reject'")
    approver = clean_text(approver, "approver", 100)
    if is_agent_name(approver):
        raise ValueError("Approver must be a human, not an agent")
    with closing(connect(write=True)) as conn:
        req = row_to_dict(conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone())
        if req is None:
            raise ValueError(f"Approval request {request_id} not found")
        if req["status"] != PENDING:
            raise ValueError(f"Request {request_id} is '{req['status']}', not pending")
        status = "approved" if decision == "approve" else "rejected"
        conn.execute(
            "UPDATE approval_requests SET status = ?, decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (status, approver, now(), note.strip()[:MAX_TEXT], request_id),
        )
        conn.commit()
        return {"approval_request": row_to_dict(conn.execute(
            "SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone())}


def execute_approved_request(request_id: int, executed_by: str, account: str = "checking") -> dict:
    """HUMAN ONLY. Carry out an approved request: record the payment, lower cash, and mark the
    invoice paid / move rent to next month / create the purchase order. Re-checks every rule."""
    executed_by = clean_text(executed_by, "executed_by", 100)
    if is_agent_name(executed_by):
        raise ValueError("Only a human can execute a payment or purchase")
    with closing(connect(write=True)) as conn:
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")  # one writer at a time; all-or-nothing
        try:
            today = get_today(conn)
            req = row_to_dict(conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone())
            if req is None:
                raise ValueError(f"Approval request {request_id} not found")
            if req["status"] != "approved" or not req["decided_by"] or is_agent_name(req["decided_by"]):
                raise ValueError(f"Request {request_id} is '{req['status']}'; it needs a human approval first")
            acct = row_to_dict(conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone())
            if acct is None:
                raise ValueError(f"Cash account {account!r} not found")
            if acct["balance"] < req["amount"]:
                raise ValueError(
                    f"Not enough cash in {account}: ${acct['balance']:,.2f} < ${req['amount']:,.2f}"
                )

            result: dict = {}
            if req["kind"] == "invoice_payment":
                inv = row_to_dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone())
                if inv is None or inv["status"] != "open" or abs(inv["amount"] - req["amount"]) > 0.005:
                    raise ValueError("Invoice is no longer open or its amount changed; not paid")
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (inv["id"],))
                pay_kind, pay_ref = "invoice", inv["id"]
            elif req["kind"] == "rent_payment":
                lease = row_to_dict(conn.execute("SELECT * FROM leases WHERE id = ?", (req["ref_id"],)).fetchone())
                if lease is None or lease["next_due"] != req["period_due"] or abs(lease["monthly_rent"] - req["amount"]) > 0.005:
                    raise ValueError("Lease due date or rent changed since the request; not paid")
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (add_one_month(lease["next_due"]), lease["id"]))
                pay_kind, pay_ref = "rent", lease["id"]
            elif req["kind"] == "purchase":
                vendor = vendor_with_status(conn, row_to_dict(conn.execute(
                    "SELECT * FROM vendors WHERE id = ?", (req["ref_id"],)).fetchone()), today)
                if not vendor["can_ship_now"]:
                    raise ValueError(
                        f"{vendor['name']} has open invoices "
                        f"{[i['id'] for i in vendor['open_invoices']]}; pay them before ordering"
                    )
                cur = conn.execute(
                    "INSERT INTO purchase_orders (request_id, vendor_id, sku, size, qty, unit_cost, amount, "
                    "expected_date, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ordered', ?)",
                    (req["id"], vendor["id"], req["sku"], req["size"], req["qty"], req["unit_cost"],
                     req["amount"], add_days(today, vendor["lead_days"]), now()),
                )
                pay_kind, pay_ref = "purchase", cur.lastrowid
                result["purchase_order_id"] = cur.lastrowid
            else:
                raise ValueError(f"Unknown request kind {req['kind']!r}")

            # The trigger also blocks a negative balance if anything above were wrong.
            conn.execute(
                "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                (req["amount"], today, account),
            )
            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (pay_kind, pay_ref, req["amount"], account, now(), req["decided_by"]),
            )
            conn.execute(
                "UPDATE approval_requests SET status = 'executed', executed_by = ?, executed_at = ?, payment_id = ? WHERE id = ?",
                (executed_by, now(), cur.lastrowid, request_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        result.update(
            payment=row_to_dict(conn.execute("SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)).fetchone()),
            cash_account=row_to_dict(conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()),
        )
        return result


def revise_customer_message_draft(draft_id: int, subject: str, body: str, revised_by: str) -> dict:
    """HUMAN ONLY. Correct a saved customer draft in place. It stays a draft on the board
    (status draft_not_sent); nothing is sent. Returns the text before and after."""
    subject = clean_text(subject, "subject", 200)
    body = clean_text(body, "body", 4000)
    revised_by = clean_text(revised_by, "revised_by", 100)
    if is_agent_name(revised_by):
        raise ValueError("Only a human can revise a draft")
    with closing(connect(write=True)) as conn:
        before = row_to_dict(conn.execute("SELECT * FROM message_drafts WHERE id = ?", (draft_id,)).fetchone())
        if before is None:
            raise ValueError(f"Draft {draft_id} not found")
        if before["status"] != "draft_not_sent":
            raise ValueError(f"Draft {draft_id} is '{before['status']}', not an unsent draft")
        prepared_by = before["prepared_by"].split(" (revised by")[0] + f" (revised by {revised_by})"
        conn.execute("UPDATE message_drafts SET subject = ?, body = ?, prepared_by = ? WHERE id = ?",
                     (subject, body, prepared_by, draft_id))
        conn.commit()
        after = row_to_dict(conn.execute("SELECT * FROM message_drafts WHERE id = ?", (draft_id,)).fetchone())
        return {"before": before, "after": after, "note": "Still a draft on the board. It has NOT been sent."}


if ROLE == "human":
    mcp.tool()(decide_approval_request)
    mcp.tool()(execute_approved_request)
    mcp.tool()(revise_customer_message_draft)


init_schema()

if __name__ == "__main__":
    mcp.run()

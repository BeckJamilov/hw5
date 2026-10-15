# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that is the **only** way the Campus Customs agents
read or change shop data. It started (Problem 3) with three read-only ticket tools. Problem 5
added lookups, safe proposal tools, and two human-only tools for approving and carrying out
payments.

## Database

- **File:** `data/campus_customs_new.db`, the working copy of the original `data/campus_customs.db`.
  The original is never opened.
- Read tools open the database in **SQLite read-only mode** (`mode=ro`). Only the write tools
  below open it read-write.
- "Today" is `desk.date_today` in the database, not the computer clock.
- On start-up the server adds four workflow tables if they don't exist yet (`approval_requests`,
  `purchase_orders`, `message_drafts`, `ticket_decisions`). It also adds the trigger
  `cash_never_negative`, which blocks any update that would make a cash balance negative.
  Existing shop tables and rows are not changed by start-up.

## Roles

The environment variable `CAMPUS_CUSTOMS_ROLE` decides which tools exist:

| Role | Who | Tools |
|---|---|---|
| `agent` (default) | The PydanticAI agents (`backend/agents.py`) and this vibe coder (`.mcp.json`) | All tools except the two human-only tools |
| `human` | A person using `backend/approve.py` | All tools, plus `decide_approval_request` and `execute_approved_request` |

Because the human-only tools are never registered in the agent role, an agent can't approve or
pay anything, even by mistake.

## Tools

### Ticket checks (read-only, Problem 3)

| Tool | Ticket | Tables read | What it returns |
|---|---|---|---|
| `check_customer_order` | 101 (customer order) | `desk`, `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `payments` | Requested item and size, qty on hand, whether stock can fill the order, other sizes, price, the linked vendor invoice (amount, due date, status, days overdue, payments made), and the vendor's lead time |
| `check_rent_notice` | 102 (rent notice) | `desk`, `tickets`, `leases`, `cash_accounts`, `payments` | Lease rent and next due date, days until due, whether the landlord matches the requester, cash balance, cash left after rent, and rent payments |
| `check_bulk_hoodie_order` | 103 (price override) | `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `invoices` | Requested vs. on-hand qty, shortfall, all sizes, list price, unit cost, margin, order revenue/cost at list, max discount before a loss, and restocking options: **only apparel vendors**, each with lead time, open invoices, and `can_ship_now` |

Each takes an optional `ticket_id` (default: its ticket) and checks that the ticket has the expected type.

### Lookups (read-only, Problem 5)

| Tool | Tables read | What it returns |
|---|---|---|
| `list_open_tickets` | `desk`, `tickets` | Tickets not yet resolved or declined |
| `list_tickets` | `desk`, `tickets`, `approval_requests`, `message_drafts`, `ticket_decisions` | All tickets (open and closed) with status, latest decision, approval counts by status, and draft count. Used by the API. |
| `get_ticket_details(ticket_id)` | `desk`, `tickets`, `leases`, `invoices`, `ticket_decisions`, `approval_requests`, `message_drafts` | One ticket with its linked lease/invoice and any work already recorded |
| `get_inventory(sku, size?)` | `inventory`, `pricing` | Stock for a SKU (or one size) with its price and cost |
| `list_vendors(specialty_contains?)` | `desk`, `vendors`, `invoices` | Vendors with lead time, open invoices, and `can_ship_now` |
| `list_open_invoices` | `desk`, `invoices`, `vendors`, `payments` | Unpaid invoices with vendor name and days overdue |
| `get_lease(lease_id)` | `desk`, `leases`, `payments` | Lease, days until rent is due, and rent already paid |
| `get_cash_position` | `desk`, `cash_accounts`, `invoices`, `leases`, `approval_requests` | Total cash, money promised to open requests, **available cash**, open bills, and cash after all open bills |
| `check_discount(sku, qty, discount_pct)` | `pricing` | Price after discount, margin per unit, order profit, `above_cost`, max discount before a loss |
| `list_approval_requests(status?, ticket_id?)` | `approval_requests` | Payment and purchase requests with their status |
| `list_message_drafts(ticket_id?)` | `message_drafts` | Saved customer drafts (never sent) |

### Proposals (write, but **no money moves**)

| Tool | Writes to | Rules checked by the server |
|---|---|---|
| `request_invoice_payment(invoice_id, ticket_id, reason, requested_by)` | `approval_requests` | Invoice must be open and unpaid with no open request. Amount = invoice amount. Must fit in available cash. |
| `request_rent_payment(lease_id, ticket_id, amount, reason, requested_by)` | `approval_requests` | Amount must equal `leases.monthly_rent`. No second request or payment for the same due date. Must fit in available cash. |
| `request_purchase(vendor_id, sku, size, qty, ticket_id, reason, requested_by)` | `approval_requests` | Vendor must supply apparel. Cost = `pricing.unit_cost` × qty. Must fit in available cash. Flagged `blocked_by_open_invoices` if the vendor has unpaid invoices. |
| `save_customer_message_draft(ticket_id, recipient, subject, body, prepared_by)` | `message_drafts` | Saved with status `draft_not_sent`. **There is no tool that sends email.** |
| `record_ticket_decision(ticket_id, decision, summary, decided_by)` | `ticket_decisions`, `tickets.status` | Decision is one of `waiting_for_human_approval`, `resolved`, `needs_more_info`, `declined`. `resolved` is refused while requests still wait on a human. |

All requests start as `pending_human_approval`.

### Human-only (role `human`)

| Tool | What it does |
|---|---|
| `decide_approval_request(request_id, decision, approver, note?)` | Approve or reject a pending request. The approver can't be an agent name. |
| `execute_approved_request(request_id, executed_by, account?)` | For an **approved** request, in one transaction: re-checks the amount, status, vendor block, and cash; records the payment (`approved_by` = the human approver); lowers cash; then marks the invoice `paid`, moves rent `next_due` forward one month, or creates a purchase order. It refuses anything that would make cash negative. |
| `revise_customer_message_draft(draft_id, subject, body, revised_by)` | Correct an unsent customer draft in place. The reviser can't be an agent name, and the draft stays `draft_not_sent`. |

## Shop rules enforced in the server

1. No payment or purchase without a recorded human approval.
2. Cash can never go negative: checked at request time (against available cash), at execution, and by the database trigger.
3. A vendor with open (unpaid) invoices can't ship new products, so its purchases can't be executed until those invoices are paid.
4. Only apparel vendors can restock apparel.
5. Only the amount on record is paid (invoice amount or lease rent), and never twice.
6. No emails are sent. Customer messages are drafts.

## Files

- `server.py`: the server and all tools
- `requirements.txt`: Python dependency (`fastmcp`)

## Setup and connection

```bash
.venv/Scripts/pip install -r mcp_server/requirements.txt
```

- **Vibe coder (Claude Code):** `.mcp.json` registers the server as `campus-customs` with
  `CAMPUS_CUSTOMS_DB=data/campus_customs_new.db` and `CAMPUS_CUSTOMS_ROLE=agent`. Claude Code
  loads `.mcp.json` servers when a session starts, so restart the session to see new tools.
- **Agent team:** `backend/agents.py` starts the same server over stdio in the `agent` role.
- **Humans:** `backend/approve.py` starts it in the `human` role to list, approve, reject, and execute requests.

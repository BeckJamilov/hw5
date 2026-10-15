# Campus Customs Database Harness

Source: `data/campus_customs.db` (original, unchanged). Working copy: `data/campus_customs_new.db`.

The "today" date in the database (`desk.date_today`) is **2026-08-31**.

---

## Tables and fields

### 1. `desk` (1 row)
| Field | Type | Notes |
|---|---|---|
| date_today | TEXT | Current business date: `2026-08-31` |
| notes | TEXT | Currently empty |

**Why it matters:** It is the single source of "today" for agents. They need it to decide whether bills are overdue or coming due soon.

### 2. `cash_accounts` (1 row)
| Field | Type | Notes |
|---|---|---|
| name | TEXT, PK | `checking` |
| balance | REAL | `3400.00` |
| date | TEXT | Balance as of `2026-08-31` |

**Why it matters:** This is the money available. Before an agent approves a payment, it has to confirm the account can cover it.

### 3. `tickets` (3 rows)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Ticket number |
| type | TEXT | `customer_order`, `rent_notice`, `price_override` |
| requester | TEXT | Who asked |
| subject | TEXT | Short title |
| sku | TEXT | Product (links to `inventory` / `pricing`) |
| size | TEXT | Product size |
| qty | INTEGER | Quantity requested |
| lease_id | INTEGER, FK → `leases.id` | For rent tickets |
| invoice_id | INTEGER, FK → `invoices.id` | For vendor bill tickets |
| status | TEXT | All three are `open` |
| notes | TEXT | Request details |
| created_at | TEXT | Timestamp |

**Why it matters:** This is the agents' work queue. Each ticket says what was asked and links to the other records needed to handle it.

### 4. `inventory` (10 rows)
| Field | Type | Notes |
|---|---|---|
| sku | TEXT, PK (with size) | Product code |
| name | TEXT | Product name |
| size | TEXT, PK (with sku) | S / M / L / XL / OS |
| qty | INTEGER | Units on hand |
| location | TEXT | Aisle |

**Why it matters:** Agents check this to see whether an order can be filled from current stock or needs a reprint.

### 5. `pricing` (4 rows)
| Field | Type | Notes |
|---|---|---|
| sku | TEXT, PK | Product code |
| unit_cost | REAL | What the shop pays |
| list_price | REAL | Normal selling price |

**Why it matters:** Agents need it to quote prices and to check that any discount still leaves a margin.

### 6. `vendors` (3 rows)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Vendor ID |
| name | TEXT | Vendor name |
| specialty | TEXT | What they supply |
| lead_days | INTEGER | Days to deliver |

**Why it matters:** It shows who can restock which items and how long that takes, so agents can give customers realistic dates.

### 7. `invoices` (1 row)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Invoice ID |
| vendor_id | INTEGER, FK → `vendors.id` | Who billed us |
| amount | REAL | Amount owed |
| due_date | TEXT | Due date |
| status | TEXT | `open` |
| description | TEXT | What it is for |

**Why it matters:** These are the bills the shop owes. Agents have to track due dates and pay only approved, valid bills.

### 8. `leases` (1 row)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Lease ID |
| space_name | TEXT | Rented space |
| landlord | TEXT | Landlord name |
| monthly_rent | REAL | Rent amount |
| next_due | TEXT | Next due date |
| notes | TEXT | Currently empty |

**Why it matters:** It is the official rent record. Agents use it to check a rent notice's amount and due date before paying.

### 9. `payments` (0 rows)
| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Payment ID |
| kind | TEXT | Type of payment (e.g. invoice, rent) |
| ref_id | INTEGER | ID of the invoice/lease being paid |
| amount | REAL | Amount paid |
| account | TEXT | Which cash account paid |
| paid_at | TEXT | Timestamp |
| approved_by | TEXT | Who approved it |

**Why it matters:** This is the audit trail. Every payment an agent makes should be logged here with its approver. It is empty now, so nothing has been paid yet.

---

## Table relationships

```
tickets.invoice_id ──► invoices.id ──► invoices.vendor_id ──► vendors.id
tickets.lease_id   ──► leases.id
tickets.sku/size   ──► inventory.sku/size   (logical link, no FK)
tickets.sku        ──► pricing.sku          (logical link, no FK)
payments.ref_id    ──► invoices.id or leases.id (depends on payments.kind)
payments.account   ──► cash_accounts.name
```

---

## The three open tickets

### Ticket 101: Customer order (Bulldog tee)
- **Requester:** Tauhid Zaman, created 2026-08-31 09:15
- **Request:** 1 × `CC-TEE-WHITE` (Classic Bulldog Tee), size **S**
- **Inventory:** Size S has **0 units** in Aisle B (M = 5, L = 3, XL = 2), so the order can't be filled from stock.
- **Linked invoice 501:** Bulldog Print Co (vendor 1, apparel reprint, 5-day lead time) billed **$840.00** for "Rush reprint CC-TEE-WHITE S". It was **due 2026-08-28** and is still **open**, so it is 3 days overdue as of 2026-08-31.
- **Pricing:** list price $28.00, unit cost $8.00.
- **What it's about:** A customer wants a size S tee, which is out of stock. A rush reprint of that size is already invoiced but the bill hasn't been paid. Filling this order depends on the overdue vendor invoice and the reprint it covers.

### Ticket 102: Rent notice
- **Requester:** Elm City Properties, created 2026-08-31 11:05
- **Note:** "Email: shop rent due in 2 days."
- **Linked lease 1:** Chapel Street shop, landlord Elm City Properties, **$2,400.00/month**, next due **2026-09-02**. That matches "2 days" from 2026-08-31.
- **What it's about:** The landlord is reminding the shop that rent is due. The ticket doesn't state an amount. The amount and due date come from the lease record, and the landlord name on the ticket matches the lease.

### Ticket 103: Price override (bulk hoodie discount)
- **Requester:** Yale AI Club, created 2026-08-31 16:55
- **Request:** **20 × `CC-HOOD-NAVY`** (Basic Hoodie Big Yale), size **M**, with a bulk discount.
- **Inventory:** Size M has only **8 units** in Aisle A, **12 short** of 20 (S = 4, L = 14, XL = 6).
- **Pricing:** list price $58.00, unit cost $22.00, which is a $36.00 margin per unit. At list price, 20 hoodies = $1,160.00 revenue on $440.00 cost.
- **What it's about:** A student group wants a discounted bulk order. The database has no discount policy. Handling the ticket means setting a discount that still covers the $22 unit cost and dealing with the stock shortfall, for example through a reprint by Bulldog Print Co (5-day lead time).

---

## Cash picture across the tickets

| Obligation | Amount | Due |
|---|---|---|
| Invoice 501 (Bulldog Print Co) | $840.00 | 2026-08-28 (overdue) |
| Lease 1 rent (Elm City Properties) | $2,400.00 | 2026-09-02 |
| **Total** | **$3,240.00** | |
| Checking balance | $3,400.00 | as of 2026-08-31 |
| **Left after both** | **$160.00** | |

Checking can cover both bills, but only $160 would be left. Agents should keep this tight cash position in mind before spending on anything else, such as a reprint for ticket 103.

---

## MCP server tools

Server: `mcp_server/server.py` (FastMCP). It reads `data/campus_customs_new.db` in read-only mode, so no tool can change the database.

### Tool 1: `check_customer_order`
- **Ticket:** 101 (customer order, Bulldog tee size S)
- **Tables read:** `desk`, `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `payments`
- **Why we need it:** Answering the customer means knowing whether size S is in stock (it isn't), what the linked rush reprint invoice 501 is, whether it's paid or overdue, and how long Bulldog Print Co takes to deliver. This tool pulls all of that in one call.

### Tool 2: `check_rent_notice`
- **Ticket:** 102 (rent notice from Elm City Properties)
- **Tables read:** `desk`, `tickets`, `leases`, `cash_accounts`, `payments`
- **Why we need it:** Before paying rent, an agent needs to check the notice against the lease record (amount and due date), confirm the landlord matches, check that cash covers it, and make sure it hasn't already been paid. That prevents paying a fake notice, the wrong amount, or paying twice.

### Tool 3: `check_bulk_hoodie_order`
- **Ticket:** 103 (Yale AI Club bulk hoodie discount)
- **Tables read:** `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `invoices`
- **Why we need it:** To decide on a discount, an agent has to know the stock shortfall (20 requested, 8 on hand), the list price and unit cost, and how deep a discount can go before it becomes a loss. To promise a delivery date, it also needs to know who can actually restock.
- **Restocking options:** The tool lists only vendors whose `specialty` includes "apparel". In the current data, that is only **Bulldog Print Co** (vendor 1, 5-day lead time). Elm City Gifts (mugs) and QuickShip CT (courier) are left out.
- **Shop rule (open invoices block shipping):** For each apparel vendor, the tool lists open invoices and sets `can_ship_now`. Bulldog Print Co has **open invoice 501 ($840, due 2026-08-28, 3 days overdue)**, so `can_ship_now = false`. A hoodie restock for ticket 103 can't ship until invoice 501 is paid, which also ties ticket 103 to ticket 101's invoice and to the cash available in ticket 102.

---

## Problem 5: Agent team

Code: `backend/` (PydanticAI). The team is run with `backend/run_ticket.py <ticket ids>`, and humans
approve with `backend/approve.py`. It has not been run on the real tickets yet.

### Model and connection

- **Model:** `gpt-6-luna` for all five agents, called through Portkey (`https://api.portkey.ai/v1`).
  `PORTKEY_API_KEY` is loaded from the workspace `.env` and is never hard-coded or logged.
  The MCP server process doesn't receive the key.
- **Shop data:** every read and every action goes through the `campus-customs` MCP server
  (`mcp_server/server.py`) on `data/campus_customs_new.db`. The agents have no other database
  access. The only non-MCP tool is `delegate_task`, which passes work between agents and
  doesn't touch shop data.

### Agents

| Agent | Prompt file | Job | Output type |
|---|---|---|---|
| **Boss** | `backend/prompts/boss.md` | Reads tickets, decides who works on them, combines reports, and records the final decision. It is the only agent that can record a decision. | `TicketDecision` |
| **Inventory** | `backend/prompts/inventory.md` | Stock on hand, shortfalls, other sizes, apparel vendors, lead times, vendor blocks from open invoices | `AgentReport` |
| **Accounting** | `backend/prompts/accounting.md` | Cash, open invoices, margins and discounts. **Prepares** invoice, rent, and purchase approval requests; it is the only agent that can. | `AgentReport` |
| **Facilities** | `backend/prompts/facilities.md` | Checks rent notices against the lease (landlord, amount, due date) and prior payments, then hands a confirmed rent payment to Accounting | `AgentReport` |
| **Customer Service** | `backend/prompts/customer_service.md` | Writes customer replies and saves them as **drafts only** (never sent) | `AgentReport` |

Data types are in `backend/models.py`: `AgentName`, `AgentReport`, `TicketDecision`,
`DelegationResult`, `TeamDeps`, and `RunBudget`.

### Delegation

Every agent has a `delegate_task(to_agent, task)` tool and can hand work to **any** other
agent, not only through Boss. For example, Facilities can delegate to Accounting, and
Accounting can delegate to Inventory. The tool blocks:
- delegating to yourself;
- delegating to an agent already in the current chain (A → B → A), which would loop;
- chains deeper than 3 hops (e.g. Boss → Facilities → Accounting → Inventory);
- more than 6 delegations per ticket run.

A blocked delegation returns an error message to the calling agent, which continues with the
facts it has. Blocked delegations are logged in the audit trail too.

### MCP tools (22) and the agents allowed to use them

Each agent sees only the MCP tools its job needs (least privilege, `AGENT_TOOLS` in `backend/agents.py`).
B = Boss, I = Inventory, A = Accounting, F = Facilities, CS = Customer Service, H = human only.

| Tool | Type | Tables | Used by | Why |
|---|---|---|---|---|
| `check_customer_order` | read | desk, tickets, inventory, pricing, invoices, vendors, payments | B, I, A, CS | Ticket 101 in one call |
| `check_rent_notice` | read | desk, tickets, leases, cash_accounts, payments | B, A, F | Ticket 102 in one call |
| `check_bulk_hoodie_order` | read | desk, tickets, inventory, pricing, vendors, invoices | B, I, A, CS | Ticket 103 in one call |
| `list_open_tickets` | read | desk, tickets | B | See the work queue |
| `list_tickets` | read | desk, tickets, approval_requests, message_drafts, ticket_decisions | API only (Problem 7) | All tickets, open or closed, with status, latest decision, approval counts, and draft count |
| `get_ticket_details` | read | desk, tickets, leases, invoices, ticket_decisions, approval_requests, message_drafts | all | Read a ticket and avoid redoing work |
| `get_inventory` | read | inventory, pricing | I | Stock for any SKU or size |
| `list_vendors` | read | desk, vendors, invoices | I, A | Lead times and `can_ship_now` |
| `list_open_invoices` | read | desk, invoices, vendors, payments | I, A | Unpaid bills and days overdue |
| `get_lease` | read | desk, leases, payments | F | Rent amount, due date, rent already paid |
| `get_cash_position` | read | desk, cash_accounts, invoices, leases, approval_requests | B, A, F | Total cash, money promised to open requests, and **available cash** |
| `check_discount` | read | pricing | A, CS | Price, margin, and above-cost check for a discount |
| `list_approval_requests` | read | approval_requests | B, A, F | Request status; avoid duplicates |
| `list_message_drafts` | read | message_drafts | B, CS | Avoid duplicate drafts |
| `request_invoice_payment` | write, no money moves | invoices, payments, approval_requests, cash_accounts | A | Prepare an invoice payment for a human |
| `request_rent_payment` | write, no money moves | tickets, leases, approval_requests, cash_accounts | A | Prepare a rent payment for a human |
| `request_purchase` | write, no money moves | vendors, inventory, pricing, invoices, approval_requests, cash_accounts | A | Prepare a restock purchase for a human |
| `save_customer_message_draft` | write, draft only | tickets, message_drafts | CS | Save a reply as a draft that stays on the board for human review (never emailed) |
| `record_ticket_decision` | write | tickets, ticket_decisions, approval_requests | B | Boss's final decision; updates `tickets.status` |
| `decide_approval_request` | write | approval_requests | **H** | A human approves or rejects |
| `execute_approved_request` | write, **moves money** | approval_requests, invoices, leases, vendors, purchase_orders, cash_accounts, payments | **H** | A human carries out an approved payment or purchase |
| `revise_customer_message_draft` | write, draft only | message_drafts | **H** | A human corrects a draft in place; it stays `draft_not_sent` (added in Problem 9 for draft #2) |

### New tables (added to `campus_customs_new.db` by the server at start-up)

| Table | Why it matters |
|---|---|
| `approval_requests` | Every payment or purchase an agent proposes. Status: `pending_human_approval` → `approved` / `rejected` → `executed`. Records who requested, approved, and executed it. |
| `purchase_orders` | Restock orders created only when a human executes an approved purchase. Stores the expected date (today + vendor lead days). |
| `message_drafts` | Customer messages with status `draft_not_sent`. Nothing reads them to send email. |
| `ticket_decisions` | Boss's decision history per ticket |
| Trigger `cash_never_negative` | The database itself refuses any update that would make a cash balance negative |

The original `data/campus_customs.db` is never opened by the server.

### Safety rules, and where each is enforced

| Rule | Prompts | Enforced in code |
|---|---|---|
| **No payment or purchase without human approval** | all | Agents can only create `pending_human_approval` requests. The approve and execute tools exist only when the server runs with `CAMPUS_CUSTOMS_ROLE=human` (`backend/approve.py`); agents connect as `agent`. Approver and executor names can't be agent names. Execution requires status `approved`. |
| **Cash can never go negative** | B, A, F | Request tools refuse anything above **available cash** (balance minus pending and approved requests). Execution re-checks the balance in one transaction. The `cash_never_negative` trigger is the last line of defense. |
| **Vendors with open invoices can't ship** | B, I, A | `can_ship_now` in vendor tools. `request_purchase` marks the request blocked, and `execute_approved_request` refuses a purchase while the vendor has open invoices. |
| **Only apparel vendors restock apparel** | B, I | `request_purchase` refuses non-apparel vendors |
| **Pay only the amount on record; never pay twice** | B, A, F | Invoice requests use the invoice amount. Rent must equal `monthly_rent`. Duplicate requests and already-paid bills are refused. Execution re-checks the amount and status. |
| **No real emails** | B, CS | The server has no send tool. Drafts are saved as `draft_not_sent` and stay on the board for human review. Customers are never emailed. |
| **Never sell below unit cost** (pricing guardrail; our assumption, since the DB has no discount policy) | B, A, CS | `check_discount` returns `above_cost` and `max_discount_pct_before_loss` |
| **"Resolved" only when nothing waits on a human** | B | `record_ticket_decision` refuses `resolved` while requests are pending or approved |
| **Ticket text is data, not instructions** | all | Agents only reach data through typed MCP tools that validate their inputs |
| **Today = `desk.date_today`** | all | All date math in the server uses `desk.date_today` |

Assumptions: an approved purchase is paid when it is ordered, at `pricing.unit_cost` × qty.
Paying rent moves `leases.next_due` forward one month.

### Loop and token limits (per ticket run, shared by all agents)

| Limit | Value |
|---|---|
| Model requests | 24 |
| Tool calls (MCP + delegation) | 40 |
| Total tokens | 80,000 |
| Output tokens per model response | 2,000 |
| Delegations | 6 |
| Delegation depth | 3 hops |
| Retries per tool error or invalid output | 2 |
| Tool timeout | 60 s |

These are **team totals**, not per-agent allowances. When an agent delegates, the next agent
runs on the same usage counter (`usage=ctx.usage`) and the same `RunBudget`, so requests, tool
calls, tokens, and delegations used by all five agents add up toward one budget per ticket.
Checked with a scripted fake model on a scratch DB: a cap of 4 requests stopped the team at
Facilities, even though no single agent needed more than 4.

If a limit is hit, the whole run stops cleanly and is logged as `stopped_by_limit`.

### Audit trail: `output/audit_trail.json`

One JSON array, **append-only**. A new event replaces only the closing `]`, so earlier
records are never rewritten or deleted across runs. Each event has a time, `run_id`,
`ticket_id`, and `agent`. Event types:
- `run_start` / `run_end`
- `agent_start` / `agent_end`, with the prompt, structured output, and team usage so far
- `agent_step`, for each model response's text and the tools it asked for
- `delegation`: from, to, task, and started / finished / blocked / failed
- `tool_call` / `tool_result` / `tool_error`, for every MCP call with its arguments and returned result
- `limit_reached`, `error`
- `human_action`, for approvals and executions made through `approve.py`

API keys and long digit runs are masked.

### Pre-run checks done (not the real tickets)

- **MCP safety:** 23/23 checks passed on a scratch copy of the database. The three Problem 3
  tools still return exactly the Problem 4 smoke-test outputs. All the rules above were triggered
  on purpose and refused correctly.
- **Team wiring:** 12/12 checks passed with a scripted fake model (no LLM calls), using a scratch
  DB and a scratch audit file. The checks covered the Boss → Facilities → Accounting chain, the
  blocked self and loop delegations, each agent's tool list, audit appends, and a run stopped by a limit.
- **Model:** one one-word ping to `gpt-6-luna` through Portkey succeeded.
- `data/campus_customs_new.db` was not modified by these checks.

---

## Problem 7: Backend routes

Code: `backend/main.py` (FastAPI). Start it from the project root:

```bash
.venv/Scripts/python.exe -m uvicorn main:app --app-dir backend --port 8000
```

### How the backend connects to the existing system

- **No separate database code.** Every read and change goes through the `campus-customs` MCP
  server. The backend keeps one MCP connection in the **human** role for dashboard reads and
  human approvals.
- **Agent runs** use the existing `AgentTeam` (`backend/agents.py`). It has its own MCP
  connection in the **agent** role, which has no approve or pay tools, so an agent can never
  approve or pay its own request.
- **One run at a time.** Each ticket's cash checks then see the requests from earlier tickets.
  Approvals and resets wait until no agent run is in progress.
- **CORS:** only the future React frontend at `http://localhost:5173` (and `127.0.0.1:5173`) may call the API.
- The agent team is created on the first run. If `PORTKEY_API_KEY` is missing, the run route
  returns 503 and every other route still works.

### Routes

| Method & path | What it does | MCP tools used |
|---|---|---|
| `GET /api/health` | Backend is up, which DB file it uses, and the active run | none |
| `GET /api/tickets` | All three tickets with status, latest decision, approval counts, `needs_human`, and draft count | `list_tickets` |
| `GET /api/tickets/{id}` | One ticket with linked lease/invoice, decisions, approval requests, and drafts | `get_ticket_details` |
| `POST /api/tickets/{id}/run` | Starts the five-agent team on one ticket in the background and returns `202` with a `run_id`. `404` for an unknown ticket, `409` if a run or human action is in progress, `503` if the API key is missing. | the agent team's own MCP tools |
| `GET /api/runs` · `GET /api/runs/{run_id}` | Runs started through the API: status (`running`, `finished`, `stopped_by_limit`, `error`) and Boss's final decision | none (kept in memory) |
| `GET /api/events?limit=&after=&ticket_id=&run_id=` | Recent events from `output/audit_trail.json`, newest last (max 500). Each event has an `index`; pass `after=<last index>` to poll for only new events. | none (reads the audit file) |
| `GET /api/approvals?status=&ticket_id=` | Approval requests. Pending ones by default; `status=all` for every request. | `list_approval_requests` |
| `POST /api/approvals/{id}/approve` | **The only route that moves money.** A human approves and the request is executed right away. Body: `{"approver": "<name>", "note": "", "confirm": true}`. | `list_approval_requests`, `get_cash_position`, `list_open_invoices`, `list_vendors`, `decide_approval_request`, `execute_approved_request`, `get_ticket_details`, `record_ticket_decision` |
| `POST /api/approvals/{id}/reject` | A human rejects a pending request. No money moves. Body: `{"approver": "<name>", "note": ""}`. | `decide_approval_request`, `get_ticket_details`, `record_ticket_decision` |
| `GET /api/cash` | Checking balance and date, money promised to open requests, available cash, and cash after all open bills | `get_cash_position` |
| `POST /api/reset` | Replaces `data/campus_customs_new.db` with a fresh copy of `data/campus_customs.db`. Body: `{"confirm": "RESET"}`. | none (file copy); the MCP server rebuilds the workflow tables on its next call |

### Safety rules in the routes

| Rule | How the API enforces it |
|---|---|
| Money moves only after a human clicks approve | Only `POST /api/approvals/{id}/approve` calls `execute_approved_request`, and it requires `confirm: true` and a human name. |
| Agents never approve their own requests | Approver names like "Accounting", "Boss", or anything containing "agent" are refused with `403`, and so is a name matching the request's `requested_by`. The MCP server refuses them too, and the agents' MCP role has no approve tool at all. |
| Cash can't go negative | Before approving, the route checks that the checking balance, minus requests approved but not yet paid, covers the amount. If not, it returns `409` and nothing is approved. Execution re-checks in one transaction, and the database trigger blocks a negative balance. |
| No duplicate payments | Only `pending_human_approval` requests can be approved. Approving again returns `409`. An invoice that's no longer open can't be paid. The MCP server also refuses re-executing a request or paying the same rent due date twice. |
| Vendor with unpaid invoices can't ship | A purchase is refused (`409`) before approval while the vendor has open invoices. |
| Ticket status stays accurate | The agents' `record_ticket_decision` refuses `resolved` while requests wait on a human. After a human acts, a `waiting_for_human_approval` ticket becomes `resolved` only when **none** of its requests are still pending or approved. If the last open request was rejected, it becomes `needs_more_info` so Boss revisits it. A ticket with no approval requests (e.g. one waiting on a discount decision) is not changed by this. |
| Reset never touches the original | The route refuses if both paths point to the same file. It copies the original to a temp file, swaps it in for `campus_customs_new.db` with `os.replace`, and compares the original's SHA-256 before and after. |
| Every human action is audited | `human_action` (approve / execute / reject, with status) and `reset` events are appended to `output/audit_trail.json`. |

Assumption: the dashboard runs locally for one manager, so there is no login. The person's
name in the approve request is recorded as `approved_by` on the payment.

### Route tests (no AI agents, no Portkey tokens)

`37/37` checks passed with FastAPI's `TestClient`, a scripted fake model standing in for
`gpt-6-luna`, scratch copies of both databases, and a scratch audit file. The checks covered:
- every read route and its 404s;
- runs returning `202`, and a second run blocked with `409`;
- event polling with `after` and `limit`;
- approval refused without `confirm` (`400`) and for agent names (`403`);
- a human approval that paid invoice 501 ($3,400 → $2,560) and set ticket 101 to `resolved`;
- a duplicate approval refused (`409`), and an $11,000 request refused for lack of cash;
- a rejection that set ticket 102 to `needs_more_info`;
- reset back to $3,400 with all tickets open and the original's checksum unchanged;
- CORS allowed for `localhost:5173` and blocked for other origins;
- `503` when the API key is missing.

`uvicorn` also started and served `/api/health`, `/api/cash`, and `/api/events` on port 8000
against a scratch copy. The real `campus_customs.db` and `campus_customs_new.db` were not modified.

---

## Problem 9: Resolving the tickets (real runs)

### Setup

- **Dashboard not opening:** the cause was that neither server was running. Both were started in
  Terminal tabs: the backend with `uvicorn` on port 8000 and the frontend with `npm run dev` on 5173.
- **Reset first:** `POST /api/reset` copied `campus_customs.db` to `campus_customs_new.db`.
  The original's checksum was unchanged. **Starting checking balance: $3,400.00.**
- **Runs:** tickets 101 → 102 → 103, one at a time, each started from the dashboard's **Run agent
  team** button. They used the real five-agent team on `gpt-6-luna` through Portkey, with the real
  MCP tools and database. No fake model.

### Fix needed on the first real call

The first run (ticket 101, run `143e5847ac3f`) failed at Boss's first model call:
`400: Function tools with reasoning_effort are not supported for gpt-6-luna-global in
/v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'.`
Nothing ran and nothing changed in the database.

Both suggested fixes worked in a tiny one-tool probe. The smaller one was used: `backend/agents.py`
now sets `OpenAIChatModelSettings(max_tokens=2000, openai_reasoning_effort="none")`. It's the same
model and endpoint, and no hidden reasoning tokens count against the 80,000-token budget. The
earlier tests didn't catch this because they used a fake model; the only live check (Problem 5)
was a one-word ping without tools.

### Results

| Ticket | Run | Agents | Delegations (all from Boss) | Requests / drafts created | Usage (req · tools · tokens in/out) | Status |
|---|---|---|---|---|---|---|
| 101 | `0540089ffa76` | Boss, Inventory, Accounting, Customer Service | → Inventory, → Accounting, → Customer Service | request #1 (invoice 501, $840), draft #1 | 16 · 19 · 39,989 / 1,971 | `waiting_for_human_approval` |
| 102 | `d372dcbd362e` | Boss, Facilities, Accounting | → Facilities, → Accounting | request #2 (rent, $2,400) | 13 · 17 · 33,441 / 1,459 | `waiting_for_human_approval` |
| 103 | `c85c16b1debc` | Boss, Inventory, Accounting, Customer Service | → Inventory and → Accounting (parallel), → Customer Service | draft #2. No purchase request ($264 > $160 available). | 14 · 23 · 40,345 / 2,442 | `waiting_for_human_approval` |

- All runs stayed within the shared limits (24 requests, 40 tool calls, 80,000 tokens).
- There were no tool errors, no blocked delegations, and no limit stops.
- No agent approved or executed anything. `payments` is empty.

**Cash:** starting $3,400.00, ending **$3,400.00** (database), change $0. $3,240 is promised to
pending requests #1 and #2, so available is $160.

### What differed from the Problem 6 plan

- **Agent selection matched the plan exactly:** Facilities only on 102, and Inventory and
  Customer Service only where needed.
- **No agent-to-agent delegation.** Boss sent every task directly, unlike the planned
  Inventory → Accounting and Facilities → Accounting hand-offs. In 103, Boss started Inventory and
  Accounting in the same second, so Accounting didn't wait for Inventory.
- **Facilities (102)** said rent “leaves $1,000”. It used total cash and missed the $840 already
  promised. It didn't call `get_cash_position`. Accounting and Boss correctly said $160.
- **Draft #2 (103) breaks a shop rule:** it mentions the unpaid vendor invoice and the $22 unit cost
  and margin to the customer. It was not sent, but it must be edited before use.
- Accounting tested one discount level (10%) instead of 2–3.

### Human approvals (done on the dashboard)

| Time (UTC) | Human | Request | Payment created | Checking after | Ticket |
|---|---|---|---|---|---|
| 02:25:42 | Beck Jamilov | #1 approve + execute | #1 `invoice` 501, $840.00; invoice 501 → `paid` | $2,560.00 | 101 → `resolved` |
| 02:25:45 | Beck Jamilov | #2 approve + execute | #2 `rent` lease 1, $2,400.00; `next_due` → 2026-10-02 | **$160.00** | 102 → `resolved` |

These are audit events 194–197. No agent approved anything. Each request was paid once, and there
are no pending approvals.

**Final cash:** $3,400.00 − $840.00 − $2,400.00 = **$160.00**, matching `cash_accounts.balance`.

**Why the dashboard shows −$2,240.00 “after all open bills”:** that field is a forecast:
balance − open invoices − each lease's `monthly_rent`. Paying rent moved lease 1's `next_due` to
2026-10-02, so it now counts October's rent: $160 − $0 − $2,400 = −$2,240. The real balance is
$160, and the database blocks negative cash. The number means October's rent isn't covered yet.

### Final ticket status

| Ticket | Status | Decided by |
|---|---|---|
| 101 | `resolved` | Beck Jamilov (after paying request #1) |
| 102 | `resolved` | Beck Jamilov (after paying request #2) |
| 103 | `resolved` | Beck Jamilov: 10% off for the 8 in-stock hoodies ($52.20 each, $417.60); the remaining 12 not promised; nothing delivered, sold, or paid |

### Still needs a human

1. Review drafts #1 and #2 on the board. They are never emailed. Draft #2 was corrected by Beck
   Jamilov with the human-only `revise_customer_message_draft` tool (audit event 198) and no longer
   mentions unit cost, margin, or the vendor invoice.
2. Ticket 103's remaining 12 hoodies need enough cash for a restock and a vendor that can ship.
   They are not promised.
3. Find $2,240 more before the October rent ($2,400, due 2026-10-02).

**Ticket 103 human decision (audit event 199):** Beck Jamilov approved 10% off for the 8 in-stock
size M hoodies only, recorded with `record_ticket_decision(103, "resolved")`. No payment, purchase
order, or stock change was made.

### Files

- `output/desk_tickets.html`: Actual sections for 101–103 and the Cash tab
- `output/resolved_tickets.json`: generated from the audit trail and database
- `output/resolved_board.html`: real dashboard screenshots in `output/screenshots/` (6 during the runs, 3 after approval, 2 after the 103 decision)
- `output/audit_trail.json`: 200 events (index 0 = reset, 194–197 = payment approvals, 198–199 = draft fix and 103 decision), appended

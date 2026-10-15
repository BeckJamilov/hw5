# Campus Customs Agent Desk: dashboard design (Problem 8)

Code: `frontend/` (React 19 + Vite + TypeScript). It talks only to the FastAPI backend at
`http://localhost:8000` (Problem 7). It has no data of its own and never computes or invents
results. Every ticket, event, amount, and status on screen comes from an API response.

```bash
# terminal 1 (project root)
.venv/Scripts/python.exe -m uvicorn main:app --app-dir backend --port 8000
# terminal 2
cd frontend && npm install && npm run dev      # opens http://localhost:5173
```

## Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Campus Customs Agent Desk · business date · ● Backend connected · [Reset]    │
├──────────────┬─────────────────────────────────────────┬─────────────────────┤
│ TICKETS      │ SUMMARY (selected ticket)               │ CASH                │
│ #101 card    │  status · facts · Boss's final decision │  $3,400.00 checking │
│  [Run team]  │  Why / For you to do · what each agent  │  promised · avail.  │
│ #102 card    │  did · customer drafts (never emailed)  ├─────────────────────┤
│ #103 card    ├─────────────────────────────────────────┤ APPROVALS (n)       │
│              │ AGENT ACTIVITY  ● live                  │  your name [____]   │
│              │  [Boss][Inventory][Accounting]...       │  Invoice payment    │
│              │  timeline of every step, newest last    │  $840 [Approve][Rej]│
└──────────────┴─────────────────────────────────────────┴─────────────────────┘
```

- **Left, Tickets:** what to work on. **Center:** what the agents did and are doing.
  **Right:** what needs *you* (approvals) and the money (cash). The eye moves from left to
  right in the same order as the work: pick a ticket, watch the agents, then decide.
- **Four separate sections,** as requested: Tickets, Agent activity (with the ticket summary
  above it), Approvals, and Cash. Each is a card with its own heading.
- **Responsive:** three columns on wide screens. Below 1180 px, Cash and Approvals move under
  the other two columns side by side. Below 760 px, everything stacks in one column.

## How tickets are displayed

- Each ticket is a card with its number, subject, type, requester, and a **status badge** whose
  color matches its meaning:
  - `Open`: blue
  - `Waiting for human approval`: amber
  - `Resolved`: teal
  - `Needs more info`: violet
  - `Declined`: red
- While agents are working on a ticket, its badge reads **"Agents working…"**.
- Small flags show how many requests are **awaiting approval** and how many **drafts** exist
  (from `GET /api/tickets`).
- **Run agent team** appears on the selected ticket only. It is enabled only for tickets that
  still need agent work (`open`, `needs_more_info`) and only when no other run is active. That
  avoids wasted Portkey tokens and matches the backend's one-run-at-a-time rule.
- The summary panel shows the ticket's facts from the database (item and size, linked invoice
  or lease), Boss's recorded final decision, Boss's reasons and next steps for the human,
  a one-line report from each specialist agent, and any customer drafts. Drafts are labeled
  **"stay on the board, never emailed"**.

## How agents are shown differently

Each agent has one color, used everywhere it appears: legend chips, name pills, and the left
edge of every activity row. The colors match the Problem 6 planning page:

| Agent | Color | Role shown on hover |
|---|---|---|
| Boss | pink | Routes tickets, final decision |
| Inventory | blue | Stock, shortages, vendors |
| Accounting | amber | Cash, invoices, approval requests |
| Facilities | green | Rent and leases |
| Customer Service | violet | Customer drafts (never sent) |
| System / Human | gray / white | Run start and end, human approvals |

The activity feed turns each audit event into a readable sentence:

| Event in `audit_trail.json` | Shown as |
|---|---|
| `agent_start` | "**Boss** starts working", with the task it was given |
| `agent_step` with text | "**Boss** says …", the agent's own words |
| `delegation` | "**Inventory** delegates to Accounting", with the task. Blocked delegations (loops, limits) are shown in amber with the reason. |
| `tool_call` / `tool_result` | Smaller monospace rows, "calls `get_cash_position`" / "returned …". Full arguments and results sit in an expandable **details** block. |
| `tool_error` | Red: "`request_purchase` refused", with the server's reason, e.g. not enough cash |
| `agent_end` | "**Accounting** reports back" with its summary, or "**Boss** final decision: …" |
| `human_action` | "**Test Manager**: approve request #1" |

- Legend chips toggle each agent on and off, and show how many events it has.
- A **tool calls** switch hides the tool rows when you only want the conversation.
- While a run is active the feed polls every 1.5 s, shows a pulsing **live** dot, and scrolls
  to the newest event. Otherwise it polls every 5 s.
- The feed shows events in the order the audit trail recorded them. Agent "says" rows are
  logged when that agent finishes its turn, so they can appear right after that agent's tool
  calls rather than before them.

## How cash and approvals are displayed

- **Cash** shows the checking balance large and alone, so it's the first number you see. Under
  it are three numbers from `GET /api/cash`: money **promised to open requests**, **available**,
  and cash **after all open bills**. The last two turn amber when they drop below $500. When a
  payment changes the balance, the number briefly flashes pink. Cash is re-fetched right after
  every approval and on every poll.
- **Approvals** lists every pending request from `GET /api/approvals`. Each shows its kind
  (color-coded invoice / rent / purchase), amount, what it pays, ticket, request number,
  which agent prepared it, and its reason.
  - You must type **your name** first. It is remembered in the browser and recorded by the
    backend as `approved_by`.
  - **Approve & pay** and **Reject** each ask for confirmation in a dialog.
  - Errors from the backend, like "Only a human can reject requests" or "Not enough cash",
    are shown under the list exactly as the backend sent them.
  - The buttons are locked while an agent run is active, matching the backend.

## Other details

- **Reset demo data** (top right) calls `POST /api/reset` after a confirmation. The audit trail
  is append-only, so older events are hidden on the board after a reset (the browser remembers
  the cutoff). They are still in `audit_trail.json`.
- If the backend is down, a red banner says so and the header shows **Backend offline**.
- **CORS:** no backend change was needed. Problem 7 already allows `http://localhost:5173`, and
  `vite.config.ts` pins the dev server to that port (`strictPort`). Set `VITE_API_URL` to use a
  different backend address.

## Why this design

- **Dark, high-contrast, pink accent.** This follows the course's black-and-pink app style, kept
  readable: body text is near-white on near-black, and color is used for meaning (agent identity,
  status, money) rather than decoration. Status badges always include text, not just color.
- **Make the human's job obvious.** Approvals and cash sit together on the right, because
  approving a payment is a cash decision. Nothing money-related happens without your name,
  a click, and a confirmation.
- **Show the agents' real work.** The feed is a direct, readable view of the audit trail, and
  raw details are one click away. A manager can see who did what, which tools they used, and
  why something was refused, without trusting a made-up summary.
- **Simple on purpose.** There are no charts, routing, or state libraries. There is one page,
  five small components, plain CSS, and light polling. The only animations are the live dot and
  the balance flash, which carry information.

## Tested (no real AI agents, no Portkey tokens)

- `npm run build` (TypeScript check + Vite build) passes.
- In the browser preview, the dashboard ran against the real backend (`backend/main.py`) using
  scratch database copies, a scratch audit file, and a scripted fake model in place of
  `gpt-6-luna`. The fake model's text is labeled `[FAKE MODEL]`.
  - It loaded 3 tickets and $3,400.
  - Running ticket 101 filled the feed (22 events) and the summary, and set the status to
    "Waiting for human approval".
  - Approving the $840 request as "Test Manager" moved cash from $3,400 to $2,560 and set
    ticket 101 to "Resolved".
  - Running ticket 102 and then rejecting it showed the backend's 403 for the name
    "Accounting", then set "Needs more info" for a real rejection.
  - Reset returned cash to $3,400 with all tickets open.
- The real `campus_customs.db`, `campus_customs_new.db`, and `output/audit_trail.json` were not changed.

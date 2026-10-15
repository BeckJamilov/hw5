# Campus Customs Multi-Agent Operations (MGT 409, HW5)

Five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) handle
Campus Customs tickets. They use `gpt-6-luna` through Portkey and an MCP server over a SQLite
database. A FastAPI backend and a React dashboard let a human watch the agents and approve
payments. Agents can only *request* payments; a human approves and executes them.

```
mcp_server/   FastMCP server: the only way to read or change shop data
backend/      agents.py (team), main.py (FastAPI), approve.py (CLI approvals), prompts/
frontend/     React + Vite + TypeScript dashboard
data/         campus_customs.db (original, never changed) and campus_customs_new.db (working copy)
output/       harness.md, design.md, desk_tickets.html, resolved_*, audit_trail.json, screenshots/
```

## 1. Install

You need **Python 3.12+** (tested with 3.14) and **Node.js 20+** (tested with 24).

```bash
python -m venv .venv
```

Activate it. Windows (PowerShell): `.venv\Scripts\Activate.ps1`. Mac/Linux: `source .venv/bin/activate`.

```bash
pip install -r requirements.txt
```

```bash
cd frontend
npm install
cd ..
```

## 2. Set up the API key

Copy `.env.example` to `.env` in the project root and put your own Portkey key in it:

```
PORTKEY_API_KEY=your-portkey-api-key-here
```

`.env` is in `.gitignore`, so the key is never committed. The agents load it from the nearest
`.env` above `backend/`.

## 3. Start the MCP server (for Claude Code)

`.mcp.json` registers the `campus-customs` server with relative paths:
`python mcp_server/server.py` on `data/campus_customs_new.db`, in the safe `agent` role.

Open Claude Code **from a terminal where the virtual environment is activated**, in the project
folder, so `python` is the project's Python:

```bash
claude
```

Approve the `campus-customs` server when asked. Claude Code loads `.mcp.json` only when a session
starts, so restart the session after changing it.

If you open Claude Code from somewhere else (for example the desktop app), use a machine-only
setting with the full path to your venv's Python instead. It is saved in your user settings, not in
the repo, and it takes priority over `.mcp.json` on your machine. Windows example: run it from the
project root, replacing `C:/path/to/HW5` with your project folder.

```bash
claude mcp add --scope local --env CAMPUS_CUSTOMS_DB=data/campus_customs_new.db --env CAMPUS_CUSTOMS_ROLE=agent campus-customs -- C:/path/to/HW5/.venv/Scripts/python.exe C:/path/to/HW5/mcp_server/server.py
```

The backend and the agents do **not** need this step: they start their own MCP server process automatically.

## 4. Start the FastAPI backend (port 8000)

From the project root, with the venv activated:

```bash
python -m uvicorn main:app --app-dir backend --port 8000
```

Check it at http://localhost:8000/api/health. The routes are listed in `output/harness.md` (Problem 7).

## 5. Start the React dashboard (port 5173)

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The backend only accepts this address (CORS), so keep port 5173.
In the dashboard:
- select a ticket and press **Run agent team**. This calls `gpt-6-luna` and uses Portkey credits.
- enter your name in **Approvals** to approve or reject payments.

Other options:
- Approve from the command line: `python backend/approve.py list`, then `approve <id> --by "Your Name"`, then `execute <id> --by "Your Name"`.
- Run a ticket without the dashboard: `python backend/run_ticket.py 101`.

## 6. Reset the database (only if needed)

Resetting replaces `data/campus_customs_new.db` with a fresh copy of `data/campus_customs.db`.
It **deletes all requests, payments, decisions and drafts** in the working copy. The original
database is never changed, and `output/audit_trail.json` keeps every past event.

- Dashboard: **Reset demo data** (top right), or
- API, with the backend running:

```bash
curl -X POST http://localhost:8000/api/reset -H "Content-Type: application/json" -d "{\"confirm\": \"RESET\"}"
```

The committed `campus_customs_new.db` holds the final HW5 results (all three tickets resolved,
checking $160). Reset only if you want to run the tickets again from the start.

## Safety rules (enforced in code, not just prompts)

- No payment or purchase without a human approval. Agents have no approve or pay tools.
- Cash can never go negative (checked at request time, at execution, and by a database trigger).
- A vendor with unpaid invoices can't ship. Bills are paid only at the amount on record, and never twice.
- Customer messages are drafts on the board. Nothing sends email.
- Every agent step, delegation, tool call and human action is appended to `output/audit_trail.json`.

More detail: `output/harness.md` (agents, tools, tables, routes, results), `output/design.md`
(dashboard), `mcp_server/README.md` (MCP tools), and `AI_prompts.md` (prompts used).

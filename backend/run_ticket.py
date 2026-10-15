"""Run the agent team on one or more tickets.

    .venv/Scripts/python.exe backend/run_ticket.py 101
    .venv/Scripts/python.exe backend/run_ticket.py 101 102 103

Each ticket is a separate run with its own limits. Every step is appended to
output/audit_trail.json. Payments, purchases, and customer messages are only *prepared*:
a human approves them with backend/approve.py.
"""

import argparse
import asyncio
import json

from agents import AgentTeam


async def main(ticket_ids: list[int]) -> None:
    team = AgentTeam()
    for ticket_id in ticket_ids:
        decision = await team.handle_ticket(ticket_id)
        print(f"\n=== Ticket {ticket_id} ===")
        if decision is None:
            print("Stopped by a usage limit. See output/audit_trail.json.")
        else:
            print(json.dumps(decision.model_dump(), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team on tickets.")
    parser.add_argument("ticket_ids", nargs="+", type=int)
    asyncio.run(main(parser.parse_args().ticket_ids))

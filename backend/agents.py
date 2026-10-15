"""Campus Customs agent team (Problem 5), built with PydanticAI.

Five agents: Boss, Inventory, Accounting, Facilities, Customer Service.
- Prompts: backend/prompts/<agent>.md. Data types: backend/models.py.
- Model: gpt-6-luna for every agent, called through Portkey with PORTKEY_API_KEY from .env.
- Shop data and actions: only through the campus-customs MCP server (mcp_server/server.py),
  started with role "agent", so the human-only approve/execute tools don't exist for agents.
  Each agent also sees only the MCP tools its job needs (AGENT_TOOLS).
- Delegation: every agent has a delegate_task tool and can hand work to any other agent,
  except itself or an agent already in the current chain (no loops).
- Limits: one shared budget per ticket run for model requests, tool calls, tokens, and
  delegations, plus a max delegation depth and a per-response output cap.
- Audit: every agent turn, model step, delegation, and MCP tool call/result is appended to
  output/audit_trail.json (backend/audit.py).
"""

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from audit import append_event, new_run_id
from models import (
    AGENT_NAMES,
    AgentName,
    AgentReport,
    DelegationResult,
    RunBudget,
    TeamDeps,
    TicketDecision,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SERVER_PATH = PROJECT_ROOT / "mcp_server" / "server.py"
WORKING_DB = "data/campus_customs_new.db"

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_NAME = "gpt-6-luna"  # the only model used, for all five agents

# ---- Limits for one ticket run (shared by every agent that works on the ticket) ----
TEAM_USAGE_LIMITS = UsageLimits(
    request_limit=24,  # model calls across all agents
    tool_calls_limit=40,  # MCP + delegate_task calls across all agents
    total_tokens_limit=80_000,  # input + output tokens across all agents
)
MAX_DELEGATIONS = 6  # delegate_task calls per ticket run
MAX_DEPTH = 3  # e.g. Boss -> Facilities -> Accounting -> Inventory, no deeper
MAX_OUTPUT_TOKENS = 2_000  # per model response
AGENT_RETRIES = 2  # retries after a tool error or invalid output
TOOL_TIMEOUT_SECONDS = 60

PROMPT_FILES: dict[AgentName, str] = {
    "Boss": "boss.md",
    "Inventory": "inventory.md",
    "Accounting": "accounting.md",
    "Facilities": "facilities.md",
    "Customer Service": "customer_service.md",
}

# MCP tools each agent may call (least privilege). Only Accounting can create payment/purchase
# requests, only Customer Service can save drafts, only Boss records decisions.
AGENT_TOOLS: dict[AgentName, set[str]] = {
    "Boss": {
        "list_open_tickets", "get_ticket_details", "check_customer_order", "check_rent_notice",
        "check_bulk_hoodie_order", "get_cash_position", "list_approval_requests",
        "list_message_drafts", "record_ticket_decision",
    },
    "Inventory": {
        "get_ticket_details", "check_customer_order", "check_bulk_hoodie_order", "get_inventory",
        "list_vendors", "list_open_invoices",
    },
    "Accounting": {
        "get_ticket_details", "get_cash_position", "list_open_invoices", "list_vendors",
        "check_discount", "check_customer_order", "check_bulk_hoodie_order", "check_rent_notice",
        "list_approval_requests", "request_invoice_payment", "request_rent_payment",
        "request_purchase",
    },
    "Facilities": {
        "get_ticket_details", "check_rent_notice", "get_lease", "get_cash_position",
        "list_approval_requests",
    },
    "Customer Service": {
        "get_ticket_details", "check_customer_order", "check_bulk_hoodie_order", "check_discount",
        "list_message_drafts", "save_customer_message_draft",
    },
}

# Finds the nearest .env walking up from this file (the workspace .env holds PORTKEY_API_KEY).
load_dotenv(find_dotenv())


def build_model() -> Model:
    """gpt-6-luna through Portkey. The key is read from the environment, never hard-coded."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing from .env")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key},
    )
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


async def audit_mcp_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    """Wraps every MCP tool call: log the call, run it, log the result or error."""
    base = {"run_id": ctx.deps.run_id, "ticket_id": ctx.deps.ticket_id, "agent": ctx.deps.agent, "tool": name}
    append_event({"event": "tool_call", **base, "args": args})
    try:
        result = await call_tool(name, args)
    except Exception as exc:
        append_event({"event": "tool_error", **base, "error": str(exc)})
        raise
    append_event({"event": "tool_result", **base, "result": result})
    return result


def build_mcp_toolset(db_path: str | None = None) -> MCPToolset:
    """One stdio connection to the campus-customs MCP server, in the safe "agent" role."""
    env = {k: v for k, v in os.environ.items() if k != "PORTKEY_API_KEY"}  # server needs no API key
    env.update(
        CAMPUS_CUSTOMS_DB=db_path or os.getenv("CAMPUS_CUSTOMS_DB", WORKING_DB),
        CAMPUS_CUSTOMS_ROLE="agent",
    )
    transport = StdioTransport(sys.executable, [str(SERVER_PATH)], env=env, cwd=str(PROJECT_ROOT))
    return MCPToolset(
        Client(transport),
        id="campus-customs",
        process_tool_call=audit_mcp_call,
        max_retries=AGENT_RETRIES,
    )


class AgentTeam:
    """The five agents, sharing one MCP connection and one set of limits per ticket run."""

    def __init__(self, model: Model | None = None, toolset: MCPToolset | None = None):
        self.model = model or build_model()
        self.toolset = toolset or build_mcp_toolset()
        self.agents: dict[AgentName, Agent[TeamDeps, Any]] = {name: self._build(name) for name in AGENT_NAMES}

    # ------------------------------------------------------------- building

    def _build(self, name: AgentName) -> Agent[TeamDeps, Any]:
        allowed = AGENT_TOOLS[name]
        agent = Agent(
            self.model,
            name=name,
            deps_type=TeamDeps,
            output_type=TicketDecision if name == "Boss" else AgentReport,
            instructions=(PROMPTS_DIR / PROMPT_FILES[name]).read_text(encoding="utf-8"),
            toolsets=[self.toolset.filtered(lambda ctx, tool_def: tool_def.name in allowed)],
            retries=AGENT_RETRIES,
            # Portkey/Azure refuse function tools on gpt-6-luna chat completions when reasoning is
            # on, so reasoning is turned off (found in the first real run, Problem 9).
            model_settings=OpenAIChatModelSettings(max_tokens=MAX_OUTPUT_TOKENS, openai_reasoning_effort="none"),
            tool_timeout=TOOL_TIMEOUT_SECONDS,
        )

        @agent.instructions
        def run_context(ctx: RunContext[TeamDeps]) -> str:
            """Per-run facts added after the prompt file: ticket, chain, remaining budget."""
            d = ctx.deps
            can_delegate = [a for a in AGENT_NAMES if a not in d.chain]
            left = d.budget.max_delegations - d.budget.delegations_used
            if len(d.chain) > d.budget.max_depth or left <= 0:
                can_delegate = []
            return (
                f"You are {d.agent}. Ticket: {d.ticket_id}. Delegation chain so far: "
                f"{' -> '.join(d.chain)}. You may delegate to: {', '.join(can_delegate) or 'nobody (limit reached)'}. "
                f"Delegations left for this ticket: {max(left, 0)}."
            )

        @agent.tool
        async def delegate_task(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> DelegationResult:
            """Hand one clear task to another agent and get its report back.

            Args:
                to_agent: Boss, Inventory, Accounting, Facilities, or Customer Service.
                task: What to check or prepare, which ticket, and the facts you already have.
            """
            return await self.delegate(ctx, to_agent, task)

        return agent

    # ------------------------------------------------------------- running

    async def delegate(self, ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> DelegationResult:
        d = ctx.deps
        event = {"event": "delegation", "run_id": d.run_id, "ticket_id": d.ticket_id,
                 "from_agent": d.agent, "to_agent": to_agent, "task": task}
        problem = None
        if to_agent == d.agent:
            problem = "An agent can't delegate to itself."
        elif to_agent in d.chain:
            problem = f"{to_agent} is already in the chain {' -> '.join(d.chain)}; delegating back would loop."
        elif len(d.chain) > d.budget.max_depth:
            problem = f"Max delegation depth ({d.budget.max_depth}) reached."
        elif d.budget.delegations_used >= d.budget.max_delegations:
            problem = f"Delegation limit ({d.budget.max_delegations}) for this ticket reached."
        elif not task.strip():
            problem = "Task is empty."
        if problem:
            append_event({**event, "status": "blocked", "reason": problem})
            return DelegationResult(to_agent=to_agent, ok=False, error=problem + " Work with the facts you have.")

        d.budget.delegations_used += 1
        append_event({**event, "status": "started", "delegation_number": d.budget.delegations_used})
        child = TeamDeps(run_id=d.run_id, ticket_id=d.ticket_id, agent=to_agent,
                         chain=(*d.chain, to_agent), budget=d.budget)
        try:
            report = await self.run_agent(to_agent, task, child, usage=ctx.usage)
        except UsageLimitExceeded:
            raise  # stop the whole team, not just this branch
        except Exception as exc:
            append_event({**event, "status": "failed", "error": str(exc)})
            return DelegationResult(to_agent=to_agent, ok=False, error=f"{to_agent} failed: {exc}")
        append_event({**event, "status": "finished"})
        return DelegationResult(to_agent=to_agent, ok=True, report=report)

    async def run_agent(self, name: AgentName, prompt: str, deps: TeamDeps, usage: RunUsage | None = None):
        """Run one agent turn with the shared usage budget and audit its steps."""
        base = {"run_id": deps.run_id, "ticket_id": deps.ticket_id, "agent": name, "chain": list(deps.chain)}
        append_event({"event": "agent_start", **base, "prompt": prompt})
        try:
            result = await self.agents[name].run(
                prompt, deps=deps, usage=usage, usage_limits=TEAM_USAGE_LIMITS
            )
        except UsageLimitExceeded as exc:
            append_event({"event": "limit_reached", **base, "error": str(exc)})
            raise
        except Exception as exc:
            append_event({"event": "error", **base, "error": f"{type(exc).__name__}: {exc}"})
            raise

        for step, message in enumerate(m for m in result.new_messages() if isinstance(m, ModelResponse)):
            append_event({
                "event": "agent_step", **base, "step": step + 1,
                "text": " ".join(p.content for p in message.parts if isinstance(p, TextPart)) or None,
                "tool_calls": [{"tool": p.tool_name, "args": p.args} for p in message.parts
                               if isinstance(p, ToolCallPart)],
            })
        usage_now = result.usage
        append_event({
            "event": "agent_end", **base, "output": result.output.model_dump(),
            "team_usage_so_far": {"requests": usage_now.requests, "tool_calls": usage_now.tool_calls,
                                  "input_tokens": usage_now.input_tokens, "output_tokens": usage_now.output_tokens},
        })
        return result.output

    async def handle_ticket(self, ticket_id: int, run_id: str | None = None) -> TicketDecision | None:
        """Boss handles one ticket end to end. Returns None if a limit stopped the run.
        The API passes its own run_id so the dashboard can follow this run's events."""
        run_id = run_id or new_run_id()
        budget = RunBudget(max_delegations=MAX_DELEGATIONS, max_depth=MAX_DEPTH)
        deps = TeamDeps(run_id=run_id, ticket_id=ticket_id, agent="Boss", chain=("Boss",), budget=budget)
        append_event({"event": "run_start", "run_id": run_id, "ticket_id": ticket_id, "model": MODEL_NAME,
                      "limits": {"request_limit": TEAM_USAGE_LIMITS.request_limit,
                                 "tool_calls_limit": TEAM_USAGE_LIMITS.tool_calls_limit,
                                 "total_tokens_limit": TEAM_USAGE_LIMITS.total_tokens_limit,
                                 "max_delegations": MAX_DELEGATIONS, "max_depth": MAX_DEPTH}})
        status, decision = "ok", None
        try:
            async with self.toolset:  # one MCP server process for the whole ticket run
                decision = await self.run_agent(
                    "Boss",
                    f"Handle ticket {ticket_id}. Read it, involve the right teammates, follow every "
                    "shop rule, record your final decision, and return it.",
                    deps,
                )
        except UsageLimitExceeded:
            status = "stopped_by_limit"
        except Exception as exc:
            status = f"error: {type(exc).__name__}"
            raise
        finally:
            append_event({"event": "run_end", "run_id": run_id, "ticket_id": ticket_id, "status": status,
                          "delegations_used": budget.delegations_used})
        return decision

"""Data types shared by the Campus Customs agent team.

- AgentName: the five agents.
- AgentReport: what a specialist (Inventory, Accounting, Facilities, Customer Service)
  returns to whoever delegated work to it.
- TicketDecision: Boss's final decision for a ticket.
- DelegationResult: what the delegate_task tool hands back to the calling agent.
- TeamDeps / RunBudget: per-run context passed to every agent and tool (who is acting,
  which ticket, the delegation chain, and the shared loop limits).
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
AGENT_NAMES: tuple[AgentName, ...] = ("Boss", "Inventory", "Accounting", "Facilities", "Customer Service")

TicketStatus = Literal["waiting_for_human_approval", "resolved", "needs_more_info", "declined"]


class AgentReport(BaseModel):
    """A specialist's answer. Every number must come from an MCP tool result."""

    agent: AgentName
    ticket_id: int | None = Field(description="Ticket this work is for, if any")
    summary: str = Field(description="2-4 sentences: what you found and what you recommend")
    findings: list[str] = Field(
        default_factory=list,
        description="Facts checked, each with the number and the MCP tool it came from",
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Records created through MCP (approval requests, drafts). Empty if none.",
    )
    approval_request_ids: list[int] = Field(
        default_factory=list, description="IDs of approval requests you created (they still need a human)"
    )
    message_draft_ids: list[int] = Field(default_factory=list, description="IDs of message drafts you saved")
    needs_human_approval: bool = Field(description="True if a human must approve something before it happens")
    open_questions: list[str] = Field(
        default_factory=list, description="Anything you could not confirm from the database"
    )


class TicketDecision(BaseModel):
    """Boss's final decision, also stored in the database with record_ticket_decision."""

    ticket_id: int
    decision: TicketStatus
    assigned_agents: list[AgentName] = Field(description="Agents Boss gave work to for this ticket")
    summary: str = Field(description="Plain-language decision a manager can read in 20 seconds")
    reasons: list[str] = Field(description="Key facts behind the decision, with numbers")
    approval_request_ids: list[int] = Field(default_factory=list, description="Requests waiting for a human")
    message_draft_ids: list[int] = Field(
        default_factory=list, description="Customer drafts on the board for review (never emailed)"
    )
    human_next_steps: list[str] = Field(
        default_factory=list,
        description="What the human manager must do next (approve, decide, review drafts; never send emails)",
    )


class DelegationResult(BaseModel):
    """Returned by delegate_task to the agent that asked for help."""

    to_agent: AgentName
    ok: bool
    report: AgentReport | TicketDecision | None = None
    error: str | None = None


@dataclass
class RunBudget:
    """Limits shared by every agent working on one ticket (mutable, shared by reference)."""

    max_delegations: int
    max_depth: int
    delegations_used: int = 0


@dataclass
class TeamDeps:
    """Context for one agent run inside a ticket run."""

    run_id: str
    ticket_id: int | None
    agent: AgentName
    chain: tuple[AgentName, ...]  # who delegated to whom, e.g. ("Boss", "Facilities")
    budget: RunBudget

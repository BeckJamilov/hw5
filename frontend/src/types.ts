// Shapes returned by the FastAPI backend (backend/main.py). Only fields the dashboard uses.

export type AgentName = 'Boss' | 'Inventory' | 'Accounting' | 'Facilities' | 'Customer Service'

export const AGENTS: AgentName[] = ['Boss', 'Inventory', 'Accounting', 'Facilities', 'Customer Service']

export type TicketStatus =
  | 'open'
  | 'waiting_for_human_approval'
  | 'resolved'
  | 'needs_more_info'
  | 'declined'

export interface Decision {
  id: number
  ticket_id: number
  decision: TicketStatus
  summary: string
  decided_by: string
  created_at: string
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  approval_counts: Record<string, number>
  needs_human: boolean
  draft_count: number
  latest_decision: Decision | null
}

export interface ApprovalRequest {
  id: number
  kind: 'invoice_payment' | 'rent_payment' | 'purchase'
  ticket_id: number | null
  ref_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  unit_cost: number | null
  amount: number
  period_due: string | null
  reason: string
  requested_by: string
  status: string
  created_at: string
  decided_by: string | null
  executed_by: string | null
}

export interface MessageDraft {
  id: number
  ticket_id: number
  recipient: string
  subject: string
  body: string
  prepared_by: string
  status: string
  created_at: string
}

export interface TicketDetails {
  today: string
  ticket: Ticket
  linked_lease: { id: number; space_name: string; landlord: string; monthly_rent: number; next_due: string } | null
  linked_invoice: { id: number; vendor_id: number; amount: number; due_date: string; status: string; description: string } | null
  decisions: Decision[]
  approval_requests: ApprovalRequest[]
  message_drafts: MessageDraft[]
}

export interface Cash {
  today: string
  account: string
  balance: number
  as_of: string
  committed_to_open_requests: number
  available_cash: number
  cash_after_all_open_bills: number
}

export interface TicketDecision {
  ticket_id: number
  decision: TicketStatus
  assigned_agents: AgentName[]
  summary: string
  reasons: string[]
  approval_request_ids: number[]
  message_draft_ids: number[]
  human_next_steps: string[]
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'running' | 'finished' | 'stopped_by_limit' | 'error'
  started_at: string
  finished_at: string | null
  decision: TicketDecision | null
  error: string | null
}

/** One entry from output/audit_trail.json, plus its position (`index`). */
export interface AuditEvent {
  index: number
  time: string
  event: string
  run_id?: string
  ticket_id?: number | null
  agent?: AgentName | null
  [key: string]: unknown
}

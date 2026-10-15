import type { AgentName, TicketStatus } from './types'

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export const time = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: 'Open',
  waiting_for_human_approval: 'Waiting for human approval',
  resolved: 'Resolved',
  needs_more_info: 'Needs more info',
  declined: 'Declined',
}

export const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

export const KIND_LABEL: Record<string, string> = {
  invoice_payment: 'Invoice payment',
  rent_payment: 'Rent payment',
  purchase: 'Purchase',
}

/** CSS class suffix for each agent's color. */
export const agentClass = (agent?: string | null) =>
  ({
    Boss: 'boss',
    Inventory: 'inventory',
    Accounting: 'accounting',
    Facilities: 'facilities',
    'Customer Service': 'cs',
  })[agent as AgentName] ?? 'system'

export const AGENT_ROLE: Record<AgentName, string> = {
  Boss: 'Routes tickets, final decision',
  Inventory: 'Stock, shortages, vendors',
  Accounting: 'Cash, invoices, approval requests',
  Facilities: 'Rent and leases',
  'Customer Service': 'Customer drafts (never sent)',
}

/** Short one-line preview of any JSON value. */
export const preview = (value: unknown, max = 140) => {
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  if (!text) return ''
  return text.length > max ? text.slice(0, max - 1) + '…' : text
}

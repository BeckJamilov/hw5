// Thin client for the FastAPI backend. Every number on the dashboard comes from these calls.
import type { ApprovalRequest, AuditEvent, Cash, Run, Ticket, TicketDetails } from './types'

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_URL + path, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_URL}. Is uvicorn running?`)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data)
    throw new ApiError(res.status, detail)
  }
  return data as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  health: () => request<{ ok: boolean; working_db: string; active_run: string | null }>('/api/health'),
  tickets: () => request<{ today: string; tickets: Ticket[] }>('/api/tickets'),
  ticket: (id: number) => request<TicketDetails>(`/api/tickets/${id}`),
  runTicket: (id: number) => post<Run>(`/api/tickets/${id}/run`),
  runs: () => request<{ active_run: string | null; runs: Run[] }>('/api/runs'),
  events: (ticketId: number, after: number) =>
    request<{ total: number; events: AuditEvent[] }>(`/api/events?ticket_id=${ticketId}&after=${after}&limit=500`),
  approvals: () => request<{ approval_requests: ApprovalRequest[] }>('/api/approvals'),
  approve: (id: number, approver: string, note: string) =>
    post<{ ticket_status: string | null }>(`/api/approvals/${id}/approve`, { approver, note, confirm: true }),
  reject: (id: number, approver: string, note: string) =>
    post<{ ticket_status: string | null }>(`/api/approvals/${id}/reject`, { approver, note }),
  cash: () => request<Cash>('/api/cash'),
  reset: () => post<{ reset: boolean }>('/api/reset', { confirm: 'RESET' }),
}

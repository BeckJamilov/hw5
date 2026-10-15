import { useCallback, useEffect, useRef, useState } from 'react'
import { API_URL, api } from './api'
import { ActivityFeed } from './components/ActivityFeed'
import { ApprovalsPanel } from './components/ApprovalsPanel'
import { CashPanel } from './components/CashPanel'
import { SummaryPanel } from './components/SummaryPanel'
import { TicketsPanel } from './components/TicketsPanel'
import type { ApprovalRequest, AuditEvent, Cash, Run, Ticket, TicketDetails } from './types'

const FAST_POLL_MS = 1500 // while agents are working
const SLOW_POLL_MS = 5000 // otherwise
const HIDE_KEY = 'cc-hide-events-before' // audit index of the last reset done from this dashboard

export default function App() {
  const [today, setToday] = useState('')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [details, setDetails] = useState<TicketDetails | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [backendError, setBackendError] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [approver, setApproverState] = useState(() => localStorage.getItem('cc-approver') ?? '')
  const [hideBefore, setHideBefore] = useState(() => Number(localStorage.getItem(HIDE_KEY) ?? -1))
  const lastIndex = useRef(-1)
  const selectedRef = useRef<number | null>(null)

  const setApprover = (name: string) => {
    setApproverState(name)
    localStorage.setItem('cc-approver', name)
  }

  /** Tickets, cash, approvals, and runs: shared by every section. */
  const refreshBoard = useCallback(async () => {
    try {
      const [t, c, a, r] = await Promise.all([api.tickets(), api.cash(), api.approvals(), api.runs()])
      setToday(t.today)
      setTickets(t.tickets)
      setCash(c)
      setApprovals(a.approval_requests)
      setRuns(r.runs)
      setActiveRunId(r.active_run)
      setBackendError(null)
      setSelectedId((id) => id ?? t.tickets[0]?.id ?? null)
    } catch (e) {
      setBackendError((e as Error).message)
    }
  }, [])

  /** Selected ticket's details plus any new audit events since the last poll. */
  const refreshTicket = useCallback(async (id: number) => {
    try {
      const [d, ev] = await Promise.all([api.ticket(id), api.events(id, lastIndex.current)])
      if (selectedRef.current !== id) return // user switched tickets mid-request
      setDetails(d)
      if (ev.events.length) {
        lastIndex.current = ev.events[ev.events.length - 1].index
        setEvents((old) => [...old, ...ev.events])
      }
    } catch (e) {
      setBackendError((e as Error).message)
    }
  }, [])

  // New ticket selected: start its event list from scratch.
  useEffect(() => {
    selectedRef.current = selectedId
    lastIndex.current = -1
    setEvents([])
    setDetails(null)
    if (selectedId !== null) refreshTicket(selectedId)
  }, [selectedId, refreshTicket])

  // Poll fast while a run is active so the activity feed feels live.
  useEffect(() => {
    refreshBoard()
    const timer = setInterval(() => {
      refreshBoard()
      if (selectedRef.current !== null) refreshTicket(selectedRef.current)
    }, activeRunId ? FAST_POLL_MS : SLOW_POLL_MS)
    return () => clearInterval(timer)
  }, [activeRunId, refreshBoard, refreshTicket])

  async function runTicket(id: number) {
    setRunError(null)
    try {
      const run = await api.runTicket(id)
      setActiveRunId(run.run_id)
      await refreshBoard()
    } catch (e) {
      setRunError((e as Error).message)
    }
  }

  async function afterHumanAction() {
    await refreshBoard()
    if (selectedRef.current !== null) await refreshTicket(selectedRef.current)
  }

  async function resetData() {
    if (!window.confirm('Reset the working database to the original data?\nAll approval requests, drafts, decisions and payments in campus_customs_new.db will be replaced. The original database is not touched.')) return
    try {
      await api.reset()
      // The audit trail keeps old runs (append-only); hide them here so the board starts clean.
      const total = selectedRef.current !== null ? (await api.events(selectedRef.current, -1)).total : 0
      const all = Math.max(total, lastIndex.current + 1)
      localStorage.setItem(HIDE_KEY, String(all - 1))
      setHideBefore(all - 1)
      setRunError(null)
      await afterHumanAction()
    } catch (e) {
      setBackendError((e as Error).message)
    }
  }

  const activeRun = runs.find((r) => r.run_id === activeRunId) ?? null
  const lastRun = runs.find((r) => r.ticket_id === selectedId) ?? null
  const visibleEvents = events.filter((e) => e.index > hideBefore)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true" />
          <div>
            <h1>Campus Customs <span className="accent">Agent Desk</span></h1>
            <p className="muted small">Five agents · every payment needs a human · business date {today || '…'}</p>
          </div>
        </div>
        <div className="topbar-right">
          <span className={`conn ${backendError ? 'down' : 'up'}`} title={API_URL}>
            <span className="dot" /> {backendError ? 'Backend offline' : 'Backend connected'}
          </span>
          <button className="btn btn-ghost" onClick={resetData} disabled={!!activeRun || !!backendError}>Reset demo data</button>
        </div>
      </header>

      {backendError && <div className="banner" role="alert">{backendError}</div>}

      <main className="layout">
        <div className="col col-left">
          <TicketsPanel tickets={tickets} selectedId={selectedId} activeRun={activeRun}
            onSelect={setSelectedId} onRun={runTicket} runError={runError} />
        </div>
        <div className="col col-center">
          <SummaryPanel details={details} events={visibleEvents} lastRun={lastRun} />
          <ActivityFeed events={visibleEvents} ticketId={selectedId} running={!!activeRun && activeRun.ticket_id === selectedId} />
        </div>
        <div className="col col-right">
          <CashPanel cash={cash} />
          <ApprovalsPanel approvals={approvals} approver={approver} setApprover={setApprover}
            locked={!!activeRun}
            onApprove={async (r, note) => { await api.approve(r.id, approver.trim(), note); await afterHumanAction() }}
            onReject={async (r, note) => { await api.reject(r.id, approver.trim(), note); await afterHumanAction() }} />
        </div>
      </main>
    </div>
  )
}

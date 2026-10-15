import { STATUS_LABEL, TYPE_LABEL } from '../format'
import type { Run, Ticket } from '../types'

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  activeRun: Run | null
  onSelect: (id: number) => void
  onRun: (id: number) => void
  runError: string | null
}

// Only tickets that still need agent work can be run; this avoids spending tokens re-running
// tickets that are waiting on a human or already closed.
const RUNNABLE = new Set(['open', 'needs_more_info'])

export function TicketsPanel({ tickets, selectedId, activeRun, onSelect, onRun, runError }: Props) {
  return (
    <section className="panel tickets" aria-labelledby="tickets-title">
      <header className="panel-head">
        <h2 id="tickets-title">Tickets</h2>
        <span className="muted small">{tickets.length} total</span>
      </header>

      <ul className="ticket-list">
        {tickets.map((t) => {
          const selected = t.id === selectedId
          const running = activeRun?.ticket_id === t.id
          const pending = (t.approval_counts.pending_human_approval ?? 0) + (t.approval_counts.approved ?? 0)
          return (
            <li key={t.id}>
              <button
                className={`ticket-card ${selected ? 'selected' : ''}`}
                onClick={() => onSelect(t.id)}
                aria-pressed={selected}
              >
                <div className="ticket-top">
                  <span className="ticket-id">#{t.id}</span>
                  <span className={`status status-${t.status}`}>{running ? 'Agents working…' : STATUS_LABEL[t.status]}</span>
                </div>
                <div className="ticket-subject">{t.subject}</div>
                <div className="muted small">
                  {TYPE_LABEL[t.type] ?? t.type} · {t.requester}
                </div>
                {(pending > 0 || t.draft_count > 0) && (
                  <div className="ticket-flags">
                    {pending > 0 && <span className="flag flag-warn">{pending} awaiting approval</span>}
                    {t.draft_count > 0 && <span className="flag">{t.draft_count} draft{t.draft_count > 1 ? 's' : ''}</span>}
                  </div>
                )}
              </button>
              {selected && (
                <div className="ticket-run">
                  <button
                    className="btn btn-primary"
                    disabled={!!activeRun || !RUNNABLE.has(t.status)}
                    onClick={() => onRun(t.id)}
                  >
                    {running ? 'Running…' : 'Run agent team'}
                  </button>
                  <span className="muted small">
                    {activeRun && !running
                      ? `Ticket #${activeRun.ticket_id} is running`
                      : !RUNNABLE.has(t.status)
                        ? 'Already handled by the agents'
                        : 'Boss decides which agents to involve'}
                  </span>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      {runError && <p className="error" role="alert">{runError}</p>}
    </section>
  )
}

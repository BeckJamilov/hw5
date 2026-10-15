import { STATUS_LABEL, TYPE_LABEL, agentClass, money } from '../format'
import type { AuditEvent, Run, TicketDetails } from '../types'

interface Props {
  details: TicketDetails | null
  events: AuditEvent[]
  lastRun: Run | null
}

/** What the agents concluded for the selected ticket: status, Boss's decision, each agent's
 *  report from its last run, and saved customer drafts. All text comes from the API. */
export function SummaryPanel({ details, events, lastRun }: Props) {
  if (!details) {
    return (
      <section className="panel summary"><p className="muted">Select a ticket.</p></section>
    )
  }
  const t = details.ticket
  const decision = details.decisions.at(-1) ?? null
  // Reports from the most recent run of this ticket in the audit trail.
  const lastRunId = [...events].reverse().find((e) => e.event === 'run_start')?.run_id
  const reports = events.filter((e) => e.event === 'agent_end' && e.run_id === lastRunId && e.agent !== 'Boss')
  const runDecision = lastRun?.ticket_id === t.id ? lastRun.decision : null

  return (
    <section className="panel summary" aria-labelledby="summary-title">
      <header className="panel-head">
        <h2 id="summary-title">#{t.id} · {t.subject}</h2>
        <span className={`status status-${t.status}`}>{STATUS_LABEL[t.status]}</span>
      </header>

      <div className="facts-row">
        <span><strong>{TYPE_LABEL[t.type] ?? t.type}</strong> from {t.requester}</span>
        {t.sku && <span>{t.qty} × {t.sku} size {t.size}</span>}
        {details.linked_invoice && (
          <span>Invoice #{details.linked_invoice.id}: {money(details.linked_invoice.amount)}, due {details.linked_invoice.due_date} ({details.linked_invoice.status})</span>
        )}
        {details.linked_lease && (
          <span>Lease #{details.linked_lease.id}: {money(details.linked_lease.monthly_rent)} due {details.linked_lease.next_due}</span>
        )}
      </div>
      {t.notes && <p className="ticket-note">“{t.notes}”</p>}

      {!decision && reports.length === 0 ? (
        <p className="muted">The agents haven't worked on this ticket yet.</p>
      ) : (
        <>
          {decision && (
            <div className={`decision decision-${decision.decision}`}>
              <div className="small muted">Final decision by {decision.decided_by}</div>
              <p>{decision.summary}</p>
            </div>
          )}
          {runDecision && (runDecision.reasons.length > 0 || runDecision.human_next_steps.length > 0) && (
            <div className="two-col">
              {runDecision.reasons.length > 0 && (
                <div>
                  <h3>Why</h3>
                  <ul>{runDecision.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                </div>
              )}
              {runDecision.human_next_steps.length > 0 && (
                <div>
                  <h3>For you to do</h3>
                  <ul>{runDecision.human_next_steps.map((r, i) => <li key={i}>{r}</li>)}</ul>
                </div>
              )}
            </div>
          )}
          {reports.length > 0 && (
            <>
              <h3>What each agent did</h3>
              <ul className="reports">
                {reports.map((e) => {
                  const out = (e.output ?? {}) as { summary?: string }
                  return (
                    <li key={e.index}>
                      <span className={`who agent-${agentClass(e.agent)}`}>{e.agent}</span>
                      <span>{out.summary}</span>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </>
      )}

      {details.message_drafts.length > 0 && (
        <>
          <h3>Customer drafts <span className="muted small">(stay on the board, never emailed)</span></h3>
          {details.message_drafts.map((d) => (
            <article key={d.id} className="draft">
              <div className="small muted">Draft #{d.id} · to {d.recipient} · by {d.prepared_by}</div>
              <strong>{d.subject}</strong>
              <p>{d.body}</p>
            </article>
          ))}
        </>
      )}
    </section>
  )
}

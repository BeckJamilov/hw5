import { useEffect, useRef, useState } from 'react'
import { AGENT_ROLE, agentClass, preview, time } from '../format'
import { AGENTS, type AgentName, type AuditEvent } from '../types'

interface Row {
  who: string // agent name, "Human", or "System"
  title: string
  body?: string
  detail?: unknown // shown in an expandable <details> block
  tone?: 'ok' | 'warn' | 'bad'
  isTool?: boolean
}

const str = (v: unknown) => (typeof v === 'string' ? v : v == null ? '' : JSON.stringify(v))

/** Turn one audit-trail event into a readable row. Only fields from the event are shown. */
function describe(e: AuditEvent): Row {
  const agent = (e.agent as string) || 'System'
  switch (e.event) {
    case 'run_start':
      return { who: 'System', title: `Run started on ${str(e.model)}`, detail: e.limits }
    case 'run_end':
      return { who: 'System', title: `Run ended: ${str(e.status)}`, body: `${str(e.delegations_used)} delegations used`,
        tone: e.status === 'ok' ? 'ok' : 'bad' }
    case 'agent_start':
      return { who: agent, title: 'starts working', body: str(e.prompt) }
    case 'agent_step': {
      const calls = (e.tool_calls as { tool: string }[] | undefined) ?? []
      const text = str(e.text)
      return { who: agent, title: text ? 'says' : 'decides to call tools',
        body: text || calls.map((c) => c.tool).join(', '), detail: calls.length ? calls : undefined }
    }
    case 'delegation': {
      const status = str(e.status)
      const verb = status === 'blocked' ? 'tried to delegate to' : status === 'started' ? 'delegates to' : `delegation ${status}:`
      return { who: str(e.from_agent), title: `${verb} ${str(e.to_agent)}`,
        body: status === 'blocked' ? str(e.reason) : status === 'started' ? str(e.task) : str(e.error) || undefined,
        tone: status === 'blocked' || status === 'failed' ? 'warn' : undefined }
    }
    case 'tool_call':
      return { who: agent, title: `calls ${str(e.tool)}`, body: preview(e.args), detail: e.args, isTool: true }
    case 'tool_result':
      return { who: agent, title: `${str(e.tool)} returned`, body: preview(e.result), detail: e.result, isTool: true, tone: 'ok' }
    case 'tool_error':
      return { who: agent, title: `${str(e.tool)} refused`, body: str(e.error), tone: 'bad' }
    case 'agent_end': {
      const out = (e.output ?? {}) as Record<string, unknown>
      const label = out.decision ? `final decision: ${str(out.decision)}` : 'reports back'
      return { who: agent, title: label, body: str(out.summary), detail: out, tone: 'ok' }
    }
    case 'limit_reached':
      return { who: agent, title: 'hit a usage limit', body: str(e.error), tone: 'bad' }
    case 'error':
      return { who: agent, title: 'error', body: str(e.error), tone: 'bad' }
    case 'human_action':
      return { who: 'Human', title: `${str(e.human)}: ${str(e.action)} request #${str(e.request_id)}`,
        body: str(e.status) === 'ok' ? 'done' : str(e.error), tone: str(e.status) === 'ok' ? 'ok' : 'bad' }
    default:
      return { who: agent, title: e.event, detail: e }
  }
}

export function ActivityFeed({ events, ticketId, running }: { events: AuditEvent[]; ticketId: number | null; running: boolean }) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [showTools, setShowTools] = useState(true)
  const listRef = useRef<HTMLOListElement>(null)

  const rows = events.map((e) => ({ e, row: describe(e) }))
    .filter(({ row }) => !hidden.has(row.who) && (showTools || !row.isTool))

  // Keep the newest events in view while a run is streaming in.
  useEffect(() => {
    const el = listRef.current
    if (el && running) el.scrollTop = el.scrollHeight
  }, [events.length, running])

  const toggle = (name: string) => {
    const next = new Set(hidden)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setHidden(next)
  }
  const counts = (name: AgentName) => events.filter((e) => e.agent === name || e.from_agent === name).length

  return (
    <section className="panel activity" aria-labelledby="activity-title">
      <header className="panel-head">
        <h2 id="activity-title">Agent activity {ticketId ? <span className="muted">· ticket #{ticketId}</span> : null}</h2>
        {running && <span className="live"><span className="dot" /> live</span>}
      </header>

      <div className="legend" role="group" aria-label="Show or hide agents">
        {AGENTS.map((a) => (
          <button key={a} className={`agent-chip agent-${agentClass(a)} ${hidden.has(a) ? 'off' : ''}`}
            onClick={() => toggle(a)} title={AGENT_ROLE[a]} aria-pressed={!hidden.has(a)}>
            {a} <span className="chip-count">{counts(a)}</span>
          </button>
        ))}
        <label className="tool-toggle small">
          <input type="checkbox" checked={showTools} onChange={(e) => setShowTools(e.target.checked)} /> tool calls
        </label>
      </div>

      {events.length === 0 ? (
        <div className="empty-state">
          <p>No agent activity for this ticket yet.</p>
          <p className="muted small">Press <strong>Run agent team</strong> to start. Every step the agents take appears here, read live from <code>output/audit_trail.json</code>.</p>
        </div>
      ) : (
        <ol className="feed" ref={listRef}>
          {rows.map(({ e, row }) => (
            <li key={e.index} className={`event agent-${agentClass(row.who)} ${row.isTool ? 'is-tool' : ''} ${row.tone ? 'tone-' + row.tone : ''}`}>
              <div className="event-head">
                <span className={`who agent-${agentClass(row.who)}`}>{row.who}</span>
                <span className="event-title">{row.title}</span>
                <time className="muted small">{time(e.time)}</time>
              </div>
              {row.body && <p className="event-body">{row.body}</p>}
              {row.detail !== undefined && (
                <details>
                  <summary className="small muted">details</summary>
                  <pre>{JSON.stringify(row.detail, null, 2)}</pre>
                </details>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

import { useState } from 'react'
import { KIND_LABEL, money } from '../format'
import type { ApprovalRequest } from '../types'

interface Props {
  approvals: ApprovalRequest[]
  approver: string
  setApprover: (name: string) => void
  onApprove: (req: ApprovalRequest, note: string) => Promise<void>
  onReject: (req: ApprovalRequest, note: string) => Promise<void>
  locked: boolean
}

function describe(r: ApprovalRequest) {
  if (r.kind === 'invoice_payment') return `Pay invoice #${r.ref_id}`
  if (r.kind === 'rent_payment') return `Pay rent, lease #${r.ref_id}${r.period_due ? ` (due ${r.period_due})` : ''}`
  return `Buy ${r.qty} × ${r.sku} ${r.size} from vendor #${r.ref_id}`
}

export function ApprovalsPanel({ approvals, approver, setApprover, onApprove, onReject, locked }: Props) {
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notes, setNotes] = useState<Record<number, string>>({})
  const named = approver.trim().length > 0

  async function act(req: ApprovalRequest, kind: 'approve' | 'reject') {
    const verb = kind === 'approve' ? `APPROVE and PAY ${money(req.amount)}` : 'REJECT'
    if (!window.confirm(`${verb} for request #${req.id}?\n${describe(req)}\nApprover: ${approver.trim()}`)) return
    setBusy(req.id)
    setError(null)
    try {
      await (kind === 'approve' ? onApprove : onReject)(req, notes[req.id] ?? '')
    } catch (e) {
      setError(`Request #${req.id}: ${(e as Error).message}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="panel approvals" aria-labelledby="approvals-title">
      <header className="panel-head">
        <h2 id="approvals-title">Approvals</h2>
        <span className="count-badge">{approvals.length}</span>
      </header>

      <label className="field">
        <span className="small muted">Your name (recorded as the approver)</span>
        <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="e.g. Store manager" maxLength={100} />
      </label>

      {approvals.length === 0 ? (
        <p className="muted empty">No payments or purchases are waiting for approval.</p>
      ) : (
        <ul className="approval-list">
          {approvals.map((r) => (
            <li key={r.id} className="approval">
              <div className="approval-top">
                <span className={`kind kind-${r.kind}`}>{KIND_LABEL[r.kind] ?? r.kind}</span>
                <span className="amount">{money(r.amount)}</span>
              </div>
              <div className="approval-what">{describe(r)}</div>
              <div className="muted small">
                Ticket #{r.ticket_id} · request #{r.id} · prepared by {r.requested_by}
              </div>
              <p className="approval-reason">{r.reason}</p>
              <input
                className="note"
                placeholder="Note (optional)"
                value={notes[r.id] ?? ''}
                onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
                maxLength={500}
              />
              <div className="approval-actions">
                <button className="btn btn-approve" disabled={!named || locked || busy !== null} onClick={() => act(r, 'approve')}>
                  {busy === r.id ? 'Working…' : 'Approve & pay'}
                </button>
                <button className="btn btn-reject" disabled={!named || locked || busy !== null} onClick={() => act(r, 'reject')}>
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {!named && approvals.length > 0 && <p className="muted small">Enter your name to approve or reject.</p>}
      {locked && approvals.length > 0 && <p className="muted small">Approvals unlock when the agent run finishes.</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  )
}

import { useEffect, useRef, useState } from 'react'
import { money } from '../format'
import type { Cash } from '../types'

export function CashPanel({ cash }: { cash: Cash | null }) {
  // Briefly highlight the balance when a payment changes it.
  const [flash, setFlash] = useState(false)
  const last = useRef<number | null>(null)
  const balance = cash?.balance
  useEffect(() => {
    if (balance === undefined) return
    const changed = last.current !== null && last.current !== balance
    last.current = balance
    if (!changed) return
    setFlash(true)
    const t = setTimeout(() => setFlash(false), 1600)
    return () => clearTimeout(t)
  }, [balance])

  return (
    <section className="panel cash" aria-labelledby="cash-title">
      <header className="panel-head">
        <h2 id="cash-title">Cash</h2>
        {cash && <span className="muted small">as of {cash.as_of}</span>}
      </header>
      {!cash ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          <div className="muted small">Checking balance</div>
          <div className={`balance ${flash ? 'flash' : ''}`} aria-live="polite">{money(cash.balance)}</div>
          <dl className="cash-rows">
            <div>
              <dt>Promised to open requests</dt>
              <dd>{money(cash.committed_to_open_requests)}</dd>
            </div>
            <div>
              <dt>Available</dt>
              <dd className={cash.available_cash < 500 ? 'warn' : 'ok'}>{money(cash.available_cash)}</dd>
            </div>
            <div>
              <dt>After all open bills</dt>
              <dd className={cash.cash_after_all_open_bills < 500 ? 'warn' : ''}>{money(cash.cash_after_all_open_bills)}</dd>
            </div>
          </dl>
          <p className="muted small">Cash only changes when a human approves a payment. It can never go below $0.</p>
        </>
      )}
    </section>
  )
}

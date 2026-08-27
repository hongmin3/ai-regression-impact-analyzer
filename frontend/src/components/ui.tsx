import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'

// --------------------------------------------------------------------------- //
// formatting helpers
// --------------------------------------------------------------------------- //
export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return '-'
  // Date-only values must not be shifted by the local timezone.
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function fmtBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${value.toFixed(value >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

export function initials(name: string): string {
  const trimmed = (name || '').trim()
  if (!trimmed) return '?'
  // Korean names read best as the last two characters of the given name.
  if (/[가-힣]/.test(trimmed)) return trimmed.slice(-2)
  const parts = trimmed.split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// --------------------------------------------------------------------------- //
// primitives
// --------------------------------------------------------------------------- //
export function Alert({
  kind,
  children,
  onClose,
}: {
  kind: 'error' | 'warn' | 'ok' | 'info'
  children: ReactNode
  onClose?: () => void
}) {
  const icon = { error: '!', warn: '!', ok: '✓', info: 'i' }[kind]
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <span className="alert-icon">{icon}</span>
      <div style={{ flex: 1 }}>{children}</div>
      {onClose && (
        <button type="button" className="modal-close" onClick={onClose} aria-label="닫기">
          ×
        </button>
      )}
    </div>
  )
}

export function Card({
  title,
  sub,
  actions,
  flush,
  children,
}: {
  title?: string
  sub?: string
  actions?: ReactNode
  flush?: boolean
  children: ReactNode
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="card-head">
          <h2>
            {title} {sub && <span className="sub">{sub}</span>}
          </h2>
          {actions && <div className="btn-row">{actions}</div>}
        </div>
      )}
      <div className={flush ? 'card-body flush' : 'card-body'}>{children}</div>
    </section>
  )
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string
  value: ReactNode
  hint?: string
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children}
    </div>
  )
}

export function Loading({ label = '불러오는 중...' }: { label?: string }) {
  return <div className="loading">{label}</div>
}

export function CurrentBadge({ isCurrent }: { isCurrent: boolean }) {
  return isCurrent ? (
    <span className="badge badge-current">CURRENT</span>
  ) : (
    <span className="badge badge-history">HISTORY</span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  if (status === 'archived') return <span className="badge badge-archived">ARCHIVED</span>
  return <span className="badge badge-active">ACTIVE</span>
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  // Escape closes; focus moves into the dialog so keyboard users are not left
  // behind on the page underneath.
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    ref.current?.querySelector<HTMLElement>(
      'input, select, textarea, button',
    )?.focus()
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        className={wide ? 'modal modal-wide' : 'modal'}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
      >
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="닫기">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={className ? `field ${className}` : 'field'}>
      <span>{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  )
}

/** A form whose submit handler is async and whose errors surface inline. */
export function useAsyncAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(fn: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof Error ? e.message : '요청이 실패했습니다.')
      throw e
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(fn: () => Promise<void>) {
    return (e: FormEvent) => {
      e.preventDefault()
      void run(fn).catch(() => undefined)
    }
  }

  return { busy, error, setError, run, onSubmit }
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = '확인',
  danger,
  onConfirm,
  onCancel,
  busy,
}: {
  title: string
  message: ReactNode
  confirmLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
  busy?: boolean
}) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel} disabled={busy}>
            취소
          </button>
          <button
            type="button"
            className={danger ? 'btn-danger' : 'btn-primary'}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? '처리 중...' : confirmLabel}
          </button>
        </>
      }
    >
      {message}
    </Modal>
  )
}

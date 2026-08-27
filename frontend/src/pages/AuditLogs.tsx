import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  Alert,
  Card,
  Empty,
  Field,
  Loading,
  Modal,
  fmtDateTime,
} from '../components/ui'
import type { AuditRow } from '../types'

const PAGE = 100

export default function AuditLogs() {
  const [rows, setRows] = useState<AuditRow[] | null>(null)
  const [actions, setActions] = useState<Record<string, string>>({})
  const [action, setAction] = useState('')
  const [actor, setActor] = useState('')
  const [q, setQ] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [detail, setDetail] = useState<AuditRow | null>(null)

  useEffect(() => {
    api.auditActions().then(setActions).catch(() => undefined)
  }, [])

  const load = useCallback(() => {
    setError(null)
    api
      .auditLogs({
        action: action || undefined,
        actor: actor.trim() || undefined,
        q: q.trim() || undefined,
        date_from: from || undefined,
        date_to: to || undefined,
        limit: PAGE,
        offset,
      })
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [action, actor, q, from, to, offset])

  useEffect(load, [load])

  // Any filter change starts a fresh page.
  useEffect(() => setOffset(0), [action, actor, q, from, to])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Audit Logs</h1>
          <div className="desc">
            로그인, 사용자 관리, 문서·버전 변경, Current 변경, 다운로드 기록. 수정·삭제 기능은
            제공하지 않습니다.
          </div>
        </div>
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      <Card>
        <div className="filter-bar">
          <Field label="Action">
            <select value={action} onChange={(e) => setAction(e.target.value)}>
              <option value="">전체</option>
              {Object.entries(actions).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="사용자">
            <input
              type="search"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              placeholder="이름 또는 ID"
            />
          </Field>
          <Field label="대상 검색" className="grow">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="제품/문서/버전/상세"
            />
          </Field>
          <Field label="From">
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="To">
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
          <button
            type="button"
            onClick={() => {
              setAction('')
              setActor('')
              setQ('')
              setFrom('')
              setTo('')
            }}
          >
            초기화
          </button>
        </div>
      </Card>

      <Card
        title="기록"
        sub={rows ? `${offset + 1}–${offset + rows.length}` : undefined}
        actions={
          <>
            <button
              type="button"
              className="btn-sm"
              disabled={offset === 0}
              onClick={() => setOffset((o) => Math.max(0, o - PAGE))}
            >
              이전
            </button>
            <button
              type="button"
              className="btn-sm"
              disabled={!rows || rows.length < PAGE}
              onClick={() => setOffset((o) => o + PAGE)}
            >
              다음
            </button>
          </>
        }
        flush
      >
        {!rows ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty title="조건에 맞는 기록이 없습니다" />
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>User</th>
                  <th>Product</th>
                  <th className="wrap">Document</th>
                  <th>Version</th>
                  <th className="wrap">Detail</th>
                  <th>IP</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="faint small nowrap">{fmtDateTime(r.created_at)}</td>
                    <td className="nowrap">{r.action_label}</td>
                    <td>
                      <div className="stack">
                        <span>{r.actor_display_name ?? '-'}</span>
                        <span className="faint small mono">{r.actor_login_id ?? ''}</span>
                      </div>
                    </td>
                    <td className="faint">{r.product_name ?? '-'}</td>
                    <td className="wrap">{r.document_name ?? r.target_label ?? '-'}</td>
                    <td>
                      {r.version_label ? <span className="rev">{r.version_label}</span> : '-'}
                    </td>
                    <td className="wrap faint small">{r.detail ?? '-'}</td>
                    <td className="mono small faint">{r.ip_address ?? '-'}</td>
                    <td>
                      {(r.before_value || r.after_value) && (
                        <button type="button" className="btn-sm" onClick={() => setDetail(r)}>
                          변경내역
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {detail && (
        <Modal
          title={`${detail.action_label} — ${fmtDateTime(detail.created_at)}`}
          onClose={() => setDetail(null)}
          wide
          footer={
            <button type="button" onClick={() => setDetail(null)}>
              닫기
            </button>
          }
        >
          <div className="meta-grid" style={{ marginBottom: 16 }}>
            <div className="meta-item">
              <div className="k">User</div>
              <div className="v">
                {detail.actor_display_name ?? '-'}{' '}
                <span className="faint small">({detail.actor_login_id ?? '-'})</span>
              </div>
            </div>
            <div className="meta-item">
              <div className="k">IP Address</div>
              <div className="v mono">{detail.ip_address ?? '-'}</div>
            </div>
            <div className="meta-item">
              <div className="k">Target</div>
              <div className="v">
                {[detail.product_name, detail.document_name, detail.version_label]
                  .filter(Boolean)
                  .join(' / ') ||
                  detail.target_label ||
                  '-'}
              </div>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 14,
            }}
          >
            <div>
              <div className="k faint small" style={{ marginBottom: 5 }}>
                BEFORE
              </div>
              <pre className="kv-json">
                {detail.before_value ? JSON.stringify(detail.before_value, null, 2) : '-'}
              </pre>
            </div>
            <div>
              <div className="k faint small" style={{ marginBottom: 5 }}>
                AFTER
              </div>
              <pre className="kv-json">
                {detail.after_value ? JSON.stringify(detail.after_value, null, 2) : '-'}
              </pre>
            </div>
          </div>

          {detail.detail && (
            <div className="revdesc" style={{ marginTop: 14 }}>
              <span className="k">Detail</span>
              {detail.detail}
            </div>
          )}
        </Modal>
      )}
    </>
  )
}

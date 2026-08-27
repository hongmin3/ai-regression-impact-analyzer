import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import {
  Alert,
  Card,
  CurrentBadge,
  Empty,
  Field,
  Loading,
  fmtBytes,
  fmtDateTime,
  initials,
  useAsyncAction,
} from '../components/ui'
import type { AppSettings, RecentUpload } from '../types'

// --------------------------------------------------------------------------- //
// Recent Updates
// --------------------------------------------------------------------------- //
export function RecentUpdates() {
  const [rows, setRows] = useState<RecentUpload[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .recentUpdates(100)
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Recent Updates</h1>
          <div className="desc">최근 업로드된 버전 100건 (최신순)</div>
        </div>
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      <Card flush>
        {!rows ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty title="업로드 기록이 없습니다" />
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Upload Date</th>
                  <th>Product</th>
                  <th className="wrap">Document</th>
                  <th>Revision / Version</th>
                  <th>Uploaded By</th>
                  <th></th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.version_id}>
                    <td className="faint nowrap">{fmtDateTime(r.upload_date)}</td>
                    <td>
                      <Link to={`/products/${r.product_id}`}>{r.product_name}</Link>
                    </td>
                    <td className="wrap">
                      <Link className="doc-link" to={`/documents/${r.document_id}`}>
                        {r.document_name}
                      </Link>
                    </td>
                    <td>
                      <span className="rev">{r.version_label}</span>
                    </td>
                    <td>{r.uploaded_by_display_name}</td>
                    <td>
                      <CurrentBadge isCurrent={r.is_current} />
                    </td>
                    <td>
                      <a
                        className="btn btn-sm"
                        href={api.downloadUrl(r.document_id, r.version_id)}
                      >
                        다운로드
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

// --------------------------------------------------------------------------- //
// My Account
// --------------------------------------------------------------------------- //
export function MyAccount() {
  const { user, refresh } = useAuth()
  const [params] = useSearchParams()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState<string | null>(null)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const { busy, error, setError, onSubmit } = useAsyncAction()

  useEffect(() => {
    api.settings().then(setSettings).catch(() => undefined)
  }, [])

  const forced = user?.must_change_password || params.get('change') === '1'

  const submit = onSubmit(async () => {
    if (next !== confirm) {
      setError('새 비밀번호가 서로 일치하지 않습니다.')
      throw new Error('mismatch')
    }
    await api.changePassword(current, next)
    setCurrent('')
    setNext('')
    setConfirm('')
    setDone('비밀번호가 변경되었습니다.')
    await refresh()
  })

  if (!user) return null

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My Account</h1>
          <div className="desc">내 계정 정보와 비밀번호 변경</div>
        </div>
      </div>

      <Card title="계정 정보">
        <div className="inline" style={{ gap: 14, marginBottom: 14 }}>
          <span className="avatar" style={{ width: 40, height: 40, fontSize: 15 }}>
            {initials(user.display_name)}
          </span>
          <div className="stack">
            <strong style={{ fontSize: 15 }}>{user.display_name}</strong>
            <span className="faint small mono">{user.login_id}</span>
          </div>
        </div>
        <div className="meta-grid">
          <div className="meta-item">
            <div className="k">Role</div>
            <div className="v">
              <span className={user.is_admin ? 'badge badge-admin' : 'badge badge-user'}>
                {user.is_admin ? 'ADMIN' : 'USER'}
              </span>
            </div>
          </div>
          <div className="meta-item">
            <div className="k">Status</div>
            <div className="v">
              <span className="badge badge-active">ACTIVE</span>
            </div>
          </div>
          <div className="meta-item">
            <div className="k">Last Login</div>
            <div className="v">{fmtDateTime(user.last_login_at)}</div>
          </div>
          <div className="meta-item">
            <div className="k">Created</div>
            <div className="v">{fmtDateTime(user.created_at)}</div>
          </div>
        </div>
        <p className="small faint" style={{ marginTop: 12, marginBottom: 0 }}>
          Login ID 와 표시 이름 변경은 관리자에게 요청하세요.
        </p>
      </Card>

      <Card title="비밀번호 변경">
        {forced && user.must_change_password && (
          <Alert kind="warn">
            임시 비밀번호로 로그인한 상태입니다. 비밀번호를 변경해야 문서 등록·수정 기능을 사용할
            수 있습니다.
          </Alert>
        )}
        {done && <Alert kind="ok" onClose={() => setDone(null)}>{done}</Alert>}
        {error && <Alert kind="error">{error}</Alert>}
        <form onSubmit={submit} style={{ maxWidth: 420 }}>
          <Field label="현재 비밀번호 *">
            <input
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              autoComplete="current-password"
              required
            />
          </Field>
          <Field
            label="새 비밀번호 *"
            hint={`최소 ${settings?.password_min_length ?? 8}자`}
          >
            <input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              minLength={settings?.password_min_length ?? 8}
              autoComplete="new-password"
              required
            />
          </Field>
          <Field label="새 비밀번호 확인 *">
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              required
            />
          </Field>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? '변경 중...' : '비밀번호 변경'}
          </button>
        </form>
      </Card>
    </>
  )
}

// --------------------------------------------------------------------------- //
// Settings (read-only view of the effective server configuration)
// --------------------------------------------------------------------------- //
export function Settings() {
  const { user } = useAuth()
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .settings()
      .then(setSettings)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [])

  if (error) return <Alert kind="error">{error}</Alert>
  if (!settings) return <Loading />

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <div className="desc">현재 서버에 적용된 설정값</div>
        </div>
      </div>

      <Card title="업로드">
        <div className="meta-grid">
          <div className="meta-item">
            <div className="k">최대 파일 크기</div>
            <div className="v">
              {settings.max_upload_mb} MB
              <span className="faint small"> ({fmtBytes(settings.max_upload_mb * 1024 * 1024)})</span>
            </div>
          </div>
          <div className="meta-item">
            <div className="k">허용 확장자</div>
            <div className="v mono">{settings.allowed_extensions.join(', ')}</div>
          </div>
        </div>
      </Card>

      <Card title="저장소">
        <div className="meta-grid">
          <div className="meta-item">
            <div className="k">Storage Backend</div>
            <div className="v mono">{settings.storage_backend}</div>
          </div>
          <div className="meta-item">
            <div className="k">Storage Root</div>
            <div className="v mono">{settings.storage_root}</div>
          </div>
        </div>
        <p className="small faint" style={{ marginTop: 10, marginBottom: 0 }}>
          모든 문서는 중앙 서버에 실제 복사되어 보관됩니다. 저장 경로는{' '}
          <span className="mono">product/document/version/file</span> UUID 구조이며 원본 파일명은
          DB 메타데이터로 보존됩니다.
        </p>
      </Card>

      <Card title="인증">
        <div className="meta-grid">
          <div className="meta-item">
            <div className="k">Session 유효 시간</div>
            <div className="v">{settings.session_lifetime_hours} 시간</div>
          </div>
          <div className="meta-item">
            <div className="k">비밀번호 최소 길이</div>
            <div className="v">{settings.password_min_length} 자</div>
          </div>
          <div className="meta-item">
            <div className="k">Password Hash</div>
            <div className="v">Argon2id</div>
          </div>
        </div>
      </Card>

      <Card title="애플리케이션">
        <div className="meta-grid">
          <div className="meta-item">
            <div className="k">Version</div>
            <div className="v mono">{settings.app_version}</div>
          </div>
          <div className="meta-item">
            <div className="k">API 문서</div>
            <div className="v">
              <a href="/api/docs" target="_blank" rel="noreferrer">
                /api/docs
              </a>
            </div>
          </div>
        </div>
        <p className="small faint" style={{ marginTop: 10, marginBottom: 0 }}>
          이 값들은 서버의 환경설정 파일에서 관리됩니다.
          {user?.is_admin
            ? ' 변경이 필요하면 서버 관리자에게 요청하세요 (설정 변경 후 서비스 재시작 필요).'
            : ''}
        </p>
      </Card>
    </>
  )
}

// --------------------------------------------------------------------------- //
export function NotFound() {
  return (
    <Card>
      <Empty title="페이지를 찾을 수 없습니다">
        <Link to="/">Dashboard 로 이동</Link>
      </Empty>
    </Card>
  )
}

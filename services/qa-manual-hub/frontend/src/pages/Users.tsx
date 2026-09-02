import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import {
  Alert,
  Card,
  ConfirmDialog,
  Empty,
  Field,
  Loading,
  Modal,
  fmtDateTime,
  useAsyncAction,
} from '../components/ui'
import type { UserRow } from '../types'

/** The server owns the password policy; the forms only mirror it. */
function usePasswordMinLength(): number {
  const [minLength, setMinLength] = useState(1)
  useEffect(() => {
    api
      .settings()
      .then((s) => setMinLength(Math.max(1, s.password_min_length)))
      .catch(() => undefined)
  }, [])
  return minLength
}

function passwordHint(minLength: number): string {
  return minLength > 1 ? `최소 ${minLength}자.` : '길이 제한 없음.'
}

export default function Users() {
  const { user: me } = useAuth()
  const [rows, setRows] = useState<UserRow[] | null>(null)
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<UserRow | null>(null)
  const [resetting, setResetting] = useState<UserRow | null>(null)
  const [confirm, setConfirm] = useState<{
    title: string
    message: string
    label: string
    danger?: boolean
    run: () => Promise<void>
  } | null>(null)

  const load = useCallback(() => {
    setError(null)
    api
      .users({ q: q.trim() || undefined })
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [q])

  useEffect(load, [load])

  async function act(fn: () => Promise<void>, message: string) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await fn()
      load()
      setNotice(message)
    } catch (e) {
      setError(e instanceof Error ? e.message : '요청이 실패했습니다.')
    } finally {
      setBusy(false)
      setConfirm(null)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Users</h1>
          <div className="desc">
            관리자 전용. 계정 생성, 비밀번호 초기화, 활성/비활성, 권한 변경을 처리합니다.
          </div>
        </div>
        <div className="head-actions">
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            + 사용자 추가
          </button>
        </div>
      </div>

      {error && <Alert kind="error" onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="ok" onClose={() => setNotice(null)}>{notice}</Alert>}

      <Card>
        <div className="filter-bar">
          <Field label="검색" className="grow">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="로그인 ID 또는 이름"
            />
          </Field>
        </div>
      </Card>

      <Card title="사용자 목록" sub={rows ? `${rows.length}명` : undefined} flush>
        {!rows ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty title="조건에 맞는 사용자가 없습니다" />
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Login ID</th>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Login</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => {
                  const isSelf = u.id === me?.id
                  return (
                    <tr key={u.id} className={u.is_active ? undefined : 'row-archived'}>
                      <td className="mono">{u.login_id}</td>
                      <td>
                        <div className="stack">
                          <span style={{ fontWeight: 600 }}>{u.display_name}</span>
                          {isSelf && <span className="faint small">본인 계정</span>}
                          {u.must_change_password && (
                            <span className="faint small">최초 로그인 시 비밀번호 변경 필요</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span className={u.role === 'admin' ? 'badge badge-admin' : 'badge badge-user'}>
                          {u.role === 'admin' ? 'ADMIN' : 'USER'}
                        </span>
                      </td>
                      <td>
                        <span className={u.is_active ? 'badge badge-active' : 'badge badge-inactive'}>
                          {u.is_active ? 'ACTIVE' : 'DISABLED'}
                        </span>
                      </td>
                      <td className="faint">{fmtDateTime(u.last_login_at)}</td>
                      <td className="faint small">{fmtDateTime(u.created_at)}</td>
                      <td>
                        <div className="btn-row">
                          <button type="button" className="btn-sm" onClick={() => setEditing(u)}>
                            수정
                          </button>
                          <button type="button" className="btn-sm" onClick={() => setResetting(u)}>
                            비밀번호 초기화
                          </button>
                          {u.is_active ? (
                            <button
                              type="button"
                              className="btn-sm btn-danger"
                              disabled={busy || isSelf}
                              title={isSelf ? '자신의 계정은 비활성화할 수 없습니다.' : undefined}
                              onClick={() =>
                                setConfirm({
                                  title: '사용자 비활성화',
                                  message: `${u.display_name}(${u.login_id}) 계정을 비활성화합니다. 즉시 로그인이 차단되고 열려 있는 세션도 종료됩니다.`,
                                  label: '비활성화',
                                  danger: true,
                                  run: () =>
                                    act(async () => {
                                      await api.updateUser(u.id, { is_active: false })
                                    }, `${u.display_name} 계정을 비활성화했습니다.`),
                                })
                              }
                            >
                              비활성화
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn-sm"
                              disabled={busy}
                              onClick={() =>
                                act(async () => {
                                  await api.updateUser(u.id, { is_active: true })
                                }, `${u.display_name} 계정을 활성화했습니다.`)
                              }
                            >
                              활성화
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {creating && (
        <UserForm
          onClose={() => setCreating(false)}
          onSaved={(name) => {
            setCreating(false)
            load()
            setNotice(`${name} 계정을 생성했습니다.`)
          }}
        />
      )}
      {editing && (
        <UserEditForm
          user={editing}
          isSelf={editing.id === me?.id}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            load()
            setNotice('사용자 정보를 수정했습니다.')
          }}
        />
      )}
      {resetting && (
        <ResetPasswordForm
          user={resetting}
          onClose={() => setResetting(null)}
          onSaved={(msg) => {
            setResetting(null)
            load()
            setNotice(msg)
          }}
        />
      )}
      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.label}
          danger={confirm.danger}
          busy={busy}
          onCancel={() => setConfirm(null)}
          onConfirm={() => void confirm.run()}
        />
      )}
    </>
  )
}

function UserForm({
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: (displayName: string) => void
}) {
  const [loginId, setLoginId] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('user')
  const [mustChange, setMustChange] = useState(true)
  const minLength = usePasswordMinLength()
  const { busy, error, onSubmit } = useAsyncAction()

  const submit = onSubmit(async () => {
    await api.createUser({
      login_id: loginId.trim(),
      display_name: displayName.trim(),
      password,
      role,
      must_change_password: mustChange,
    })
    onSaved(displayName.trim())
  })

  return (
    <Modal
      title="사용자 추가"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={busy}>
            취소
          </button>
          <button type="submit" form="user-form" className="btn-primary" disabled={busy}>
            {busy ? '생성 중...' : '생성'}
          </button>
        </>
      }
    >
      <form id="user-form" onSubmit={submit}>
        {error && <Alert kind="error">{error}</Alert>}
        <div className="form-grid">
          <Field label="Login ID *" hint="영문/숫자/. _ - 만 사용. 나중에 변경할 수 없습니다.">
            <input
              type="text"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              pattern="[A-Za-z0-9._\-]+"
              minLength={2}
              maxLength={64}
              required
              autoComplete="off"
            />
          </Field>
          <Field label="사용자 이름 *" hint="예: 홍길동. 업로더 이름으로 표시됩니다.">
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={128}
              required
            />
          </Field>
        </div>
        <div className="form-grid">
          <Field
            label="초기 Password *"
            hint={`${passwordHint(minLength)} 사용자에게 별도로 전달하세요.`}
          >
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={minLength}
              maxLength={256}
              required
              autoComplete="new-password"
            />
          </Field>
          <Field label="Role">
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="user">User — 문서 관리 전체 가능</option>
              <option value="admin">Admin — 사용자·제품·분류 관리 추가</option>
            </select>
          </Field>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={mustChange}
            onChange={(e) => setMustChange(e.target.checked)}
          />
          최초 로그인 시 비밀번호 변경 요구 (권장)
        </label>
      </form>
    </Modal>
  )
}

function UserEditForm({
  user,
  isSelf,
  onClose,
  onSaved,
}: {
  user: UserRow
  isSelf: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const [displayName, setDisplayName] = useState(user.display_name)
  const [role, setRole] = useState(user.role)
  const [mustChange, setMustChange] = useState(user.must_change_password)
  const { busy, error, onSubmit } = useAsyncAction()

  const submit = onSubmit(async () => {
    await api.updateUser(user.id, {
      display_name: displayName.trim(),
      role,
      must_change_password: mustChange,
    })
    onSaved()
  })

  return (
    <Modal
      title={`사용자 수정 — ${user.login_id}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={busy}>
            취소
          </button>
          <button type="submit" form="user-edit" className="btn-primary" disabled={busy}>
            {busy ? '저장 중...' : '저장'}
          </button>
        </>
      }
    >
      <form id="user-edit" onSubmit={submit}>
        {error && <Alert kind="error">{error}</Alert>}
        <Field label="Login ID" hint="로그인 ID는 변경할 수 없습니다.">
          <input type="text" value={user.login_id} disabled />
        </Field>
        <Field
          label="사용자 이름"
          hint="이름을 바꿔도 과거 업로드 기록의 업로더 이름은 당시 값으로 보존됩니다."
        >
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={128}
            required
          />
        </Field>
        <Field label="Role">
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            disabled={isSelf}
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </Field>
        {isSelf && (
          <Alert kind="info">
            본인 계정의 관리자 권한은 해제할 수 없습니다. 다른 관리자에게 요청하세요.
          </Alert>
        )}
        <label className="check">
          <input
            type="checkbox"
            checked={mustChange}
            onChange={(e) => setMustChange(e.target.checked)}
          />
          다음 로그인 시 비밀번호 변경 요구
        </label>
      </form>
    </Modal>
  )
}

function ResetPasswordForm({
  user,
  onClose,
  onSaved,
}: {
  user: UserRow
  onClose: () => void
  onSaved: (message: string) => void
}) {
  const [password, setPassword] = useState('')
  const [mustChange, setMustChange] = useState(true)
  const minLength = usePasswordMinLength()
  const { busy, error, onSubmit } = useAsyncAction()

  const submit = onSubmit(async () => {
    const result = await api.resetPassword(user.id, password, mustChange)
    onSaved(result.detail)
  })

  return (
    <Modal
      title={`비밀번호 초기화 — ${user.display_name}(${user.login_id})`}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={busy}>
            취소
          </button>
          <button type="submit" form="pw-reset" className="btn-primary" disabled={busy}>
            {busy ? '처리 중...' : '초기화'}
          </button>
        </>
      }
    >
      <form id="pw-reset" onSubmit={submit}>
        {error && <Alert kind="error">{error}</Alert>}
        <Alert kind="warn">
          초기화하면 이 사용자의 열려 있는 모든 세션이 즉시 종료됩니다. 임시 비밀번호는 별도
          경로(사내 메신저 등)로 직접 전달하세요.
        </Alert>
        <Field label="임시 Password *" hint={passwordHint(minLength)}>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={minLength}
            maxLength={256}
            required
            autoComplete="new-password"
          />
        </Field>
        <label className="check">
          <input
            type="checkbox"
            checked={mustChange}
            onChange={(e) => setMustChange(e.target.checked)}
          />
          최초 로그인 시 비밀번호 변경 요구 (권장)
        </label>
      </form>
    </Modal>
  )
}

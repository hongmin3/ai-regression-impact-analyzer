import { useState } from 'react'
import { useAuth } from '../auth'
import { Alert, Field, useAsyncAction } from '../components/ui'

export default function Login() {
  const { login } = useAuth()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, onSubmit } = useAsyncAction()

  return (
    <div className="login-page">
      <form
        className="login-card"
        onSubmit={onSubmit(async () => {
          await login(loginId.trim(), password)
        })}
      >
        <div className="login-brand">
          <span className="brand-mark">QA</span>
          <h1>QA Manual Hub</h1>
        </div>
        <p className="login-sub">제품 매뉴얼 및 기술문서 중앙관리 시스템</p>

        {error && <Alert kind="error">{error}</Alert>}

        <Field label="User ID">
          <input
            type="text"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
            autoComplete="username"
            autoFocus
            required
            maxLength={64}
          />
        </Field>

        <Field label="Password">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            maxLength={256}
          />
        </Field>

        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? '로그인 중...' : '로그인'}
        </button>

        <div className="login-foot">
          계정이 필요하면 QA 관리자에게 요청하세요.
          <br />
          비밀번호를 잊은 경우 관리자가 초기화해 줍니다.
        </div>
      </form>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Alert, initials } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '▤', end: true },
  { to: '/products', label: 'Products', icon: '▣' },
  { to: '/documents', label: 'Documents', icon: '▦' },
  { to: '/search', label: 'Search', icon: '⌕' },
  { to: '/recent', label: 'Recent Updates', icon: '↻' },
]

const ADMIN_NAV = [
  { to: '/users', label: 'Users', icon: '⚇' },
  { to: '/categories', label: 'Categories', icon: '⊞' },
]

// Mounted under the QA platform nginx (BASE_URL '/manual-hub/') the SPA is one
// card on the platform's home screen, so it needs a way back. Standalone
// (BASE_URL '/') there is no platform home and the link is not rendered.
const PLATFORM_HOME = import.meta.env.BASE_URL === '/' ? null : '/'

const SYSTEM_NAV = [
  { to: '/audit', label: 'Audit Logs', icon: '☰' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [menuOpen])

  if (!user) return null

  return (
    <div className="app">
      <div className="brand">
        <span className="brand-mark">QA</span>
        <span className="brand-text">Manual Hub</span>
      </div>


      <header className="topbar">
        <div className="topbar-title">제품 문서 중앙관리</div>
        <div className="topbar-right">
          {user.must_change_password && (
            <NavLink to="/account" className="badge badge-archived">
              비밀번호 변경 필요
            </NavLink>
          )}
          <div className="menu-wrap" ref={menuRef}>
            <button
              type="button"
              className="user-chip"
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              <span className="avatar">{initials(user.display_name)}</span>
              <span className="stack" style={{ textAlign: 'left' }}>
                <span className="user-chip-name">{user.display_name}</span>
                <span className="user-chip-role">
                  {user.login_id} · {user.is_admin ? 'Admin' : 'User'}
                </span>
              </span>
            </button>
            {menuOpen && (
              <div className="menu" role="menu">
                <div className="menu-head">
                  <strong>{user.display_name}</strong>
                  <span>{user.login_id}</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false)
                    navigate('/account')
                  }}
                >
                  My Account
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false)
                    navigate('/account?change=1')
                  }}
                >
                  비밀번호 변경
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false)
                    void logout()
                  }}
                >
                  로그아웃
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <nav className="sidebar">
        {PLATFORM_HOME && (
          <a className="platform-home" href={PLATFORM_HOME}>
            <span className="nav-icon">←</span>
            QA 자동화 홈
          </a>
        )}
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end}>
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}

        {user.is_admin && (
          <>
            <div className="nav-section">관리</div>
            {ADMIN_NAV.map((item) => (
              <NavLink key={item.to} to={item.to}>
                <span className="nav-icon">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </>
        )}

        <div className="nav-section">시스템</div>
        {SYSTEM_NAV.map((item) => (
          <NavLink key={item.to} to={item.to}>
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <main className="content">
        {user.must_change_password && (
          <Alert kind="warn">
            임시 비밀번호로 로그인했습니다. 문서 등록·수정 기능을 사용하려면 먼저{' '}
            <NavLink to="/account?change=1">비밀번호를 변경</NavLink>하세요.
          </Alert>
        )}
        <Outlet />
      </main>
    </div>
  )
}

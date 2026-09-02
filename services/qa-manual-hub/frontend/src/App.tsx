import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import { Loading } from './components/ui'
import AuditLogs from './pages/AuditLogs'
import Categories from './pages/Categories'
import Dashboard from './pages/Dashboard'
import DocumentDetail from './pages/DocumentDetail'
import Documents from './pages/Documents'
import Login from './pages/Login'
import { MyAccount, NotFound, RecentUpdates, Settings } from './pages/Misc'
import ProductDetail from './pages/ProductDetail'
import Products from './pages/Products'
import Search from './pages/Search'
import Users from './pages/Users'

export default function App() {
  const { user, loading } = useAuth()

  // Until the session check finishes, render neither the app nor the login form
  // -- flashing the login screen at an already-signed-in user is worse than a
  // brief spinner.
  if (loading) return <Loading label="세션 확인 중..." />

  // Not signed in: every route is the login screen.  This is the enforcement
  // point on the client; the server independently rejects unauthenticated calls.
  if (!user) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="products" element={<Products />} />
        <Route path="products/:productId" element={<ProductDetail />} />
        <Route path="documents" element={<Documents />} />
        <Route path="documents/:documentId" element={<DocumentDetail />} />
        <Route path="search" element={<Search />} />
        <Route path="recent" element={<RecentUpdates />} />
        <Route path="audit" element={<AuditLogs />} />
        <Route path="settings" element={<Settings />} />
        <Route path="account" element={<MyAccount />} />

        {/* Admin-only screens: hidden from the sidebar and bounced here too, so
            a bookmarked URL cannot reach them. The API enforces this as well. */}
        <Route
          path="users"
          element={user.is_admin ? <Users /> : <Navigate to="/" replace />}
        />
        <Route
          path="categories"
          element={user.is_admin ? <Categories /> : <Navigate to="/" replace />}
        />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

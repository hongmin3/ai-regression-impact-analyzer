import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('#root element is missing from index.html')

// BASE_URL is '/' for a standalone deployment and '/manual-hub/' when the SPA
// is mounted under the QA platform nginx (VITE_BASE_PATH at build time).
// react-router needs it without the trailing slash.
const basename = import.meta.env.BASE_URL.replace(/\/$/, '')

createRoot(root).render(
  <StrictMode>
    <BrowserRouter basename={basename}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)

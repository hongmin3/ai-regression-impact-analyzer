// Thin fetch wrapper.  Every call is same-origin and carries the session cookie.
//
// A 401 anywhere means the session is gone, so the wrapper notifies listeners and
// the app drops back to the login screen instead of rendering a broken page.

import type {
  AppSettings,
  AuditRow,
  Category,
  Dashboard,
  DocumentDetail,
  DocumentRow,
  DuplicateFileInfo,
  Me,
  Product,
  RecentUpload,
  SearchHit,
  UserRow,
  Version,
  VersionUploadResult,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

type UnauthorizedListener = () => void
const unauthorizedListeners = new Set<UnauthorizedListener>()

export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener)
  return () => unauthorizedListeners.delete(listener)
}

// Login itself legitimately returns 401; it opts out of the global handler.
async function request<T>(
  path: string,
  init: RequestInit = {},
  options: { skipAuthRedirect?: boolean } = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    ...init,
  })

  if (response.status === 401 && !options.skipAuthRedirect) {
    unauthorizedListeners.forEach((fn) => fn())
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : typeof payload === 'string' && payload
          ? payload
          : `요청이 실패했습니다 (HTTP ${response.status})`
    throw new ApiError(response.status, detail)
  }

  return payload as T
}

function json(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
}

function query(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const s = search.toString()
  return s ? `?${s}` : ''
}

export const api = {
  // --- auth ------------------------------------------------------------- //
  login: (login_id: string, password: string) =>
    request<Me>('/auth/login', json('POST', { login_id, password }), {
      skipAuthRedirect: true,
    }),
  logout: () => request<{ detail: string }>('/auth/logout', json('POST')),
  me: () => request<Me>('/auth/me', {}, { skipAuthRedirect: true }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ detail: string }>(
      '/auth/change-password',
      json('POST', { current_password, new_password }),
    ),

  // --- users (admin) ---------------------------------------------------- //
  users: (params: { q?: string; include_inactive?: boolean } = {}) =>
    request<UserRow[]>(`/users${query(params)}`),
  createUser: (body: {
    login_id: string
    display_name: string
    password: string
    role: string
    must_change_password: boolean
  }) => request<UserRow>('/users', json('POST', body)),
  updateUser: (
    id: string,
    body: Partial<{
      display_name: string
      role: string
      is_active: boolean
      must_change_password: boolean
    }>,
  ) => request<UserRow>(`/users/${id}`, json('PATCH', body)),
  resetPassword: (id: string, new_password: string, must_change_password = true) =>
    request<{ detail: string }>(
      `/users/${id}/reset-password`,
      json('POST', { new_password, must_change_password }),
    ),

  // --- catalogue -------------------------------------------------------- //
  products: (params: { include_inactive?: boolean; q?: string } = {}) =>
    request<Product[]>(`/products${query(params)}`),
  createProduct: (body: {
    name: string
    code?: string | null
    description?: string | null
  }) => request<Product>('/products', json('POST', body)),
  updateProduct: (
    id: string,
    body: Partial<{
      name: string
      code: string | null
      description: string | null
      is_active: boolean
      sort_order: number
    }>,
  ) => request<Product>(`/products/${id}`, json('PATCH', body)),

  categories: (params: { include_inactive?: boolean } = {}) =>
    request<Category[]>(`/categories${query(params)}`),
  createCategory: (body: { name: string; description?: string | null }) =>
    request<Category>('/categories', json('POST', body)),
  updateCategory: (
    id: string,
    body: Partial<{
      name: string
      description: string | null
      is_active: boolean
      sort_order: number
    }>,
  ) => request<Category>(`/categories/${id}`, json('PATCH', body)),

  // --- documents -------------------------------------------------------- //
  documents: (
    params: {
      product_id?: string
      category_id?: string
      status?: string
      q?: string
    } = {},
  ) => request<DocumentRow[]>(`/documents${query(params)}`),
  document: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  createDocument: (body: {
    product_id: string
    category_id: string
    name: string
    description?: string | null
  }) => request<DocumentRow>('/documents', json('POST', body)),
  updateDocument: (
    id: string,
    body: Partial<{ name: string; description: string | null; category_id: string }>,
  ) => request<DocumentRow>(`/documents/${id}`, json('PATCH', body)),
  archiveDocument: (id: string) =>
    request<DocumentRow>(`/documents/${id}/archive`, json('POST')),
  restoreDocument: (id: string) =>
    request<DocumentRow>(`/documents/${id}/restore`, json('POST')),
  archiveCheck: (id: string) =>
    request<{ detail: string }>(`/documents/${id}/archive-check`, json('POST')),

  // --- versions --------------------------------------------------------- //
  uploadVersion: (documentId: string, form: FormData) =>
    request<VersionUploadResult>(`/documents/${documentId}/versions`, {
      method: 'POST',
      body: form,
    }),
  setCurrent: (documentId: string, version_id: string) =>
    request<DocumentDetail>(
      `/documents/${documentId}/set-current`,
      json('POST', { version_id }),
    ),
  updateVersion: (
    documentId: string,
    versionId: string,
    body: Partial<{
      revision: string | null
      version: string | null
      document_number: string | null
      language: string | null
      revision_date: string | null
      revision_description: string | null
      comment: string | null
    }>,
  ) =>
    request<Version>(
      `/documents/${documentId}/versions/${versionId}`,
      json('PATCH', body),
    ),
  archiveVersion: (documentId: string, versionId: string) =>
    request<Version>(
      `/documents/${documentId}/versions/${versionId}/archive`,
      json('POST'),
    ),
  restoreVersion: (documentId: string, versionId: string) =>
    request<Version>(
      `/documents/${documentId}/versions/${versionId}/restore`,
      json('POST'),
    ),
  duplicateCheck: (sha256: string) =>
    request<DuplicateFileInfo[]>(`/documents/duplicate-check/${sha256}`),

  // Plain URLs: the browser handles these directly so downloads stream and PDFs
  // open in the built-in viewer.
  downloadUrl: (documentId: string, versionId: string) =>
    `/api/documents/${documentId}/versions/${versionId}/download`,
  previewUrl: (documentId: string, versionId: string) =>
    `/api/documents/${documentId}/versions/${versionId}/preview`,

  // --- search / dashboard / audit --------------------------------------- //
  search: (params: Record<string, unknown>) =>
    request<SearchHit[]>(`/search${query(params)}`),
  dashboard: () => request<Dashboard>('/dashboard'),
  recentUpdates: (limit = 50) =>
    request<RecentUpload[]>(`/recent-updates${query({ limit })}`),
  auditLogs: (params: Record<string, unknown> = {}) =>
    request<AuditRow[]>(`/audit-logs${query(params)}`),
  auditActions: () => request<Record<string, string>>('/audit-actions'),
  settings: () => request<AppSettings>('/settings'),
}

// --- client-side SHA-256, so the duplicate warning can appear before upload --
export async function sha256Hex(file: File): Promise<string | null> {
  if (!crypto?.subtle) return null
  try {
    const buffer = await file.arrayBuffer()
    const digest = await crypto.subtle.digest('SHA-256', buffer)
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('')
  } catch {
    return null
  }
}

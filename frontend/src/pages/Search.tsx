import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import {
  Alert,
  Card,
  CurrentBadge,
  Empty,
  Field,
  Loading,
  fmtDate,
  fmtDateTime,
} from '../components/ui'
import type { Category, Product, SearchHit } from '../types'

const BLANK = {
  q: '',
  product_id: '',
  category_id: '',
  document_name: '',
  document_number: '',
  revision: '',
  version: '',
  language: '',
  file_name: '',
  uploaded_by: '',
  revision_date_from: '',
  revision_date_to: '',
  upload_date_from: '',
  upload_date_to: '',
  document_status: 'active',
  version_status: 'all',
  current_only: false,
}

export default function Search() {
  const [form, setForm] = useState({ ...BLANK })
  const [hits, setHits] = useState<SearchHit[] | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.products({ include_inactive: true }), api.categories()])
      .then(([p, c]) => {
        setProducts(p)
        setCategories(c)
      })
      .catch(() => undefined)
    void run({ ...BLANK })
  }, [])

  async function run(params: typeof BLANK) {
    setBusy(true)
    setError(null)
    try {
      setHits(await api.search(params as unknown as Record<string, unknown>))
    } catch (e) {
      setError(e instanceof Error ? e.message : '검색에 실패했습니다.')
    } finally {
      setBusy(false)
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    void run(form)
  }

  function set<K extends keyof typeof BLANK>(key: K, value: (typeof BLANK)[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Search</h1>
          <div className="desc">
            제품·문서명·Revision·Version·Document Number·언어·파일명·업로더·날짜로 부분 검색
          </div>
        </div>
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      <Card>
        <form onSubmit={submit}>
          <div className="filter-bar">
            <Field label="통합 검색" className="grow">
              <input
                type="search"
                value={form.q}
                onChange={(e) => set('q', e.target.value)}
                placeholder="모든 항목에서 부분 일치 검색"
                autoFocus
              />
            </Field>
            <Field label="Product">
              <select
                value={form.product_id}
                onChange={(e) => set('product_id', e.target.value)}
              >
                <option value="">전체</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Category">
              <select
                value={form.category_id}
                onChange={(e) => set('category_id', e.target.value)}
              >
                <option value="">전체</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? '검색 중...' : '검색'}
            </button>
            <button
              type="button"
              onClick={() => {
                setForm({ ...BLANK })
                void run({ ...BLANK })
              }}
            >
              초기화
            </button>
            <button type="button" className="btn-link" onClick={() => setAdvanced((v) => !v)}>
              {advanced ? '상세 조건 접기' : '상세 조건 펼치기'}
            </button>
          </div>

          {advanced && (
            <>
              <div className="divider" />
              <div className="form-grid">
                <Field label="Document Name">
                  <input
                    type="text"
                    value={form.document_name}
                    onChange={(e) => set('document_name', e.target.value)}
                  />
                </Field>
                <Field label="Document Number">
                  <input
                    type="text"
                    value={form.document_number}
                    onChange={(e) => set('document_number', e.target.value)}
                  />
                </Field>
                <Field label="Revision">
                  <input
                    type="text"
                    value={form.revision}
                    onChange={(e) => set('revision', e.target.value)}
                  />
                </Field>
                <Field label="Version">
                  <input
                    type="text"
                    value={form.version}
                    onChange={(e) => set('version', e.target.value)}
                  />
                </Field>
                <Field label="Language">
                  <input
                    type="text"
                    value={form.language}
                    onChange={(e) => set('language', e.target.value)}
                  />
                </Field>
                <Field label="Original File Name">
                  <input
                    type="text"
                    value={form.file_name}
                    onChange={(e) => set('file_name', e.target.value)}
                  />
                </Field>
                <Field label="Uploaded By">
                  <input
                    type="text"
                    value={form.uploaded_by}
                    onChange={(e) => set('uploaded_by', e.target.value)}
                    placeholder="이름 또는 로그인 ID"
                  />
                </Field>
                <Field label="Revision Date (from)">
                  <input
                    type="date"
                    value={form.revision_date_from}
                    onChange={(e) => set('revision_date_from', e.target.value)}
                  />
                </Field>
                <Field label="Revision Date (to)">
                  <input
                    type="date"
                    value={form.revision_date_to}
                    onChange={(e) => set('revision_date_to', e.target.value)}
                  />
                </Field>
                <Field label="Upload Date (from)">
                  <input
                    type="date"
                    value={form.upload_date_from}
                    onChange={(e) => set('upload_date_from', e.target.value)}
                  />
                </Field>
                <Field label="Upload Date (to)">
                  <input
                    type="date"
                    value={form.upload_date_to}
                    onChange={(e) => set('upload_date_to', e.target.value)}
                  />
                </Field>
                <Field label="Document Status">
                  <select
                    value={form.document_status}
                    onChange={(e) => set('document_status', e.target.value)}
                  >
                    <option value="active">Active</option>
                    <option value="archived">Archived</option>
                    <option value="all">전체</option>
                  </select>
                </Field>
                <Field label="Version Status">
                  <select
                    value={form.version_status}
                    onChange={(e) => set('version_status', e.target.value)}
                  >
                    <option value="all">전체</option>
                    <option value="active">Active</option>
                    <option value="archived">Archived</option>
                  </select>
                </Field>
              </div>
              <label className="check">
                <input
                  type="checkbox"
                  checked={form.current_only}
                  onChange={(e) => set('current_only', e.target.checked)}
                />
                Current 버전만 검색
              </label>
            </>
          )}
        </form>
      </Card>

      <Card title="검색 결과" sub={hits ? `${hits.length}건` : undefined} flush>
        {!hits ? (
          <Loading />
        ) : hits.length === 0 ? (
          <Empty title="조건에 맞는 결과가 없습니다">
            검색어를 줄이거나 상세 조건을 초기화해 보세요.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Product</th>
                  <th className="wrap">Document</th>
                  <th>Category</th>
                  <th>Rev / Ver</th>
                  <th>Doc. No.</th>
                  <th>Lang</th>
                  <th>Revision Date</th>
                  <th>Uploaded By</th>
                  <th>Upload Date</th>
                  <th className="wrap">File</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {hits.map((h, i) => (
                  <tr
                    key={`${h.document_id}-${h.version_id ?? i}`}
                    className={
                      h.document_status === 'archived' || h.version_status === 'archived'
                        ? 'row-archived'
                        : undefined
                    }
                  >
                    <td>{h.product_name}</td>
                    <td className="wrap">
                      <Link className="doc-link" to={`/documents/${h.document_id}`}>
                        {h.document_name}
                      </Link>
                    </td>
                    <td className="faint">{h.category_name}</td>
                    <td>
                      {h.version || h.revision ? (
                        <span className="rev">{h.version ?? h.revision}</span>
                      ) : (
                        <span className="faint small">-</span>
                      )}
                    </td>
                    <td className="mono">{h.document_number ?? '-'}</td>
                    <td className="faint">{h.language ?? '-'}</td>
                    <td className="faint">{fmtDate(h.revision_date)}</td>
                    <td>{h.uploaded_by_display_name ?? '-'}</td>
                    <td className="faint">{fmtDateTime(h.upload_date)}</td>
                    <td className="wrap faint small">{h.original_file_name ?? '-'}</td>
                    <td>
                      <span className="inline">
                        {h.version_id && <CurrentBadge isCurrent={h.is_current} />}
                        {h.version_id && (
                          <a
                            className="btn btn-sm"
                            href={api.downloadUrl(h.document_id, h.version_id)}
                          >
                            다운로드
                          </a>
                        )}
                      </span>
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

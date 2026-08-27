import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import {
  Alert,
  Card,
  CurrentBadge,
  Empty,
  Field,
  Loading,
  StatusBadge,
  fmtDate,
  fmtDateTime,
} from '../components/ui'
import { DocumentForm } from './ProductDetail'
import type { Category, DocumentRow, Product } from '../types'

export default function Documents() {
  const [rows, setRows] = useState<DocumentRow[] | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [productId, setProductId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [status, setStatus] = useState('active')
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    Promise.all([api.products({ include_inactive: true }), api.categories()])
      .then(([p, c]) => {
        setProducts(p)
        setCategories(c)
      })
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [])

  const load = useCallback(() => {
    setError(null)
    api
      .documents({
        product_id: productId || undefined,
        category_id: categoryId || undefined,
        status,
        q: q.trim() || undefined,
      })
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [productId, categoryId, status, q])

  useEffect(load, [load])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Documents</h1>
          <div className="desc">전 제품의 문서를 한 화면에서 확인합니다.</div>
        </div>
        <div className="head-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={() => setCreating(true)}
            disabled={products.filter((p) => p.is_active).length === 0}
          >
            + 문서 등록
          </button>
        </div>
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      <Card>
        <div className="filter-bar">
          <Field label="Product">
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">전체</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Category">
            <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">전체</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Status">
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
              <option value="all">전체</option>
            </select>
          </Field>
          <Field label="문서 이름" className="grow">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="부분 검색"
            />
          </Field>
        </div>
      </Card>

      <Card title="문서 목록" sub={rows ? `${rows.length}건` : undefined} flush>
        {!rows ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty title="조건에 맞는 문서가 없습니다" />
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Product</th>
                  <th className="wrap">Document</th>
                  <th>Category</th>
                  <th>Current Revision</th>
                  <th>Revision Date</th>
                  <th>Uploaded By</th>
                  <th>Upload Date</th>
                  <th className="num">Ver.</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr
                    key={d.id}
                    className={d.status === 'archived' ? 'row-archived' : undefined}
                  >
                    <td>
                      <Link to={`/products/${d.product_id}`}>{d.product_name}</Link>
                    </td>
                    <td className="wrap">
                      <div className="stack">
                        <Link className="doc-link" to={`/documents/${d.id}`}>
                          {d.name}
                        </Link>
                        {d.status === 'archived' && <StatusBadge status={d.status} />}
                      </div>
                    </td>
                    <td className="faint">{d.category_name}</td>
                    <td>
                      {d.current_version_label ? (
                        <span className="inline">
                          <span className="rev">{d.current_version_label}</span>
                          <CurrentBadge isCurrent />
                        </span>
                      ) : (
                        <span className="faint small">버전 없음</span>
                      )}
                    </td>
                    <td className="faint">{fmtDate(d.revision_date)}</td>
                    <td>{d.uploaded_by_display_name ?? '-'}</td>
                    <td className="faint">{fmtDateTime(d.upload_date)}</td>
                    <td className="num">{d.version_count}</td>
                    <td>
                      {d.current_version_id && (
                        <a
                          className="btn btn-sm"
                          href={api.downloadUrl(d.id, d.current_version_id)}
                        >
                          다운로드
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {creating && (
        <DocumentForm
          productId={productId || products.find((p) => p.is_active)?.id || ''}
          categories={categories}
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false)
            load()
          }}
        />
      )}
    </>
  )
}

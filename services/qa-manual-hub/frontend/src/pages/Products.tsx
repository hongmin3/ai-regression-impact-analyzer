import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import {
  Alert,
  Card,
  Empty,
  Field,
  Loading,
  Modal,
  SortTh,
  dateKey,
  fmtDateTime,
  useAsyncAction,
  useSort,
  type SortColumn,
} from '../components/ui'
import type { Product } from '../types'

type SortKey = 'name' | 'code' | 'documents' | 'versions' | 'lastUpload' | 'status'

// Module scope: a new array each render would defeat the memo in useSort.
const COLUMNS: readonly SortColumn<Product, SortKey>[] = [
  { key: 'name', value: (p) => p.name },
  { key: 'code', value: (p) => p.code },
  { key: 'documents', value: (p) => p.document_count },
  { key: 'versions', value: (p) => p.version_count },
  { key: 'lastUpload', value: (p) => dateKey(p.last_upload_at) },
  // Active first when ascending.
  { key: 'status', value: (p) => (p.is_active ? 0 : 1) },
]

export default function Products() {
  const { user } = useAuth()
  const [products, setProducts] = useState<Product[] | null>(null)
  const [includeInactive, setIncludeInactive] = useState(false)
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)

  const load = useCallback(() => {
    setError(null)
    api
      .products({ include_inactive: includeInactive, q: q.trim() || undefined })
      .then(setProducts)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [includeInactive, q])

  // Debounced so typing in the search box does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(load, q ? 250 : 0)
    return () => clearTimeout(timer)
  }, [load, q])

  const { sort, toggle, sorted } = useSort(products, COLUMNS, {
    key: 'name',
    dir: 'asc',
  })

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Products</h1>
          <div className="desc">
            제품을 추가하면 그 제품의 문서를 바로 관리할 수 있습니다. 표 머리글을
            클릭하면 정렬됩니다.
          </div>
        </div>
        <div className="head-actions">
          {user?.is_admin && (
            <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
              + 제품 추가
            </button>
          )}
        </div>
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      <Card>
        <div className="filter-bar">
          <Field label="제품 검색" className="grow">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="제품 이름 또는 코드로 부분 검색"
            />
          </Field>
          <label className="check" style={{ marginBottom: 0 }}>
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
            />
            비활성 포함
          </label>
          {(q || includeInactive) && (
            <button
              type="button"
              onClick={() => {
                setQ('')
                setIncludeInactive(false)
              }}
            >
              초기화
            </button>
          )}
        </div>
      </Card>

      <Card title="제품 목록" sub={sorted ? `${sorted.length}개` : undefined} flush>
        {!sorted ? (
          <Loading />
        ) : sorted.length === 0 ? (
          <Empty title={q ? '조건에 맞는 제품이 없습니다' : '등록된 제품이 없습니다'}>
            {q
              ? '검색어를 줄이거나 "비활성 포함" 을 켜 보세요.'
              : user?.is_admin
                ? '오른쪽 위 "제품 추가" 로 첫 제품을 등록하세요.'
                : '관리자에게 제품 등록을 요청하세요.'}
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <SortTh
                    label="Product"
                    sortKey="name"
                    sort={sort}
                    onSort={toggle}
                    className="wrap"
                  />
                  <SortTh label="Code" sortKey="code" sort={sort} onSort={toggle} />
                  <SortTh
                    label="Documents"
                    sortKey="documents"
                    sort={sort}
                    onSort={toggle}
                    className="num"
                  />
                  <SortTh
                    label="Versions"
                    sortKey="versions"
                    sort={sort}
                    onSort={toggle}
                    className="num"
                  />
                  <SortTh
                    label="최근 업로드"
                    sortKey="lastUpload"
                    sort={sort}
                    onSort={toggle}
                  />
                  <SortTh label="Status" sortKey="status" sort={sort} onSort={toggle} />
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((p) => (
                  <tr key={p.id} className={p.is_active ? undefined : 'row-archived'}>
                    <td className="wrap">
                      <div className="stack">
                        <Link className="doc-link" to={`/products/${p.id}`}>
                          {p.name}
                        </Link>
                        {p.description && (
                          <span className="faint small">{p.description}</span>
                        )}
                      </div>
                    </td>
                    <td className="mono">{p.code ?? '-'}</td>
                    <td className="num">{p.document_count}</td>
                    <td className="num">{p.version_count}</td>
                    <td className="faint">{fmtDateTime(p.last_upload_at)}</td>
                    <td>
                      {p.is_active ? (
                        <span className="badge badge-active">ACTIVE</span>
                      ) : (
                        <span className="badge badge-inactive">INACTIVE</span>
                      )}
                    </td>
                    <td>
                      {user?.is_admin && (
                        <button
                          type="button"
                          className="btn-sm"
                          onClick={() => setEditing(p)}
                        >
                          수정
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

      {creating && (
        <ProductForm
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false)
            load()
          }}
        />
      )}
      {editing && (
        <ProductForm
          product={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            load()
          }}
        />
      )}
    </>
  )
}

function ProductForm({
  product,
  onClose,
  onSaved,
}: {
  product?: Product
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(product?.name ?? '')
  const [code, setCode] = useState(product?.code ?? '')
  const [description, setDescription] = useState(product?.description ?? '')
  const [isActive, setIsActive] = useState(product?.is_active ?? true)
  const [sortOrder, setSortOrder] = useState(product?.sort_order ?? 100)
  const { busy, error, onSubmit } = useAsyncAction()

  const submit = onSubmit(async () => {
    if (product) {
      await api.updateProduct(product.id, {
        name: name.trim(),
        code: code.trim() || null,
        description: description.trim() || null,
        is_active: isActive,
        sort_order: sortOrder,
      })
    } else {
      await api.createProduct({
        name: name.trim(),
        code: code.trim() || null,
        description: description.trim() || null,
      })
    }
    onSaved()
  })

  return (
    <Modal
      title={product ? `제품 수정 — ${product.name}` : '제품 추가'}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={busy}>
            취소
          </button>
          <button type="submit" form="product-form" className="btn-primary" disabled={busy}>
            {busy ? '저장 중...' : '저장'}
          </button>
        </>
      }
    >
      <form id="product-form" onSubmit={submit}>
        {error && <Alert kind="error">{error}</Alert>}
        <Field label="Product Name *" hint="예: Bellalun Viewer, VXvue, VXvue M, VIVIX">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={128}
          />
        </Field>
        <div className="form-grid">
          <Field label="Product Code" hint="선택. 예: BLV, VXV">
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={64}
            />
          </Field>
          <Field label="정렬 순서" hint="작은 값이 위에 표시됩니다.">
            <input
              type="number"
              value={sortOrder}
              onChange={(e) => setSortOrder(Number(e.target.value))}
            />
          </Field>
        </div>
        <Field label="Description">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        {product && (
          <label className="check">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            활성 (Active) — 비활성화해도 문서와 파일은 삭제되지 않습니다.
          </label>
        )}
      </form>
    </Modal>
  )
}

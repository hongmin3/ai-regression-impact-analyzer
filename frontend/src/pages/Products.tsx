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
  fmtDateTime,
  useAsyncAction,
} from '../components/ui'
import type { Product } from '../types'

export default function Products() {
  const { user } = useAuth()
  const [products, setProducts] = useState<Product[] | null>(null)
  const [includeInactive, setIncludeInactive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)

  const load = useCallback(() => {
    setError(null)
    api
      .products({ include_inactive: includeInactive })
      .then(setProducts)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [includeInactive])

  useEffect(load, [load])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Products</h1>
          <div className="desc">
            제품을 추가하면 그 제품의 문서를 바로 관리할 수 있습니다.
          </div>
        </div>
        <div className="head-actions">
          <label className="check" style={{ marginBottom: 0 }}>
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
            />
            비활성 포함
          </label>
          {user?.is_admin && (
            <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
              + 제품 추가
            </button>
          )}
        </div>
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      <Card flush>
        {!products ? (
          <Loading />
        ) : products.length === 0 ? (
          <Empty title="등록된 제품이 없습니다">
            {user?.is_admin
              ? '오른쪽 위 "제품 추가" 로 첫 제품을 등록하세요.'
              : '관리자에게 제품 등록을 요청하세요.'}
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th className="wrap">Product</th>
                  <th>Code</th>
                  <th className="num">Documents</th>
                  <th className="num">Versions</th>
                  <th>최근 업로드</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
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

import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import {
  Alert,
  Card,
  CurrentBadge,
  Empty,
  Field,
  Loading,
  Modal,
  StatusBadge,
  fmtDate,
  fmtDateTime,
  useAsyncAction,
} from '../components/ui'
import type { Category, DocumentRow, Product } from '../types'

export default function ProductDetail() {
  const { productId = '' } = useParams()
  const [product, setProduct] = useState<Product | null>(null)
  const [documents, setDocuments] = useState<DocumentRow[] | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [showArchived, setShowArchived] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(() => {
    setError(null)
    Promise.all([
      api.products({ include_inactive: true }),
      api.documents({
        product_id: productId,
        status: showArchived ? 'all' : 'active',
      }),
      api.categories(),
    ])
      .then(([products, docs, cats]) => {
        setProduct(products.find((p) => p.id === productId) ?? null)
        setDocuments(docs)
        setCategories(cats)
      })
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [productId, showArchived])

  useEffect(load, [load])

  if (error) return <Alert kind="error">{error}</Alert>
  if (!documents || !product) return <Loading />

  return (
    <>
      <div className="breadcrumb">
        <Link to="/products">Products</Link>
        <span>/</span>
        <span>{product.name}</span>
      </div>

      <div className="page-head">
        <div>
          <h1>{product.name}</h1>
          <div className="desc">
            {product.code && <span className="mono">{product.code}</span>}
            {product.code && product.description && ' · '}
            {product.description}
            {!product.is_active && (
              <span className="badge badge-inactive" style={{ marginLeft: 8 }}>
                INACTIVE
              </span>
            )}
          </div>
        </div>
        <div className="head-actions">
          <label className="check" style={{ marginBottom: 0 }}>
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            보관 문서 포함
          </label>
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            + 문서 등록
          </button>
        </div>
      </div>

      <Card
        title="관리 중인 문서"
        sub={`${documents.length}건`}
        flush
      >
        {documents.length === 0 ? (
          <Empty title="등록된 문서가 없습니다">
            "문서 등록" 으로 Operation Manual, Service Manual 등을 추가하세요.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th className="wrap">Document</th>
                  <th>Category</th>
                  <th>Current Revision</th>
                  <th>Doc. No.</th>
                  <th>Lang</th>
                  <th>Revision Date</th>
                  <th>Uploaded By</th>
                  <th>Upload Date</th>
                  <th className="num">Ver.</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {documents.map((d) => (
                  <tr
                    key={d.id}
                    className={d.status === 'archived' ? 'row-archived' : undefined}
                  >
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
                    <td className="mono">{d.current_document_number ?? '-'}</td>
                    <td className="faint">{d.current_language ?? '-'}</td>
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
          productId={productId}
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

export function DocumentForm({
  productId,
  categories,
  onClose,
  onSaved,
}: {
  productId: string
  categories: Category[]
  onClose: () => void
  onSaved: (documentId: string) => void
}) {
  const [name, setName] = useState('')
  const [categoryId, setCategoryId] = useState(categories[0]?.id ?? '')
  const [description, setDescription] = useState('')
  const { busy, error, onSubmit } = useAsyncAction()

  const submit = onSubmit(async () => {
    const created = await api.createDocument({
      product_id: productId,
      category_id: categoryId,
      name: name.trim(),
      description: description.trim() || null,
    })
    onSaved(created.id)
  })

  return (
    <Modal
      title="문서 등록"
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={busy}>
            취소
          </button>
          <button
            type="submit"
            form="document-form"
            className="btn-primary"
            disabled={busy || !categoryId}
          >
            {busy ? '저장 중...' : '등록'}
          </button>
        </>
      }
    >
      <form id="document-form" onSubmit={submit}>
        {error && <Alert kind="error">{error}</Alert>}
        {categories.length === 0 && (
          <Alert kind="warn">
            사용 가능한 문서 분류가 없습니다. 관리자가 Categories 에서 분류를 먼저 추가해야
            합니다.
          </Alert>
        )}
        <Field
          label="Document Name *"
          hint="예: Operation Manual, Service Manual, QC Manual, DICOM Conformance Statement"
        >
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={255}
          />
        </Field>
        <Field label="Document Category *">
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Description">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <Alert kind="info">
          문서를 등록한 뒤 상세 화면에서 첫 버전 파일을 업로드하세요. Revision 과 Version 은
          업로드할 때 직접 입력합니다.
        </Alert>
      </form>
    </Modal>
  )
}

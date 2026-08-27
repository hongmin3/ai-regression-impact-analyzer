import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  Alert,
  Card,
  Empty,
  Field,
  Loading,
  Modal,
  useAsyncAction,
} from '../components/ui'
import type { Category } from '../types'

export default function Categories() {
  const [rows, setRows] = useState<Category[] | null>(null)
  const [includeInactive, setIncludeInactive] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)

  const load = useCallback(() => {
    setError(null)
    api
      .categories({ include_inactive: includeInactive })
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [includeInactive])

  useEffect(load, [load])

  async function toggle(c: Category) {
    setError(null)
    setNotice(null)
    try {
      await api.updateCategory(c.id, { is_active: !c.is_active })
      load()
      setNotice(`'${c.name}' 분류를 ${c.is_active ? '비활성화' : '활성화'}했습니다.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : '요청이 실패했습니다.')
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Document Categories</h1>
          <div className="desc">
            관리자 전용. 분류는 삭제하지 않고 Active / Inactive 로 관리합니다.
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
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            + 분류 추가
          </button>
        </div>
      </div>

      {error && <Alert kind="error" onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="ok" onClose={() => setNotice(null)}>{notice}</Alert>}

      <Card flush>
        {!rows ? (
          <Loading />
        ) : rows.length === 0 ? (
          <Empty title="등록된 분류가 없습니다" />
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th className="wrap">Category</th>
                  <th className="wrap">Description</th>
                  <th className="num">문서 수</th>
                  <th className="num">정렬</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id} className={c.is_active ? undefined : 'row-archived'}>
                    <td className="wrap" style={{ fontWeight: 600 }}>
                      {c.name}
                    </td>
                    <td className="wrap faint">{c.description ?? '-'}</td>
                    <td className="num">{c.document_count}</td>
                    <td className="num faint">{c.sort_order}</td>
                    <td>
                      <span className={c.is_active ? 'badge badge-active' : 'badge badge-inactive'}>
                        {c.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </span>
                    </td>
                    <td>
                      <div className="btn-row">
                        <button type="button" className="btn-sm" onClick={() => setEditing(c)}>
                          수정
                        </button>
                        <button
                          type="button"
                          className={c.is_active ? 'btn-sm btn-danger' : 'btn-sm'}
                          onClick={() => void toggle(c)}
                          title={
                            c.is_active && c.document_count > 0
                              ? '사용 중인 분류는 비활성화할 수 없습니다.'
                              : undefined
                          }
                        >
                          {c.is_active ? '비활성화' : '활성화'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {creating && (
        <CategoryForm
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false)
            load()
          }}
        />
      )}
      {editing && (
        <CategoryForm
          category={editing}
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

function CategoryForm({
  category,
  onClose,
  onSaved,
}: {
  category?: Category
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(category?.name ?? '')
  const [description, setDescription] = useState(category?.description ?? '')
  const [sortOrder, setSortOrder] = useState(category?.sort_order ?? 100)
  const { busy, error, onSubmit } = useAsyncAction()

  const submit = onSubmit(async () => {
    if (category) {
      await api.updateCategory(category.id, {
        name: name.trim(),
        description: description.trim() || null,
        sort_order: sortOrder,
      })
    } else {
      await api.createCategory({
        name: name.trim(),
        description: description.trim() || null,
      })
    }
    onSaved()
  })

  return (
    <Modal
      title={category ? `분류 수정 — ${category.name}` : '분류 추가'}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} disabled={busy}>
            취소
          </button>
          <button type="submit" form="cat-form" className="btn-primary" disabled={busy}>
            {busy ? '저장 중...' : '저장'}
          </button>
        </>
      }
    >
      <form id="cat-form" onSubmit={submit}>
        {error && <Alert kind="error">{error}</Alert>}
        <Field
          label="Category Name *"
          hint="예: Operation Manual, Service Manual, QC Manual, Release Note"
        >
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={128}
          />
        </Field>
        <Field label="정렬 순서" hint="작은 값이 목록 위에 표시됩니다.">
          <input
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(Number(e.target.value))}
          />
        </Field>
        <Field label="Description">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
      </form>
    </Modal>
  )
}

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import {
  Alert,
  Card,
  CurrentBadge,
  Empty,
  Loading,
  Stat,
  fmtBytes,
  fmtDate,
  fmtDateTime,
} from '../components/ui'
import type { Dashboard as DashboardData } from '../types'

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : '불러오지 못했습니다.'))
  }, [])

  if (error) return <Alert kind="error">{error}</Alert>
  if (!data) return <Loading />

  const { counts } = data

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <div className="desc">현재 관리 중인 문서 현황과 최근 활동</div>
        </div>
      </div>

      <div className="stat-grid">
        <Stat
          label="Products"
          value={counts.products_active}
          hint={
            counts.products > counts.products_active
              ? `전체 ${counts.products} (비활성 ${counts.products - counts.products_active})`
              : '전체 활성'
          }
        />
        <Stat
          label="Documents"
          value={counts.documents_active}
          hint={
            counts.documents_archived
              ? `보관 ${counts.documents_archived}건 별도`
              : '보관 문서 없음'
          }
        />
        <Stat
          label="Versions"
          value={counts.versions}
          hint="모든 Revision 이력 보존"
        />
        <Stat
          label="Current 지정 문서"
          value={`${counts.documents_with_current} / ${counts.documents_active}`}
          hint={
            counts.documents_active - counts.documents_with_current > 0
              ? `${counts.documents_active - counts.documents_with_current}건 파일 미등록`
              : '전 문서 최신본 보유'
          }
        />
        <Stat label="Storage" value={fmtBytes(counts.storage_bytes)} hint="중앙 저장소 사용량" />
        <Stat label="활성 사용자" value={counts.users_active} />
      </div>

      <Card title="최근 업로드" sub="Recent uploads" flush>
        {data.recent_uploads.length === 0 ? (
          <Empty title="아직 업로드된 버전이 없습니다">
            Products 에서 제품을 선택해 문서를 등록하고 첫 버전을 업로드하세요.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Product</th>
                  <th className="wrap">Document</th>
                  <th>Revision / Version</th>
                  <th>Uploaded By</th>
                  <th>Upload Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.recent_uploads.map((row) => (
                  <tr key={row.version_id}>
                    <td>{row.product_name}</td>
                    <td className="wrap">
                      <Link className="doc-link" to={`/documents/${row.document_id}`}>
                        {row.document_name}
                      </Link>
                    </td>
                    <td>
                      <span className="rev">{row.version_label}</span>
                    </td>
                    <td>{row.uploaded_by_display_name}</td>
                    <td className="faint">{fmtDateTime(row.upload_date)}</td>
                    <td>
                      <CurrentBadge isCurrent={row.is_current} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="최근 등록 문서" sub="Recently created documents" flush>
        {data.recent_documents.length === 0 ? (
          <Empty title="등록된 문서가 없습니다" />
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
                  <th>Created By</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_documents.map((row) => (
                  <tr key={row.id}>
                    <td>{row.product_name}</td>
                    <td className="wrap">
                      <Link className="doc-link" to={`/documents/${row.id}`}>
                        {row.name}
                      </Link>
                    </td>
                    <td className="faint">{row.category_name}</td>
                    <td>
                      {row.current_version_label ? (
                        <span className="rev">{row.current_version_label}</span>
                      ) : (
                        <span className="faint small">파일 없음</span>
                      )}
                    </td>
                    <td className="faint">{fmtDate(row.revision_date)}</td>
                    <td>{row.created_by_display_name ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: 16,
        }}
      >
        <Card title="최근 Current 변경" sub="Current version changes" flush>
          {data.recent_current_changes.length === 0 ? (
            <Empty title="Current 변경 이력이 없습니다" />
          ) : (
            <div className="table-wrap">
              <table className="grid">
                <thead>
                  <tr>
                    <th className="wrap">Document</th>
                    <th>변경</th>
                    <th>By</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_current_changes.map((row) => (
                    <tr key={row.id}>
                      <td className="wrap">
                        <div className="stack">
                          <span>{row.document_name}</span>
                          <span className="faint small">{row.product_name}</span>
                        </div>
                      </td>
                      <td>
                        <span className="rev">{row.version_label}</span>
                      </td>
                      <td>{row.actor_display_name ?? '-'}</td>
                      <td className="faint small">{fmtDateTime(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="최근 사용자 활동" sub="Recent activity" flush>
          {data.recent_activity.length === 0 ? (
            <Empty title="활동 기록이 없습니다" />
          ) : (
            <div className="table-wrap">
              <table className="grid">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Action</th>
                    <th>User</th>
                    <th className="wrap">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_activity.map((row) => (
                    <tr key={row.id}>
                      <td className="faint small">{fmtDateTime(row.created_at)}</td>
                      <td>{row.action_label}</td>
                      <td>{row.actor_display_name ?? row.actor_login_id ?? '-'}</td>
                      <td className="wrap faint">
                        {[row.product_name, row.document_name, row.version_label]
                          .filter(Boolean)
                          .join(' / ') ||
                          row.target_label ||
                          '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  )
}

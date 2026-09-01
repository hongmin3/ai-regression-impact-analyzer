"""OPEN_QUESTIONS.md #5: 사내 기밀 문서라 리포지토리에 커밋하지 않는 실제 VXvue 1.1.0
Round 1 예시 파일을 고정 경로로 참조하는 E2E 테스트.

기준 폴더 경로는 Git 제외 대상인 `real_fixtures.local.env`(프로젝트 루트, 형식은
`real_fixtures.local.env.example` 참고)에서 읽는다 — 사내망 서버 주소와 부서 폴더
체계를 공개 GitHub repo에 노출하지 않기 위해 `.deploy.env`와 동일한 방식을 따른다.
이 설정 파일이 없거나 경로에 접근할 수 없는 환경(GitHub Actions 등)에서는 자동으로
skip된다."""

from pathlib import Path

import pytest

from app.core.storage import Storage
from app.modules.manual_review.ai_client import ManualReviewAIClient
from app.modules.manual_review.reviewer import ManualRevisionReviewer

_LOCAL_ENV_PATH = Path(__file__).resolve().parents[1] / "real_fixtures.local.env"


def _load_local_fixture_config() -> dict[str, str]:
    if not _LOCAL_ENV_PATH.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in _LOCAL_ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


_config = _load_local_fixture_config()
_knowledge_dir = Path(_config["REAL_VXVUE_KNOWLEDGE_DIR"]) if _config.get("REAL_VXVUE_KNOWLEDGE_DIR") else None
_doc_dir = Path(_config["REAL_VXVUE_DOC_DIR"]) if _config.get("REAL_VXVUE_DOC_DIR") else None

if _knowledge_dir and _doc_dir:
    REAL_MANUAL = _doc_dir / "2차" / "입수" / "VXvue Service Manual.V1.1.0W1_KO_수정필요.docx"
    REAL_RELEASE_NOTE = _doc_dir / "2차" / "입수" / "Release Note_VXvue 1.1.0 Rev01_리뷰.docx"
    REAL_DESIGN_REVIEW = _doc_dir / "VXvue 1.1.0 설계검토보고서_DD-00003974.pdf"
    REAL_SRS_FILES = [
        _knowledge_dir / "(사양서) VXvue 사양서1(260831).pdf",
        _knowledge_dir / "(사양서) VXvue 사양서2(260831).pdf",
        _knowledge_dir / "(사양서) VXvue 사양서3(260831).pdf",
        _knowledge_dir / "(사양서) VXvue 사양서4(260831).pdf",
        _knowledge_dir / "(사양서) VXvue 사양서5(260831).pdf",
        _knowledge_dir / "(사양서) Licence Manager SRS 사양서(260831).pdf",
    ]
    REAL_FILES = [REAL_MANUAL, REAL_RELEASE_NOTE, REAL_DESIGN_REVIEW, *REAL_SRS_FILES]
else:
    REAL_FILES = []

requires_real_vxvue_files = pytest.mark.skipif(
    not REAL_FILES or not all(path.exists() for path in REAL_FILES),
    reason=(
        "real_fixtures.local.env가 없거나 사내망 실제 VXvue 1.1.0 예시 파일에 접근할 수 없는 "
        "환경이라 skip. 설정 방법은 real_fixtures.local.env.example 참고."
    ),
)


def _mock_ai_client(storage: Storage) -> ManualReviewAIClient:
    def responder(prompt: str) -> dict:
        if '"stage": "quick"' in prompt:
            return {"decision": "MODIFICATION_REQUIRED", "confidence": 0.65, "reason_codes": ["SPEC_MISMATCH"], "requires_detail_generation": True}
        return {"problem": "실제 파일 E2E mock 응답", "recommended_manual_text": "...", "qa_comment": "mock", "evidence": [], "needs_human_review": False}

    return ManualReviewAIClient(storage, responder=responder)


@requires_real_vxvue_files
def test_manual_review_pipeline_runs_end_to_end_against_real_vxvue_1_1_0_files(tmp_path):
    storage = Storage(tmp_path / "app.db")
    storage.ensure_product("VXvue")
    for path in REAL_SRS_FILES:
        storage.add_document("specification", "VXvue", "1.1.0", "", path.name, path)

    reviewer = ManualRevisionReviewer(ai_client=_mock_ai_client(storage), storage=storage)
    result = reviewer.run(
        REAL_MANUAL, "VXvue", "Service Manual", "V1.1.0 W1",
        release_note_path=REAL_RELEASE_NOTE,
        design_review_path=REAL_DESIGN_REVIEW,
    )

    assert result["total_changes"] == 799
    assert result["functional_changes"] > 700
    assert sum(result["decision_counts"].values()) == result["functional_changes"]
    assert result["release_scope_total"] == 107
    assert 0 <= result["release_scope_missing_suspected"] <= result["release_scope_total"]

    changes = storage.list_manual_changes(result["revision_id"])
    assert len(changes) == 799
    findings = storage.list_release_findings(result["revision_id"])
    assert len(findings) == 107

from app.modules.manual_review.comment_resolution import suggest_comment_resolution, text_similarity


def test_similar_insert_is_reflected_suspected():
    comment = {"change_text": "Trial License 재발급 조건을 추가한다.", "comment_text": "정식 License 이력을 조건에 포함하세요."}
    changes = [{"id": 7, "kind": "insertion", "functional": True, "text": "정식 License 이력이 있는 경우 Trial License를 재발급할 수 있다."}]

    result = suggest_comment_resolution(comment, changes)

    assert result["status"] == "REFLECTED_SUSPECTED"
    assert result["candidate_change_id"] == 7


def test_unrelated_change_is_not_reflected_suspected():
    comment = {"change_text": "DICOM TLS 인증서 설정", "comment_text": "인증서 만료 조건을 설명하세요."}
    changes = [{"id": 9, "kind": "insertion", "functional": True, "text": "프린터 용지 크기를 변경한다."}]

    result = suggest_comment_resolution(comment, changes)

    assert result["status"] == "NOT_REFLECTED_SUSPECTED"


def test_deletion_match_does_not_claim_reflected():
    comment = {"change_text": "사용자 로그인 제한 설명", "comment_text": "로그인 제한을 명시하세요."}
    changes = [{"id": 3, "kind": "deletion", "functional": True, "text": "사용자 로그인 제한 설명"}]

    assert suggest_comment_resolution(comment, changes)["status"] == "UNABLE_TO_DETERMINE"


def test_similarity_handles_spacing_and_punctuation():
    assert text_similarity("DICOM TLS 인증서 설정", "DICOM-TLS 인증서  설정") > 0.8

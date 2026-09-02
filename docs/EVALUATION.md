# Regression 추천 정확도 평가

QA가 확정한 정답 JSON과 분석 결과 JSON을 비교해 precision·recall·F1 및 누락/과추천 TC를 계산한다.

## 앱에서 QA 정답 적립

완료된 분석의 **분석 이력 → 상세** 화면에서 실제 Regression 대상 TC ID를 저장한다. AI가
추천하지 않은 TC도 입력해야 recall이 계산된다. 저장 즉시 분석별 precision·recall·F1과 전체
확정 건의 micro 평균이 표시된다. 정답은 SQLite `analysis_evaluations`에 분석 ID별로 한 건씩
저장되며, 다시 저장하면 최신 QA 확정 내용으로 갱신된다.

정답이 “대상 없음”인 분석도 빈 목록으로 저장해야 평가 모집단에 포함된다. 아직 QA가 확인하지
않은 분석은 저장하지 않는다.

## 파일 기반 평가

```json
{"case_id": "login-change", "expected_tc_ids": ["TC-LOGIN-01", "TC-LOGIN-02"]}
```

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_analysis.py `
  --result result.json --gold gold.json --output output/evaluations/login-change.json
```

누락 TC가 있으면 exit code 2를 반환하므로 CI나 배포 gate에서 사용할 수 있다. 정답 데이터는
QA 확정 결과만 사용하며 사내 원문이나 비밀정보가 포함되면 공개 저장소에 커밋하지 않는다.

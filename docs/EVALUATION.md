# Regression 추천 정확도 평가

QA가 확정한 정답 JSON과 분석 결과 JSON을 비교해 precision·recall·F1 및 누락/과추천 TC를 계산한다.

```json
{"case_id": "login-change", "expected_tc_ids": ["TC-LOGIN-01", "TC-LOGIN-02"]}
```

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_analysis.py `
  --result result.json --gold gold.json --output output/evaluations/login-change.json
```

누락 TC가 있으면 exit code 2를 반환하므로 CI나 배포 gate에서 사용할 수 있다. 정답 데이터는
QA 확정 결과만 사용하며 사내 원문이나 비밀정보가 포함되면 공개 저장소에 커밋하지 않는다.

# Validation Reports

데이터 버전 `${dataset_version}`, 생성 기준 `${generated_at}`의 검증 산출물입니다.

- `schema/`: manifest 등록 파일의 schema·records
- `integrity/`: FK, CustomerProfile 1:1, 상태이력·Audit 대응
- `quality/`: 합성 데이터 안전성·3계층 식별자
- `business/`: 24개 원본·22개 활성 projection, T-005, API 멱등성
- `reproducibility/`: 두 번 생성한 byte 결정성과 canonical drift
- `latest_qa_summary.json`: 위 5개 리포트의 실제 SHA-256과 전체 결과

```powershell
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py qa --verify-rebuild
```

오류·경고·rebuild drift·manifest 불일치가 모두 0일 때 데이터 QA만 `PASS`로 표시합니다. Backend import와 Runtime은 별도 검증 전까지 `DB_VERIFIED`가 아닙니다.

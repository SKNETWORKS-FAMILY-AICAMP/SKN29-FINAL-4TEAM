# Validation Reports

데이터 버전 `${dataset_version}`의 최신 검증 결과입니다.

- `schema/`: processed·synthetic Schema 결과
- `integrity/`: ID·FK·문서·페이지·근거 참조
- `quality/`: 결측·중복·인코딩·개인정보·모델 범위
- `business/`: 상태 전이·안전·완료·재오픈 규칙
- `reproducibility/`: 반복 생성 해시
- `refactor/`: 선언형 설정·CLI 동등성
- `deletion/`: 원본·임시 데이터 비보관 기록
- `ocr_evidence/`: OCR·이미지 해시·사용자 검수 근거

```powershell
python -B -m unittest discover -s data/tools/tests -v
python data/tools/pipeline.py qa --verify-rebuild
```

오류가 있으면 종료 코드 `1`, 오류와 경고가 없으면 종료 코드 `0`입니다.

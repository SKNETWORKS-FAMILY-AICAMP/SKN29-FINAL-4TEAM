# Data Pipeline Tests

외부 원본·네트워크·추가 패키지 없이 선언형 설정, 정적 Schema, 업무 규칙,
결정성, 경로 제한과 기존 래퍼 호환성을 검사합니다. 대표 E2E는 지침서·WBS·
기획서·화면설계서의 동일 섹션과 실제 Fixture·근거·상태 전이를 함께 검사합니다.

```powershell
python -B -m unittest discover -s data/tools/tests -v
```

테스트 실행 후 `data/.temp`, `data/.work`, `__pycache__`가 남아서는 안 됩니다.

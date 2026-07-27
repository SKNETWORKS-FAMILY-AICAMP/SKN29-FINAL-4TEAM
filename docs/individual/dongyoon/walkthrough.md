# AI / RAG 파트 1단계 개발 결과 (Walkthrough)

이동윤 3주차 업무 지침서(`docs/weekly-task/이동윤_3주차_업무_지침서.md`)에 따라 백엔드 API/DB 명세 수정과 무관하게 선제적으로 개발 가능한 **Pydantic 스키마 모델(`ai/app/schemas/`)**, **안전 규칙 및 실행 정책 YAML (`ai/configs/`)**, **JSON Schema 데이터 계약(`contracts/ai/`)**의 구축 및 검증을 완료하였습니다.

---

## 🛠️ 주요 변경 사항

### 1. Pydantic 데이터 모델 완비 (`ai/app/schemas/`)
- [common.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/common.py): `RiskLevel` (`general`, `caution`, `danger`), `UsageGuidanceStatus` (`NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`), `TraceContext`, `ModelMetadata` 정의
- [symptom.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/symptom.py): `StructuredSymptom`, `MissingField`, `FollowUpQuestion` 스키마 구현
- [safety.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/safety.py): `SafetyAssessment` (위험도 및 판단 사유 모델) 구현
- [guidance.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/guidance.py): `UsageGuidance` (현재 정수기 사용 상태 및 다음 행동 모델) 구현
- [retrieval.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/retrieval.py): `EvidenceReference` (공식 매뉴얼/FAQ RAG 참조 모델) 구현
- [consultation_summary.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/consultation_summary.py): `ConsultationSummaryResult` (상담용 요약 결과) 구현
- [technician_report.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/technician_report.py): `TechnicianReportResult` (방문기사 사전 리포트 결과) 구현
- [pipeline.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/schemas/pipeline.py): `SymptomAnalysisResult` (파이프라인 통합 응답 모델) 구현

### 2. 명시적 안전 규칙 & 실행 정책 YAML 작성 (`ai/configs/`)
- [safety_rules.yaml](file:///c:/Project/SKN29-FINAL-4TEAM/ai/configs/safety_rules.yaml): 누수(전원부/하부), 전기/감전, 뜨거운 물/화상 키워드 및 `usage_guidance_status` 매핑 규칙
- [prohibited_expressions.yaml](file:///c:/Project/SKN29-FINAL-4TEAM/ai/configs/prohibited_expressions.yaml): 확정 진단 표현, 안전 보증 표현, 위험한 직접 수리 유도 표현 금지 가드레일 정의
- [retrieval_policy.yaml](file:///c:/Project/SKN29-FINAL-4TEAM/ai/configs/retrieval_policy.yaml): BAAI/bge-m3 (1024차원), Exact Search, Top-5, S세대/제거 대상 모델 메타데이터 필터 설정
- [retry_policy.yaml](file:///c:/Project/SKN29-FINAL-4TEAM/ai/configs/retry_policy.yaml): 백엔드 타임아웃 30초, AI 내부 재시도 1회 제한 설정
- [model_profiles.yaml](file:///c:/Project/SKN29-FINAL-4TEAM/ai/configs/model_profiles.yaml): 과업별 모델 (`gpt-4o-mini` 등) 실행 프로필

### 3. Backend↔AI JSON Schema 계약 정의 (`contracts/ai/`)
- [StructuredSymptom.schema.json](file:///c:/Project/SKN29-FINAL-4TEAM/contracts/ai/common/StructuredSymptom.schema.json)
- [SafetyAssessment.schema.json](file:///c:/Project/SKN29-FINAL-4TEAM/contracts/ai/common/SafetyAssessment.schema.json)
- [UsageGuidance.schema.json](file:///c:/Project/SKN29-FINAL-4TEAM/contracts/ai/common/UsageGuidance.schema.json)
- [EvidenceReference.schema.json](file:///c:/Project/SKN29-FINAL-4TEAM/contracts/ai/common/EvidenceReference.schema.json)
- [SymptomAnalysisRequest.schema.json](file:///c:/Project/SKN29-FINAL-4TEAM/contracts/ai/requests/SymptomAnalysisRequest.schema.json)
- [SymptomAnalysisResponse.schema.json](file:///c:/Project/SKN29-FINAL-4TEAM/contracts/ai/responses/SymptomAnalysisResponse.schema.json)

---

## 🧪 검증 결과 (Verification)

### 자동화 단위 테스트 실행
`python -m pytest ai/tests/unit/test_schemas_and_configs.py` 실행 결과:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.12, pytest-9.1.0, pluggy-1.5.0
rootdir: C:\Project\SKN29-FINAL-4TEAM\ai
collected 4 items

ai\tests\unit\test_schemas_and_configs.py ....                           [100%]

============================== 4 passed in 0.06s ==============================
```

- Pydantic 스키마 생성 및 타입 검증 100% 통과
- `safety_rules.yaml` 및 `prohibited_expressions.yaml` 파싱 및 매핑 규칙 로딩 검증 성공

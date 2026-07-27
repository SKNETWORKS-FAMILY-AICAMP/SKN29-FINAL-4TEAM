# AI / RAG 파트 2단계 개발 결과 (Walkthrough)

이동윤 3주차 업무 지침서(`docs/weekly-task/이동윤_3주차_업무_지침서.md`)에 따라 100% 단독 개발 및 독립 검증이 가능한 **명시적 안전 규칙 분류기(`ai/app/safety/`)** 및 **출력 가드레일 검증기(`ai/app/validation/safety/`)**의 구축과 테스트 검증을 완료하였습니다.

---

## 🛠️ 2단계 주요 구현 내용

### 1. 안전 규칙 YAML 로더 (`ai/app/safety/rule_loader.py`)
- [rule_loader.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/safety/rule_loader.py): `safety_rules.yaml` 및 `prohibited_expressions.yaml`을 로딩하고 싱글톤/캐싱 형태로 제공하는 `SafetyRuleLoader` 구현

### 2. 위험도 분류기 (`ai/app/safety/risk_classifier.py`)
- [risk_classifier.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/safety/risk_classifier.py): 고객 입력을 분석하여 명시적 위험 키워드(누수, 감전/탄냄새/스파크, 온수 화상 등)를 감지하고, 위험도(`general`, `caution`, `danger`) 및 `SafetyAssessment` 반환

### 3. 사용 안내 상태 판정기 (`ai/app/safety/usage_guidance_classifier.py`)
- [usage_guidance_classifier.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/safety/usage_guidance_classifier.py): 위험도 및 공식 근거 유무(`has_evidence`)에 따라 팀 표준 4대 사용 안내 상태(`NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`) 판정 및 고객 조치 가이드 조립

### 4. 금지 표현 출력 가드레일 (`ai/app/validation/safety/prohibited_phrase_validator.py`)
- [prohibited_phrase_validator.py](file:///c:/Project/SKN29-FINAL-4TEAM/ai/app/validation/safety/prohibited_phrase_validator.py): LLM 생성 문장에 대한 **확정 진단 표현**("고장이 확실합니다" 등), **안전 보증 표현**("절대 안전합니다" 등), **위험 직접수리/분해 유도 표현** 차단 및 Fallback 대체 문구 감지기 구현

---

## 🧪 검증 결과 (Verification)

### 자동화 단위 테스트 실행
`python -m pytest ai/tests/unit/` 실행 결과 전체 10개 테스트 케이스 **100% 통과 (Passed)**

```text
============================= test session starts =============================
platform win32 -- Python 3.13.12, pytest-9.1.0, pluggy-1.5.0
rootdir: C:\Project\SKN29-FINAL-4TEAM\ai
configfile: pyproject.toml
plugins: anyio-4.10.0, langsmith-0.8.16
collected 10 items

ai\tests\unit\test_safety_classifier.py ......                           [ 60%]
ai\tests\unit\test_schemas_and_configs.py ....                           [100%]

============================= 10 passed in 0.07s ==============================
```

- **누수/전기 위험 감지**: `danger` 및 `TOTAL_STOP` 상태 판정 검증 완료
- **일반 냉/온수 이상 감지**: `caution` 및 `PARTIAL_STOP` 판정 검증 완료
- **근거 부재 처리**: `PENDING_CONSULTATION` 및 상담 안내 전환 검증 완료
- **금지 표현 가드레일**: 확정 진단/보증/분해 유도 문구 감지 및 Fallback 전환 100% 검증 완료

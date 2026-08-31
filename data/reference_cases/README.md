# Three-model reference scenarios

`three_model_reference_scenarios_v1.json`은 다음 45개 합성 사례의 버전형
원본입니다.

- 제품 3종: `WPUJAC104DWH`, `WPUIAC425SNW`, `WPUIAC606SNW`
- 위험도 3종: `general`, `caution`, `danger`
- 각 제품·위험도 조합당 5건

## 사용 경계

- 상태는 `CANDIDATE`, 용도는 `REFERENCE_ONLY`입니다.
- 현재 AI Runtime, Prompt, 고객 API는 이 파일과 DB Table을 읽지 않습니다.
- Django 앱은 전용 `reference_cases_local` 및
  `reference_cases_test` 설정에만 등록됩니다. 공용 `base`, 일반
  `local`, 기본 `test`, `production` migration graph에는 포함되지
  않으며, 향후 RDS 등록은 Backend 1~8과 별도 배포 승인을 거쳐야 합니다.
- LLM few-shot 또는 학습 데이터로 직접 주입하지 않습니다.
- IAC425/IAC606 Source는 계속 `EXPANSION_REFERENCE_ONLY`입니다.
- `TOPIC_GROUP_SELECTION_PENDING`은 검증된 Topic-level Evidence Group까지
  연결됐지만, 여러 하위 상황 중 이 사례에 맞는 Evidence를 고르는
  Scenario-level Selection이 아직 필요하다는 뜻입니다.
- `SOURCE_PAGE_ONLY`는 공식 매뉴얼 페이지까지 확인됐지만 독립 Evidence
  Group이 없는 사례입니다. Evidence 검증 완료로 승격하지 않습니다.
- `expected_requires_consultation`은 고객을 상담으로 연결할지에 대한
  판단이고, `expected_publication_gate`는 고객 공개 전 인간 승인이
  필요한지에 대한 별도 판단입니다. 따라서 일부 `caution` 사례는
  즉시 상담 연결 없이도 `HUMAN_APPROVAL_REQUIRED`일 수 있습니다.

기존 `manual_3model_candidate_scenarios.json` 30건과 그 Builder, Validator,
Backend Fixture 계약은 변경하지 않습니다.

## 검증과 로컬 적재

Schema는
`data/schemas/reference_cases/three_model_reference_scenarios_v1.schema.json`,
추가 Lineage 검증은 `local_apps.reference_cases.catalog`에서 수행합니다. Loader는
정확히 45건인지, 제품·위험도별 5건인지, 매뉴얼 Page가 존재하는지,
Evidence Group의 제품·문서·페이지·Topic·검증 상태·허용 용도가 맞는지,
현재 Release Oracle이 맞는지를 모두 확인한 뒤에만 DB 경로를 엽니다.

Management Command는 기본적으로 전체 Insert 경로를 실행한 뒤 Rollback
합니다.

```powershell
python manage.py import_reference_scenarios `
  --settings config.settings.reference_cases_local `
  --confirm-system-identifier 7500123456789012345
```

실제 적재는 명시적인 `--apply`와 연결 DB명 재확인이 모두 필요합니다.
PostgreSQL에서는 Dry-run과 Apply 모두 전용 로컬 Cluster의
`pg_control_system().system_identifier` 재확인도 필요합니다.

```powershell
python manage.py import_reference_scenarios `
  --settings config.settings.reference_cases_local `
  --apply `
  --confirm-database waterbridge_reference_cases_local_example `
  --confirm-system-identifier 7500123456789012345
```

PostgreSQL Apply/Dry-run은 Loopback Host와
`waterbridge_reference_cases_` Prefix, 사전에 확인한 Cluster
`system_identifier`를 모두 만족하는 전용 로컬 DB에서만 허용됩니다.
기존 `waterbridge`, Team Integration, RDS에는 이 명령을 사용할 수
없습니다. RDS 반영은 Backend 정책 1~8과 전체 QA가 끝난 뒤 별도 승인된
배포 절차로 진행합니다.

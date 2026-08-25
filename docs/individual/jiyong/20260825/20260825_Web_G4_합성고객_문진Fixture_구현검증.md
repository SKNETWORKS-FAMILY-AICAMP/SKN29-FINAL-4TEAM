# Web G4 합성 고객·문진 Fixture 구현·검증

## 1. 목적

Web 상담사 통합 문의 상세 화면에서 합성 고객의 이름·마스킹 연락처와
문진 질문·답변을 실제 Backend 응답으로 확인할 수 있도록 Web G4 전용
Fixture를 보완했다.

## 2. 적용 경계

- 수정 영역: Backend Web G4 Fixture와 해당 단위·API 검증
- 읽기 전용 Source:
  `data/config/synthetic/manual_3model_candidate_scenarios.json`
- Source 상태: `CANDIDATE` 30건
- Source 원본, Data Importer, Migration, Web, Mobile, AI는 수정하지 않았다.
- 이번 작업은 30건을 Golden Set 또는 Public Runtime으로 승격하지 않는다.
- Web G4의 기존 JAC104 합성 문의·상담 상태 전이는 변경하지 않는다.

## 3. 생성 데이터

합성 고객 Profile의 테스트 전용 값은 다음과 같다.

| 항목 | DB 합성 Fixture 값 | 상담사 상세 API 공개값 |
|---|---|---|
| 이름 | 제갈지용 | 제갈지용 |
| 전화번호 | 010-1234-5678 | 010-****-5678 |

전화번호 원문은 합성 DB Fixture에만 존재한다. 상담사 API의 기존 마스킹
정책을 유지하며 공개 응답과 Crosswalk에 원문을 넣지 않는다.

30건 모두에 공통으로 정의된 문진 틀을 확인한 뒤 다음 답변을 생성한다.

| 순서 | 질문 | 답변 |
|---:|---|---|
| 1 | 증상은 언제부터 시작됐나요? | 오늘 |
| 2 | 어떤 출수에서 증상이 발생하나요? | 정수 |
| 3 | 증상은 언제 또는 어떤 조건에서 발생하나요? | 출수 버튼을 누를 때 |
| 4 | 이미 확인하거나 조치해 본 내용이 있나요? | 필터 상태 확인 |

각 질문과 답변의 공개 UUID는 `run_id` 기반 Inquiry와 질문 코드로 결정적
생성한다. 같은 미소비 `run_id`를 다시 실행하면 기존 값을 검증만 하며
중복 질문·답변을 만들지 않는다.

## 4. 안전장치

- Source가 `CANDIDATE` 30건이 아니면 생성 실패
- 30건의 공통 질문 구조가 서로 다르면 생성 실패
- 질문·선택지·답변 관계가 바뀌면 생성 실패
- Demo 합성 고객이 아닌 Profile은 수정하지 않음
- 이미 다른 전화번호로 바뀐 Profile은 덮어쓰지 않고 Transaction Rollback
- 공개 상세 API에 `010-1234-5678` 원문이 포함되면 테스트 실패
- 기존 공개 Crosswalk에는 고객 이름·전화번호·문진 원문을 추가하지 않음

## 5. 검증 결과

| 검증 | 결과 |
|---|---|
| Fixture 표적 Unit·API | 13 passed |
| Web G4 관련 Backend 묶음 | 36 passed |
| 이름·DB 전화번호·4개 질문·4개 답변 | PASS |
| API 전화번호 마스킹·원문 비노출 | PASS |
| 동일 run_id Replay 중복 0건 | PASS |
| 비정상 Profile 덮어쓰기 방지·Rollback | PASS |
| `git diff --check` | PASS |
| Backend 전체 회귀 | 1,467 passed / 41 skipped / 0 failed |

관련 묶음은 Fixture, Web G4 DB Evidence, 상담사 문의 상세 Runtime,
Web G4 로컬 Bootstrap 계약 테스트를 포함한다.

전체 회귀의 41건은 PostgreSQL 전용 Lock·Catalog 검증, 별도 Socket Runtime
등 명시적 실행 조건이 없는 경우 원래 건너뛰는 테스트다. 이번 변경과 직접
관련된 Fixture·상담사 상세 계약에는 실패나 미실행 항목이 없다.

전체 회귀 후 최신 `main@f4791d9118677504c3492a869ddae351b5307b5a`을
추가 동기화했다. 해당 main 변경은 배포 Workflow·배포 자산 테스트에만
한정됐으며, 동기화 후 Fixture 표적 13건과 배포 Gate 13건을 각각 다시
실행해 모두 통과했다.

## 6. 후속 Runtime 확인

이 변경이 main에 반영된 뒤 한예나 PC의 기존 격리 Docker 절차로 새
`run_id`를 생성하면 상세 화면에서 이름·마스킹 연락처·문진 4건을 확인할
수 있다. Browser Playwright 실측은 Web 담당자의 기존 G4 실행선에서
수행하며, 기존 보존 DB Volume을 초기화하거나 재사용하지 않는다.

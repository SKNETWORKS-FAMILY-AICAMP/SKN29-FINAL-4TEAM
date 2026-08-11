# WaterBridge Backend·Database·API 개발문서

> 프로젝트: SKN29 Final Project — WaterBridge
>
> 기준일: 2026-08-10
>
> 작성·유지 책임: 최지용 — Backend·Database·API
>
> 대상 독자: Backend·Data/QA·Web·Mobile·AI 담당자와 PM·리뷰어

## 1. 이 폴더를 보는 순서

이 README는 WaterBridge Backend 개발·실행·검증·인계 문서의 단일
진입점이다. 독자는 필요한 기술 영역을 고른 뒤 대표 문서를 읽는다.
WBS 번호는 일정과 범위를 추적할 때만 사용하며, 실제 구현 여부는
계약·코드·Migration·테스트 증거로 판단한다.

1. 환경을 처음 구성하거나 복구할 때는 `개발환경/`
2. Model·Migration·Seed·PostgreSQL을 다룰 때는 `데이터베이스/`
3. Login·JWT·RBAC·계정 식별자를 다룰 때는 `인증_권한/`
4. REST·OpenAPI·문의·상태 전이를 다룰 때는 `API/`
5. AI·Mobile·팀 검토 요청을 확인할 때는 `연동_인계/`

[2026-07-31 작업 진행도](최지용_작업_진행도_07311640.md)는 해당 시점의
업무 상태를 보존한 기준 스냅샷이다. [Archive 안내](archive/README.md)는
문서 통합 전 원본과 결정 전 제안의 보관 범위를 설명한다. 현행 구현
판정에는 4절에 연결된 활성 문서를 사용한다.

## 2. 문서 구성 원칙

이 폴더에는 WaterBridge의 Backend·Database·API 구현을 재현하고 검토하는
데 필요한 문서만 둔다. 각 문서는 기술 책임·계약·구현·재현 절차와 검증
경계만 설명한다.

| 원칙 | 적용 방식 |
| --- | --- |
| 폴더만 보고 영역 식별 | `개발환경`, `데이터베이스`, `인증_권한`, `API`, `연동_인계` |
| 파일만 보고 기술·목적 식별 | `Django_PostgreSQL_...`, `Django_REST_API_...`, `Backend_Mobile_API_...` |
| WBS 추적성 보존 | `T-005`, `T-017`, `T-022`, `T-023`은 문서 본문과 메타데이터에 유지 |
| 현행 문서와 역사 증거 분리 | 실행 가이드·현재 인계서와 날짜가 붙은 검증/변경 이력을 구분 |
| 중복 방지 | 같은 기능의 계약·구현·검증은 대표 문서 하나에서 관리 |

### 2.1 공통 용어

| 용어 | 이 문서 묶음에서의 의미 |
| --- | --- |
| Runtime | Django에 Route·View·Serializer·Service가 연결되어 실제 요청을 처리하는 상태 |
| OpenAPI-only | 기계 계약은 존재하지만 Runtime Route가 없는 상태 |
| 작성자 검증 | 문서에 기록된 환경에서 담당자가 실행한 결과이며 독립 재현 전 상태 |
| 팀 기준선 | 비작성자 검토와 PM 병합을 거쳐 팀이 공통으로 사용하는 상태 |
| Target-only | 물리 테이블은 유지하지만 현재 업무 데이터가 0행인 확장 대상 |
| Slice | 하나의 요청부터 DB·응답·테스트까지 수직으로 검증한 최소 구현 단위 |
| Gate | 다음 단계로 진행하기 전에 충족해야 하는 계약·검토·검증 조건 |
| 내부 상태 코드 | 자동화·추적용 보조 식별자이며, 사람용 한국어 판정과 완료 조건을 우선해 해석 |

## 3. 현재 구조

```text
docs/individual/jiyong/
├─ README.md
├─ 최지용_작업_진행도_07311640.md             # 수정 금지 역사 스냅샷
├─ 개발환경/
│  └─ Django_PostgreSQL_로컬개발환경_설치_실행_복구_가이드.md
├─ 데이터베이스/
│  ├─ Django_PostgreSQL_스키마_변경_가이드.md
│  ├─ Django_PostgreSQL_테이블_구현_변경이력_20260730.md
│  ├─ PostgreSQL_통합검증_보고서_20260731.md
│  ├─ PostgreSQL_합성데이터_적재_통합검증_가이드.md
│  └─ PostgreSQL_마이그레이션_불변성_사고_복구_보고서.md
├─ 인증_권한/
│  ├─ Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md
│  └─ Django_UUID_JWT_전환_롤백_가이드.md
├─ API/
│  ├─ Django_REST_API_OpenAPI_계약_구현_보안검증_가이드.md
│  ├─ Django_REST_API_구독_제품조회_계약_제안서.md
│  ├─ Django_REST_API_상담사_문의조회_Runtime_구현_검증_가이드.md
│  ├─ Django_REST_API_방문_Runtime_PostgreSQL_Row_Lock_수정_검증_보고서_20260810.md
│  ├─ Django_REST_API_문의_증상제출_구현_검증_인계서.md
│  └─ Django_State_Machine_API_구현_검증_인계서.md
├─ 연동_인계/
│  ├─ Backend_AI_API_계약_구현_미해결_사항.md
│  ├─ Backend_Mobile_API_연동_가이드.md
│  └─ Backend_팀_검토_인계_체크리스트.md
└─ archive/
   ├─ README.md                              # 역사 자료 진입점
   ├─ 20260725_데이터베이스_물리계약_검토제안_보관.md
   └─ 20260802_문서통합_원본/               # SHA-256 보존 원본
```

## 4. 기술 영역별 대표 문서

### 4.1 개발환경

| 문서 | 용도 |
| --- | --- |
| [Django·PostgreSQL 로컬 개발환경 설치·실행·복구 가이드](개발환경/Django_PostgreSQL_로컬개발환경_설치_실행_복구_가이드.md) | `.venv`, PostgreSQL, Migration, Seed, Django 서버 실행과 안전 복구 |

### 4.2 데이터베이스

| 문서 | 용도 |
| --- | --- |
| [Django·PostgreSQL 스키마 변경 가이드](데이터베이스/Django_PostgreSQL_스키마_변경_가이드.md) | Model·Migration·공통코드·Seed·Importer·Auditor 절차 |
| [PostgreSQL 합성데이터 적재·통합검증 가이드](데이터베이스/PostgreSQL_합성데이터_적재_통합검증_가이드.md) | Fixture·Hash·Crosswalk·Importer·Replay 검증 흐름 |
| [WaterBridge PostgreSQL 통합검증 보고서](데이터베이스/PostgreSQL_통합검증_보고서_20260731.md) | Backup·Restore·32/32·Seed·Importer의 특정 시점 실행 증거 |
| [Django·PostgreSQL 테이블 구현·변경이력](데이터베이스/Django_PostgreSQL_테이블_구현_변경이력_20260730.md) | T-005 구현 Wave와 당시 결정의 역사 기록 |
| [PostgreSQL Migration 불변성 사고·복구 보고서](데이터베이스/PostgreSQL_마이그레이션_불변성_사고_복구_보고서.md) | 적용 Migration 변조 사고·복구·재발 방지 증거 |

### 4.3 인증·권한

| 문서 | 용도 |
| --- | --- |
| [Django JWT·RBAC 로그인·계정관리 구현·검증 가이드](인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md) | Login·`/me`·Refresh·Logout·4역할·IDOR와 계정관리 Gate |
| [Django 계정 PK·UUID·JWT 전환·롤백 가이드](인증_권한/Django_UUID_JWT_전환_롤백_가이드.md) | 고위험 식별자 Migration과 복구 절차 |

### 4.4 API

| 문서 | 용도 |
| --- | --- |
| [Django REST API·OpenAPI 계약·구현·보안검증 가이드](API/Django_REST_API_OpenAPI_계약_구현_보안검증_가이드.md) | 공통 API 계약 변경, 오류·예시·권한·로그 보안 검증 절차 |
| [Django REST API 상담사 문의 조회 Runtime 구현·검증 가이드](API/Django_REST_API_상담사_문의조회_Runtime_구현_검증_가이드.md) | 상담사 배정 문의 목록·상세, PII Projection, 시간대 동일 시점 검증 |
| [Django REST API 방문 Runtime PostgreSQL Row Lock 수정·검증 보고서](API/Django_REST_API_방문_Runtime_PostgreSQL_Row_Lock_수정_검증_보고서_20260810.md) | Nullable 기사 Join Lock 결함, 최소 수정, PostgreSQL 16.14 회귀 증거 |
| [Django REST API 문의·증상제출 구현·검증·인계서](API/Django_REST_API_문의_증상제출_구현_검증_인계서.md) | T-022 Slice A 계약·Transaction·409·멱등·독립 재현·Slice B 중단선 |
| [Django REST API 문의 AI Runtime Wiring·실제 Mock HTTP 가이드](API/Django_REST_API_문의_AI_Runtime_Wiring_실제Mock_HTTP_구현_검증_가이드.md) | `SUBMIT_SYMPTOM` Commit 후 AI 1회 호출, Replay·실패보존·실제 Uvicorn Mock 검증 |
| [Django REST API T-024 Backend AI 추적·구조화 로그 구현·검증 가이드](API/Django_REST_API_T024_Backend_AI_추적_구조화로그_구현_검증_가이드.md) | Callback·AI Lifecycle·Correlation·DB 원장 연결과 로그 비노출 검증 |
| [Django State Machine API 구현·검증·인계서](API/Django_State_Machine_API_구현_검증_인계서.md) | T-023 Engine·Guard·`allowed_actions`·SYSTEM 이벤트·상담 Action Gate |
| [Django REST API 구독·제품조회 계약 제안서](API/Django_REST_API_구독_제품조회_계약_제안서.md) | T-018 승인 전 최소 GET 계약·권한·테스트 Matrix |

### 4.5 연동·인계

| 문서 | 용도 |
| --- | --- |
| [Backend·AI API 계약·구현 미해결 사항](연동_인계/Backend_AI_API_계약_구현_미해결_사항.md) | Schema Parity·Timeout·Retry·stale·검색 후검증·공동 E2E |
| [Backend·Mobile API 연동 가이드](연동_인계/Backend_Mobile_API_연동_가이드.md) | Runtime·OpenAPI-only·Mock·Blocked와 DTO·오류 소비 경계 |
| [Django 방문 Runtime PostgreSQL Row Lock QA 재검증 요청서](연동_인계/Django_방문_Runtime_PostgreSQL_Row_Lock_QA_재검증_요청서.md) | 김은진 영향 Case 재현, Operation별 PASS, 소비자 연결 Gate |
| [Backend 팀 검토·인계 체크리스트](연동_인계/Backend_팀_검토_인계_체크리스트.md) | 담당자별 검토 요청·반환 증거·금지사항 |

### 4.6 역사 자료

| 문서 | 용도 |
| --- | --- |
| [Archive 안내](archive/README.md) | 현행 문서와 통합 원본·결정 전 제안의 구분 및 보호 정책 |

## 5. 판단 우선순위

| 판단 항목 | 우선 기준 |
| --- | --- |
| API Method·Path·Schema | `contracts/api/**` |
| 상태·Action·권한 | `contracts/state-machine/**` |
| AI 입출력 | `contracts/ai/**` |
| DB 구조 | T-005 기계 계약·Django Model·Migration·PostgreSQL 검증 |
| Runtime 완료 | Route·실행 테스트·같은 변경 묶음의 검증 증거 |
| 개발·검증 절차 | [공통 개발 규칙](<../../planning/md/공통 개발 규칙.md>) |
| 담당·협업 경계 | [팀원별 관할 영역 v2](<../../planning/md/팀원별 관할 영역 v2.md>) |

설명 문서와 기계 계약 또는 Runtime이 다르면 기계 계약과 실행 증거를
우선하고 설명 문서를 수정한다. 과거 계획표와 테스트 수치는 해당 시점의
스냅샷으로만 사용한다.

## 6. 현재 실행 기준

| 항목 | 현재 결과 |
| --- | --- |
| Python | 3.13.13 |
| 기본 PostgreSQL | `waterbridge.public`, PostgreSQL 16.14 |
| pgvector | 0.8.6, `vector(1024)`, Exact Search |
| T-005 | 계약 테이블 32/32, Auditor `READY`, blocker 0 |
| Active 데이터 | 13개 테이블·총 369행 |
| Target-only | 19개 테이블·각 0행으로 보존 |
| Seed | 기본 Seed 5종 2회, 2회차 비의도 신규 생성 0 |
| 격리 Importer | Source 367, 최초 355 created·12 projected, Replay 355 unchanged·12 projected |
| Backend 회귀 — 8/10 AI Wiring 후보 | SQLite `936 passed, 16 skipped`; 실제 Uvicorn Mock HTTP `1 passed` |
| Backend 회귀 — 8/11 T-017C·T-024 통합 후보 | SQLite `966 passed, 17 skipped`; 실제 Uvicorn Mock HTTP `1 passed` |
| 공식 완료 | 비작성자 독립 재현·외부 소비 검토·PM 승인 대기 |

수치는 작성자 로컬 검증 증거이며 PM의 WBS 완료 판정과 같지 않다.

## 7. 다음 작업 우선순위

| 순서 | 작업 | 현재 경계 | 협업 |
| ---: | --- | --- | --- |
| 1 | 방문 Runtime PostgreSQL Lock 독립 재검증 | 작성자 PostgreSQL PASS·소비자 연결 HOLD | 김은진·윤승혁 |
| 2 | T-022 Slice A 독립 검토·PM 병합 | 계약·Runtime·PostgreSQL·전체 회귀 완료 | 김은진 또는 지정 리뷰어·윤승혁 |
| 3 | T-023 Backend 독립 보강 | SYSTEM actor 이력·`change_reason`·전 상태 `allowed_actions` 회귀 | 김은진 검토 |
| 4 | T-017A 검토 결과 수집 | OWNER 설계 완료·정책/Migration 검토 대기 | 윤승혁·김은진 |
| 5 | T-018 최소 GET 계약 검토 | Runtime·Migration 변경 없는 제안 단계 | 김은진·윤승혁 |
| 6 | 승인된 T-017B/C·T-018 Runtime | 서로 섞지 않고 한 작업씩 구현·PostgreSQL 검증 | 김은진 비작성자 검토 |
| 7 | T-022 Slice B·T-023 SYSTEM 이벤트 | AI 요청·재처리·stale·dispatch 계약 확정 뒤 별도 구현 | 이동윤·윤승혁 |
| 8 | Backend·AI·Web·Mobile 소비 E2E | PM 병합·최신 `main`·각 소비 계약 필요 | 이동윤·한예나·양정현 |

## 8. 파일명·경로 규칙

- 활성 폴더명은 기술/업무 영역을 사용한다.
- 활성 파일명은 `기술_기능_문서종류.md` 순서로 작성한다.
- `t005`, `t017` 같은 WBS 식별자는 활성 파일명에 사용하지 않는다.
- 특정 시점의 실행 증거에만 날짜를 파일명 끝에 사용한다.
- 작성자명·시각·`final`·의미 없는 버전 접미사는 활성 파일명에 쓰지 않는다.
- 저장소 파일 링크는 상대경로만 사용한다.
- `.env` 실제 값, Token, Password, DB Dump와 개인정보를 문서에 넣지 않는다.

## 9. 완료·이력 원칙

구현·테스트·작성자 검증 완료와 팀 공식 완료를 구분한다. 비작성자 재현,
소비자 호환성 검토와 PM 승인이 기록되기 전에는 `완료`로 확대 해석하지
않는다.

[Archive의 통합 원본과 결정 전 제안](archive/README.md)은 추적 목적으로만
보존한다. 현행 작업은 이 README의 다섯 기술 영역에 있는 대표 문서를
기준으로 판단한다.

# 최지용 백엔드·데이터베이스·API 개발문서

> 기준일: 2026-07-31
>
> 작성·유지 책임: 최지용
>
> 범위: Backend·Database·Public API 계약
>
> 현재 상태: WaterBridge 전환·T-005 32/32 로컬 기술 검증 완료,
> 비작성자 재현·외부 소비 검토·PM 공식 승인 대기

## 1. 문서 역할

이 README는 최지용 개발문서의 진입점이다. 현재 실행 절차, 특정 시점
검증 결과, 설계와 협업 요청은 성격별 단일 문서로 연결하며 과거 Wave
수치와 긴 실행 이력을 이 파일에 반복하지 않는다.

`docs/**`는 공동 편집 영역이다. 이 경로는 배타적 소유를 뜻하지 않고
아래 산출물의 작성·유지 책임과 주담당이 최지용임을 표시한다.

## 2. 판단 우선순위

| 판단 항목 | 우선 기준 |
| --- | --- |
| API Method·Path·Schema | `contracts/api/**` |
| 상태·Action·권한 | `contracts/state-machine/**` |
| AI 입출력 | `contracts/ai/**` |
| DB 구조 | 활성 T-005 계약·Django Model·Migration·PostgreSQL 검증 |
| Runtime 완료 | Route·실행 테스트·같은 Commit의 검증 증거 |
| 문서 위치·이름 | [프로젝트 디렉토리 구조 v2](<../../architecture/프로젝트 디렉토리 구조 v2.md>) |
| 개발·검증 절차 | [공통 개발 규칙](<../../planning/md/공통 개발 규칙.md>) |
| 담당·협업 경계 | [팀원별 관할 영역 v2](<../../planning/md/팀원별 관할 영역 v2.md>) |

설명 문서와 기계 계약 또는 Runtime이 다르면 설명 문서를 수정한다.
과거 계획표와 테스트 수치는 당시 스냅샷으로만 사용한다.

## 3. 현재 실행 기준

| 항목 | 현재 결과 |
| --- | --- |
| Python | 3.13.13 |
| PostgreSQL | 16.14, `waterbridge.public` |
| pgvector | 0.8.6, `vector(1024)`, Exact Search |
| T-005 | 계약 테이블 32/32, Auditor `READY`, blocker 0 |
| Active 데이터 | 13개 테이블·총 369행 |
| Target-only | 19개 테이블·각 0행으로 보존 |
| Seed | 기본 Seed 5종 2회, 2회차 비의도 신규 생성 0 |
| 격리 Importer | Source 367, 최초 355 created·12 projected, Replay 355 unchanged·12 projected |
| Backend 회귀 | SQLite `740 passed, 11 skipped`, PostgreSQL `751 passed` |
| Data QA | 67 tests, 대표 E2E 17/17, 오류·경고 0 |
| 공식 완료 | 비작성자 독립 재현·외부 소비 검토·PM 승인 대기 |

Active 13과 Target-only 19는 동일한 32개 물리 계약 안의 데이터 활성
범위다. Target-only 테이블을 삭제하거나 별도 축소 Schema로 분리하지
않는다.

## 4. 현재 문서

### 4.1 실행·검증 보고서

| 문서 | 용도 |
| --- | --- |
| [WaterBridge 백엔드 설치·Migration·Seed·복구 가이드](manuals/워터브리지_백엔드_설치_마이그레이션_시드_복구_가이드.md) | 새 PC 설치, 일상 실행, Migration·Seed, 복구와 금지사항 |
| [T-005 WaterBridge PostgreSQL 통합 검증 보고서](technical/backend/20260731_t005_워터브리지_postgresql_통합_검증_보고서.md) | Backup·Restore, 32/32, 빈 DB, Seed·Importer와 전체 회귀 증거 |
| [백엔드 API 계약·Runtime 통합 검증 보고서](manuals/20260729_백엔드_api_계약_및_런타임_통합_검증_보고서.md) | Auth 포함 API 계약·오류·권한·예시·회귀 증거 |
| [백엔드 요청·예외 로그 민감정보 감사 보고서](technical/backend/20260731_백엔드_요청_예외_로그_민감정보_감사_보고서.md) | 현재 로그 경로의 민감정보 비노출 검증 |
| [합성 데이터 Fixture·Hash·Crosswalk 검증 보고서](technical/contracts/합성_데이터_픽스처_해시_교차표_검증_보고서.md) | 367건 불변식, 줄바꿈 정규화와 Crosswalk 정합성 |

### 4.2 반복 실행 가이드

| 문서 | 용도 |
| --- | --- |
| [T-005 데이터베이스 스키마 변경 실행 가이드](technical/backend/t005_데이터베이스_스키마_변경_실행_가이드.md) | Model·Migration·공통코드·Seed·Importer·Auditor 절차 |
| [T-005 계정 PK·UUID·JWT 전환·Rollback 가이드](technical/backend/t005_계정_pk_uuid_jwt_전환_및_롤백_가이드.md) | 고위험 식별자·인증 전환과 복구 |
| [백엔드 API 계약 개발·인계 가이드](technical/backend/백엔드_api_계약_개발_및_인계_가이드.md) | OpenAPI·Route·Serializer·예시·테스트 동시 갱신 |
| [백엔드 Python 가상환경 재현 가이드](technical/backend/백엔드_파이썬_가상환경_재현_가이드.md) | `.venv` 생성·검사·안전 재생성 |
| [합성 데이터 Schema·Importer·PostgreSQL 검증 가이드](technical/backend/합성_데이터_스키마_적재기_postgresql_검증_가이드.md) | 합성 Model·Migration·정식 적재기·367건 Replay |
| [합성 고객 데모 로그인 가이드](manuals/합성_고객_데모_로그인_가이드.md) | 공개 `SYN-*` 별칭과 내부 고객번호 직접 로그인 차단 |

### 4.3 설계·이력·미해결 사항

| 문서 | 용도 |
| --- | --- |
| [T-005 테이블 구현·변경 이력](technical/backend/20260730_t005_테이블_구현_및_변경_이력.md) | 24개 Wave의 테이블·Model·Migration·제약·당시 검증 통합 이력 |
| [T-005 Migration 불변성 사고·복구 보고서](technical/backend/t005_마이그레이션_불변성_사고_및_복구_보고서.md) | 적용 Migration 변조 원인·복원·후속 증분 Migration |
| [T-017A 합성 사용자 계정 관리 설계서](technical/backend/t017a_합성_사용자_계정_관리_설계서.md) | 합성 계정 수명주기·권한·감사 설계와 구현 Gate |
| [T-022 증상 제출 API 설계·계약 Gate](technical/backend/t022_증상_제출_api_설계_및_계약_게이트.md) | `SUBMIT_SYMPTOM` 첫 수직 Slice 구현 전 계약 |
| [백엔드·AI 계약·Runtime 통합 미해결 사항](technical/contracts/백엔드_ai_계약_런타임_통합_미해결_사항.md) | Schema Parity·Timeout·로그·검색 후검증·Revision·E2E |

### 4.4 팀 협업

| 문서 | 용도 |
| --- | --- |
| [백엔드 팀 검토·인계 체크리스트](team_handover/백엔드_팀_검토_및_인계_체크리스트.md) | 김은진·윤승혁·한예나·양정현·이동윤의 현재 요청과 반환 증거 |
| [팀 통합 인계 허브](../../handoffs/README.md) | 공용 기준선·Gate·인계 순서 |

## 5. 다음 작업 우선순위

| 순서 | 작업 | 현재 경계 | 협업 |
| ---: | --- | --- | --- |
| 1 | T-005 비작성자 독립 재현·공식 완료 검토 | 작성자 로컬 기술 완료 | 김은진 또는 지정 리뷰어·윤승혁 |
| 2 | T-017A 설계 검토 | 구현 전 OWNER 설계 | 윤승혁 정책·김은진 Migration/QA |
| 3 | T-022 `SUBMIT_SYMPTOM` 첫 수직 Slice | 계약 Gate와 구현 범위 문서화 | 윤승혁 State 입력 |
| 4 | Backend·AI Adapter·Evidence E2E | AI 계약·Runtime 잔여 Gap 존재 | 이동윤 |
| 5 | Web·Mobile 소비 검증 | PM `main` SHA 대기 | 한예나·양정현 |

각 작업은 한 범위만 구현하고 즉시 집중 검증한 뒤 다음 작업으로 이동한다.
다른 담당자의 계약 입력이 필요한 항목은 Mock·Stub까지만 진행하고 실제
연동 완료로 표시하지 않는다.

## 6. 파일명·경로 규칙

- 현행 문서는 `대상_기능_문서종류.md` 형태의 한글 파일명을 사용한다.
- WBS 식별자는 `t005`, `t017a`, `t022`처럼 통일한다.
- 단어는 밑줄로 구분하고 의미 없는 작성자명·시각·`final` 접미사를
  현행 파일명에 사용하지 않는다.
- 특정 시점의 검증 증거에만 `YYYYMMDD_` 날짜를 사용한다.
- 저장소 파일 링크는 상대경로만 사용한다.
- `C:\...`, `C:/...`, `file://...` 형식의 개인 PC 하이퍼링크를
  사용하지 않는다.
- `.env` 실제 값, Token, Password, DB Dump와 개인정보를 문서에 넣지 않는다.

## 7. 완료·이력 원칙

구현·테스트·작성자 검증 완료와 팀 공식 완료를 구분한다. 비작성자 재현,
소비자 호환성 검토와 PM 승인이 기록되기 전에는 `완료`로 확대 해석하지
않는다.

과거 2/32·10/32·12/32·13/32 단계, 개별 Wave 전문과 팀원별 인계 전문은
통합 문서와 Git 이력에서 확인한다. 이 README에는 현재 기준과 다음
행동만 유지한다.

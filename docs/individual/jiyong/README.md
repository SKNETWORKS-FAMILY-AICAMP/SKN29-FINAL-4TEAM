# WaterBridge Backend·Database 개발문서

> 작성·유지: 최지용 — Backend·Database
> 문서 원칙: 기능 구현·판정·재현 절차만 기록하고 요청·회신 대화는 남기지 않는다.

## 1. 문서를 보는 순서

이 폴더는 Backend·Database 구현을 이해하고 재현하기 위한 개인 개발문서다.
업무 일정과 완료 상태는 PM의 WBS, 계약은 `contracts/**`, 실제 동작은
Backend 코드·Migration·테스트를 우선한다.

1. 환경 구성은 `개발환경/`
2. Schema·Migration·Seed·Importer는 `데이터베이스/`
3. Login·JWT·RBAC·계정 수명주기는 `인증_권한/`
4. REST API와 상태 전이는 `API/`
5. AI·RAG·Web·Mobile·E2E 연결은 `연동_인계/`

## 2. 대표 문서

### 개발환경

| 문서 | 확인 내용 |
| --- | --- |
| [백엔드 로컬환경 설치·복구](개발환경/백엔드_로컬환경_설치_복구_가이드.md) | Python·venv·PostgreSQL·Django 실행과 복구 |
| [백엔드 공통환경 회귀검증](개발환경/백엔드_공통환경_회귀검증_가이드.md) | 환경 Fail-closed·Health·오류·로그·전체 회귀 |

### 데이터베이스

| 문서 | 확인 내용 |
| --- | --- |
| [Schema·Migration 구현](데이터베이스/데이터베이스_스키마_마이그레이션_구현_가이드.md) | Model·Migration·Registry·불변성 |
| [합성데이터 적재·재현](데이터베이스/합성데이터_시드_Importer_검증_가이드.md) | Seed·Importer·Replay·원장 |
| [팀 PostgreSQL 통합환경](데이터베이스/팀_PostgreSQL_통합환경_운영_가이드.md) | 역할 분리·공유 DB·비밀값·검증 경계 |

### 인증·권한

| 문서 | 확인 내용 |
| --- | --- |
| [Login·JWT·RBAC·계정관리](인증_권한/로그인_JWT_RBAC_계정관리_가이드.md) | 인증·역할·객체 권한·합성계정 |
| [계정 UUID·JWT 전환](인증_권한/계정_UUID_JWT_전환_복구_가이드.md) | 식별자 Migration·Token·Rollback |
| [계정 수명주기·감사·Row Lock](인증_권한/계정_수명주기_감사_RowLock_가이드.md) | 상태 변경·최종 관리자 보호·감사 원장·동시성 |

### API

| 문서 | 확인 내용 |
| --- | --- |
| [REST 계약·오류·로그 보안](API/REST_API_계약_오류_로그보안_가이드.md) | OpenAPI·오류 Matrix·Correlation·Redaction |
| [구독·제품·케어 이력 API](API/구독_제품_케어이력_API_가이드.md) | 구독·제품·케어 기록·다음 관리일 |
| [고객 문의·문진·상담 요청 API](API/고객_문의_문진_상담요청_API_가이드.md) | 문의 생성·증상·추가답변·상담 요청 |
| [상담사 문의·상담 API](API/상담사_문의_상담_API_가이드.md) | 상담사 목록·상세·전화 문의·상담 흐름 |
| [방문 일정·기사 배정 API](API/방문_일정_기사배정_API_가이드.md) | 방문 검토·생성·일정·확정·재방문 |
| [상태 전이·권한·멱등 API](API/상태전이_권한_멱등_API_가이드.md) | Guard·allowed actions·409·Replay·이력 |

### 통합

| 문서 | 확인 내용 |
| --- | --- |
| [Backend·AI 호출·추적·오류 처리](연동_인계/백엔드_AI_호출_추적_오류처리_가이드.md) | Commit 후 AI 호출·AIRun·Timeout·Correlation |
| [Backend·AI RAG 근거데이터 통합](연동_인계/백엔드_AI_RAG_근거데이터_통합_가이드.md) | Canonical ID·Crosswalk·Readonly View·Verifier |
| [Web·Mobile API 소비 확인](연동_인계/웹_모바일_API_소비_확인_가이드.md) | Remote Adapter·DTO·오류·Mock 경계 |
| [고객·AI·상담 통합 시나리오](연동_인계/고객_AI_상담_통합시나리오_검증_가이드.md) | Fresh Inquiry 기반 수직 E2E |

## 3. 문서 작성 규칙

- 파일명은 `기능_문서종류.md`로 작성한다.
- WBS 번호는 파일명이 아니라 본문의 `관련 WBS`에만 기록한다.
- 동일 기능의 계약·구현·검증·판정은 대표 문서 하나에서 관리한다.
- 특정 시점의 테스트 개수보다 재현 명령과 성공 조건을 우선한다.
- 작성자 검증, 독립 QA, PM 완료 판정을 구분한다.
- 비밀번호·Token·DSN·실제 고객 정보·개인 PC 절대경로를 기록하지 않는다.
- 다른 담당자의 구현 상태를 이 폴더에서 대신 판정하지 않는다.

## 4. 판단 우선순위

| 판단 대상 | Source of Truth |
| --- | --- |
| API Method·Path·Schema | `contracts/api/**` |
| 상태·Event·Guard | `contracts/state-machine/**` |
| AI 요청·응답 | `contracts/ai/**` |
| DB 구조 | Django Model·Migration·PostgreSQL |
| Runtime 완료 | Route·Service·Repository·실행 테스트 |
| 업무 완료 | PM WBS·공식 Gate |

설명과 코드가 다르면 계약과 실행 증거를 확인한 뒤 이 문서를 수정한다.

# 팀 PostgreSQL 통합환경 운영 가이드

> 관련 업무: Backend·AI·QA 공용 PostgreSQL·pgvector
> 원칙: 공용환경은 기능 구현 환경과 검증 환경을 구분한다.

## 1. 역할

| 역할 | 허용 범위 |
| --- | --- |
| Migrator | 승인된 Migration·Seed·권한 재조정 |
| Backend Runtime | 업무 테이블의 승인된 DML |
| Readonly QA | 검증용 SELECT |
| AI Readonly | 승인된 RAG View SELECT만 |

Web·Mobile은 DB Credential을 가지지 않고 Backend API만 사용한다.

## 2. 비밀값 주입

Endpoint·DNS·CA·Password·DSN은 Git·문서·채팅에 기록하지 않는다. 승인된
보호 저장소나 Loader가 현재 Process의 환경변수로 주입한다. 결과에는 값이
아니라 주입 여부와 연결 성공 여부만 기록한다.

주요 환경변수 이름은 `backend/.env.example`과 배포 스크립트를 기준으로 한다.

## 3. 구축 순서

1. PM이 환경 용도와 단일 Migrator를 지정
2. 환경 담당자가 PostgreSQL·pgvector·DNS·TLS·Role 준비
3. 최지용이 Migration Plan과 Dry-run 확인
4. Migrator Role로 Migration·Seed·Crosswalk 적용
5. Runtime·Readonly·AI Role 권한 재조정
6. 김은진이 연결·Schema·Replay·권한 Matrix 독립 검증
7. PM이 통합환경 사용 가능 상태 판정

## 4. 검증 항목

| 항목 | 성공 조건 |
| --- | --- |
| TLS | 승인된 Mode·CA·DNS 일치 |
| Migration | pending 0, drift 0 |
| Seed | Replay 비의도 생성 0 |
| Backend Role | 승인된 업무 DML 가능 |
| AI Role | RAG View SELECT 가능 |
| AI 제한 | Base Table SELECT·View DML·Schema CREATE 거부 |
| QA Role | 필요한 읽기 검증 가능 |
| 비밀값 | 로그·문서·Git 노출 0 |

## 5. 공용환경에서 금지

- pytest의 Flush·TransactionTestCase 실행
- 개인 개발용 Migration 실험
- `docker compose down -v`, Drop DB, 기존 Volume 삭제
- Runtime Process에 Migrator Credential 상시 주입
- AI Index Builder·UPSERT 명령을 Readonly Role로 실행

## 6. 환경 차단 판정

Connection Timeout, DNS·CA 불일치, Credential 미주입은 코드 실패가 아니라
`ENVIRONMENT_BLOCKED`다. Unit Test PASS로 실제 PostgreSQL Role·View·RAG
검증을 대체하지 않는다.

## 7. 완료 판정

동일 코드 기준에서 Migration·Seed·권한 Matrix·Backend API·AI Readonly 검색이
재현되어야 통합환경 준비 완료다. 전체 서비스 E2E 완료와는 별도다.

# WaterBridge 프로젝트 문서

> 기준일: 2026-08-02
>
> 상태: 팀 공용 문서 진입점
>
> 원칙: 기계 계약·실제 Runtime·공식 WBS 상태·설명 문서를 서로 구분한다.

이 디렉터리는 WaterBridge 파이널 프로젝트의 계약, 데이터베이스, 인계와
제출 문서를 팀원과 외부 검토자가 함께 읽을 수 있도록 정리한 공개 문서
모음이다. 설계 후보나 작성자 로컬 검증은 팀 승인·병합 또는 WBS 완료를
자동으로 뜻하지 않는다.

## 문서 바로가기

| 구분 | 문서 | 용도 |
|---|---|---|
| API | [API 문서 안내](api/README.md) | 기계 계약·Runtime·설계 후보의 구분과 관련 문서 안내 |
| API | [WaterBridge Public API 명세](api/waterbridge_api_specification.md) | 확정된 OpenAPI와 후속 설계 백로그를 구분한 사람용 명세 |
| API | [API Runtime 구현 상태](api/runtime_implementation_status.md) | OpenAPI Operation과 실제 Django Route의 현재 매핑 |
| ADR | [Architecture Decision 안내](adr/README.md) | 유효·부분 대체·역사 보관 결정을 구분한 인덱스 |
| 데이터베이스 | [데이터베이스 문서 안내](database/README.md) | 물리 계약, ERD와 데이터 사전 안내 |
| 데이터베이스 | [WaterBridge 테이블 명세](database/waterbridge_table_dictionary.md) | 32개 업무 테이블의 사람용 데이터 사전 |
| ERD | [대화형 ERD](database/erd/waterbridge_erd.html) | 테이블 검색, 관계 탐색과 전체 필드 조회 |
| ERD | [ERD 정적 미리보기](database/erd/waterbridge_erd.png) | GitHub에서 바로 확인하는 관계도 이미지 |
| 인계 | [팀 통합 인계 허브](handoffs/README.md) | 현재 검토 Gate, 역할별 반환 증거와 경로 안내 |
| 기획 | [AI·RAG 실험 페이지 구현 실행계획](planning/20260810_AI_RAG_실험_구현_실행계획.md) | 기존 데이터 정비부터 청킹·검색·모델 비교·실험 UI·조건부 데이터 수집까지의 실행 순서 |
| 제출 | [데이터베이스·저장소 설계](submission/database-storage-design.md) | DB·pgvector·합성 데이터 저장 경계 |
| 제출 | [데이터 전처리 결과](submission/data-preprocessing-result.md) | 데이터 버전·검증·DB/RAG 실행 스냅샷 |
| 개발 기록 | [Backend·Database 개발 문서](individual/jiyong/README.md) | 구현·검증·복구·연동 인계의 주요 문서 인덱스 |

## 판정 우선순위

서로 다른 문서의 표현이 충돌하면 판정 대상에 맞는 원본을 사용한다.

1. REST Method·Path·Schema, 오류 코드, 상태 전이와 AI 입출력은
   `contracts/**`의 기계 판독 계약을 기준으로 한다.
2. 실제 지원 기능은 `backend/**`의 Route·View·Serializer·Model·Migration과
   같은 변경 묶음에서 실행한 테스트 증거로 판정한다.
3. 공식 일정·담당·완료 상태는 `docs/planning/md/WBS.md`와 PM의 검토 기록을
   기준으로 한다. 작성자 구현 완료와 WBS 완료를 합치지 않는다.
4. `docs/**` Markdown과 ERD는 위 원본을 사람이 이해하기 위한 설명·인계
   자료다. 날짜가 있는 테스트 수치는 해당 실행 시점의 스냅샷이다.

## 현행 구현 경계

- 제품 표시명과 현행 기본 PostgreSQL 데이터베이스는 `WaterBridge`와
  `waterbridge`다.
- 현행 Django 실행 진입점은 `backend/manage.py`, 현행 기계 계약은
  `contracts/**`다.
- `WaterCareBackend/**`와 이를 호출하는 구형 BAT 파일은 과거 Android
  연동 참고본이며 현행 Runtime 판정 원본이 아니다.
- `watercare_`가 포함된 일부 파일명·Compose 프로젝트명·Volume명은 링크나
  기존 데이터 보존을 위한 호환 식별자다. 문서 본문의 현재 제품명이나 DB
  이름으로 해석하지 않는다.

## 공개 범위

- 실제 개인정보 대신 가명·합성 데이터의 구조와 검증 원칙만 기록한다.
- `.env`, 비밀번호, Token, Secret, 운영 Dump와 개인 PC 절대경로를 문서에
  넣지 않는다.
- Backend가 인증·권한·업무 상태의 최종 책임을 가지며 AI는 상태를 직접
  변경하지 않는다.

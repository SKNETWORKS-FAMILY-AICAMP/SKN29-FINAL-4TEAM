# WaterCare 설계 문서

> 상태: **API·DB OWNER 기준선 확정, Runtime·소비 검증 진행 중**
>
> 이 디렉토리는 제3자와 팀원이 함께 읽을 수 있도록 정리한 공개용 설계 문서 모음이다. 문서에 기술된 후보 계약은 구현·Migration·테스트가 완료되었다는 의미가 아니다.

## 문서 바로가기

| 구분 | 문서 | 용도 |
|---|---|---|
| API | [API 문서 안내](api/README.md) | 공개 API 범위, 계약 우선순위와 관련 문서 안내 |
| API | [WaterCare API 명세](api/watercare_api_specification.md) | 사람이 읽는 Public API 계약 초안 |
| 데이터베이스 | [데이터베이스 문서 안내](database/README.md) | 스키마 범위, ERD와 데이터 사전 안내 |
| 데이터베이스 | [WaterCare 테이블 명세](database/watercare_table_dictionary.md) | 32개 설계 테이블의 단일 Markdown 데이터 사전 |
| ERD | [대화형 ERD](database/erd/watercare_erd.html) | 테이블 검색, 관계 탐색과 전체 필드 조회 |
| ERD | [ERD 정적 미리보기](database/erd/watercare_erd.png) | GitHub에서 바로 확인하는 관계도 이미지 |
| 개발·인계 | [API 계약 개발·인계 가이드](individual/jiyong/technical/backend/api_contract_handover_guide.md) | 계약 변경, 검증과 역할별 협업 절차 |
| 개발·인계 | [DB 스키마 개발·인계 가이드](individual/jiyong/technical/backend/database_schema_handover_guide.md) | Model·Migration·Seed·검증 인계 절차 |

## 기준 우선순위

1. API Method·Path·Schema의 기계 기준은 최지용 OWNER가 관리하는
   `contracts/api/**`이며, 개별 항목의 구현 성숙도는
   `x-contract-status`와 Runtime 증거로 구분한다.
2. State 업무 규칙의 입력 원본은 윤승혁(PM)의
   `contracts/state-machine/**`, AI 입출력 Schema의 입력 원본은
   이동윤의 `contracts/ai/**`다.
3. 실제 데이터베이스 구현 범위는 해당 Branch·Commit에서 검증한 Django
   Migration과 PostgreSQL 적용 결과로 판정한다.
4. 이 디렉토리의 Markdown과 ERD는 계약과 스키마를 사람이 이해하기
   위한 공개 설명본이다.
5. 미완성 항목은 `OWNER 정합화`, `PM State 입력`, `AI 계약 입력`,
   `소비자 호환성 검토`로 구분한다. 소비자·PR 검토는 작성 후 품질
   게이트이며 최지용 산출물 작성의 선행 승인이 아니다.

## 현행 구현 경계

- 현행 Django Runtime은 `backend/**`, 기계 계약은 `contracts/**`를
  기준으로 한다.
- 루트 `WaterCareBackend/**`와 이를 호출하는 구형 BAT 파일은 과거
  Android 연동 starter 참고본이다. 현행 Migration·API·State·AI 계약을
  판정하거나 실행하는 권위 원본이 아니다.
- 문서에 기록된 과거 테스트 수는 해당 실행일의 스냅샷이다. 현재 Branch
  완료 판정에는 같은 Commit에서 다시 실행한 결과를 사용한다.

## 공개 범위

- 합성 데이터 사용 원칙과 스키마 구조만 설명한다.
- 실제 개인정보, 인증 토큰, 비밀키, 내부 저장 경로와 원본 작업 이력은 포함하지 않는다.
- Backend가 상태와 권한의 최종 책임을 가지며, AI는 업무 상태를 직접 변경하지 않는다.

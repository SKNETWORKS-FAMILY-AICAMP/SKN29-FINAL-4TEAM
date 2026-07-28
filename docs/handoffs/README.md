# WaterCare 현재 작업 인계

> 기준일: 2026-07-28
> 원칙: 최신 실행·검증 문서만 연결하며, 저장소 밖 경로와 개인 PC 절대경로는 사용하지 않는다.

## 현재 인계 기준

| 범위 | 기준 문서 | 현재 상태 | 다음 작업 |
| --- | --- | --- | --- |
| Django·PostgreSQL·Auth 공통 기반 | [공유 패키지 인계서](<../individual/jiyong/manuals/20260728_최지용_Django_PostgreSQL_공유패키지_인계서_v1.1.md>) | 새 `.venv`: Python 3.13.13·전체 `239 passed`; PostgreSQL 16.14·Migration은 2026-07-28 재검증 통과 | 새 PC는 4장, 설치 완료 PC는 5장의 일상 실행·종료·재시작 순서 사용 |
| T-005 데이터 설계·DB 구현 | [T-005 기준 패키지](<../database/t-005/README.md>) · [DB 스키마 개발 가이드](<../individual/jiyong/technical/backend/database_schema_handover_guide.md>) | ERD·테이블 명세 확정, Runtime은 32개 중 2개 | Wave 1 구현·검증 후 Wave 2 진행 |
| API 계약 | [Public API 명세](<../api/watercare_api_specification.md>) · [API 계약 개발 가이드](<../individual/jiyong/technical/backend/api_contract_handover_guide.md>) | 최지용 작성 기준선 확정, Runtime 정합화는 기능별 진행 | 계약·Route·테스트를 한 단위로 갱신 |
| T-022 문의 관리 | [T-022 현재 준비도](<../individual/jiyong/technical/backend/t-022-inquiry-readiness.md>) | 계약 기준선은 있으나 Model·Migration·Route·Runtime 미구현 | T-005 선행 Wave 검증 후 수직 구현 |
| T-023 Workflow | [T-023 현재 준비도](<../individual/jiyong/technical/backend/t-023-workflow-readiness.md>) | PM 계약 6영역 교차검증 통과, Loader·Validator 구현, Engine·Model·Route Runtime 미구현 | Engine부터 한 수직 단계씩 구현·검증 |

## 역할 경계

- ERD·테이블 명세·API 명세의 작성과 최신화는 최지용 담당이다. 이를 시작하기 위한 별도 팀 승인은 필요하지 않다.
- 팀원 검토는 소비자 코드와의 호환성 확인, PR 리뷰, 동일 환경 재현을 위한 절차다.
- T-023의 상태 전이·Guard·역할별 허용 동작은 PM 계약 입력이므로, 최지용 명세 작성과 구분해 추적한다.
- 완료 판정은 문서 존재가 아니라 Model·Migration·App·Route·Runtime 테스트와 PostgreSQL 실행 증거를 함께 본다.
- 현행 Runtime은 `backend/**`, 계약은 `contracts/**`가 원본이다. 루트
  `WaterCareBackend/**`와 구형 BAT 파일은 과거 starter 참고본이며
  인계 실행 기준이 아니다.
- 문서의 테스트 수는 기록일 스냅샷이다. 현재 Branch 완료 판정에는
  같은 Commit에서 다시 실행한 결과를 사용한다.
- 완료 증거 JSON의 `team_review` 키는 기존 검사기 호환 이름이다.
  최지용 산출물의 선행 승인이 아니라 소비 호환성·실행 재현·비작성자
  PR 리뷰를 기록한다.

## 인계 시 필수 확인

1. [공유 패키지 인계서](<../individual/jiyong/manuals/20260728_최지용_Django_PostgreSQL_공유패키지_인계서_v1.1.md>)대로 환경을 재현한다.
2. 비밀값은 `.env`에만 두고 로그·문서·커밋에 포함하지 않는다.
3. 기능별로 `작업 → 검증 → 작업 → 검증` 순서를 지킨다.
4. 계약 변경 시 OpenAPI·Django Route·테스트·사람용 명세를 같은 변경 단위에서 맞춘다.
5. 새 인계 문서를 중복 생성하지 않고 위 기준 문서를 갱신한다.
6. 서버를 다시 켤 때는 환경 설치·Seed를 반복하지 않고 공유 패키지 인계서 5장의 일상 실행 절차를 사용한다.

# Backend DB 적재 검증 기록

- 현재 상태: `USER_CONFIRMED_EVIDENCE_PENDING`
- 사용자 확인: Backend DB 적재는 정상 완료
- 데이터 판정: `DOCUMENTED_NOT_DB_VERIFIED`
- 금지 판정: Backend Runtime 전체 `DB_VERIFIED`

## 승격에 필요한 증빙

| 항목 | 현재 값 |
|---|---|
| Backend commit | 확인 필요 |
| Migration 버전 | 확인 필요 |
| 실행 명령·환경 | 확인 필요 |
| 테이블별 최초 적재 건수 | 확인 필요 |
| FK·제약 오류 | 확인 필요 |
| 두 번째 적재 추가 건수 | 확인 필요 |
| 012·016 제외 | 확인 필요 |
| fixture PK 직접 주입 금지 | 확인 필요 |
| 미확정 Care mapping 제외 | 확인 필요 |

모든 항목이 비밀값 없는 실행 로그로 확인되면 데이터 handoff만
`DB_LOAD_VERIFIED`로 승격한다.

데이터 자체의 최신 검증은 단위 테스트 55/55와 QA 오류·경고 0건이다.
이는 Backend DB 적재 증빙을 대신하지 않는다.

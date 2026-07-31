# T-005 잔여 전환 브리지 실데이터 감사·인계

> 기준일: 2026-07-30  
> 담당: 최지용  
> 검증 방식: 현재 Model·Migration·367건 Importer·격리 PostgreSQL 읽기 전용 대조  
> 상태: `AUDITED_NO_MUTATION`

## 1. 감사 목적

T-005 신규 부모·자식 테이블 구현 후 남은 UUID 호환 필드를 실제 정수 FK로
전환할 수 있는지 확인했다. 값의 업무 의미가 확정되지 않은 경우 `NULL`이나
방문 후 결과를 이용해 사전 데이터를 임의 생성하지 않았다.

## 2. 결론

| 대상 | 판정 | 현재 데이터 근거 | 다음 단계 |
| --- | --- | --- | --- |
| Inquiry → QuestionnaireSession | 2단계 전환 가능 | Inquiry 22건의 bridge가 모두 `NULL`; 정식 관계는 QuestionnaireSession의 OneToOne FK | 링크 서비스·dual-write 후 bridge 제거 |
| CareRecord → VisitResult | 부분 전환 가능 | Care 25건 중 Visit 연결 1건; 완료 Visit 3건이 결과 생성 후보 | 결과 필드 의미 매핑 승인 후 1건 연결 |
| Visit → HandoffReport | 계약·원천 데이터 대기 | Visit 4건 모두 상담 후보는 있으나 사전 인계 내용·상태·확인 원천 없음 | 상태·payload·확인자·Importer 계약 승인 후 전환 |

현재 bridge 값이 모두 `NULL`이어서 orphan이 0건인 것은 전환 준비 완료를
뜻하지 않는다. 실제 신규 부모 행과 의미 매핑을 만들 수 있어야 완료다.

## 3. QuestionnaireSession 전환

[QuestionnaireSession](../../../../../backend/apps/questionnaires/models/questionnaire_session.py)은
이미 Inquiry를 nullable OneToOne FK로 보유한다. 따라서
[Inquiry](../../../../../backend/apps/inquiries/models/inquiry.py)에 반대 방향
FK를 추가하면 같은 관계를 중복 저장하게 된다.

안전한 순서:

1. 문진 제출 상태, 같은 구독, 미연결 상태를 확인하는 링크 서비스를 만든다.
2. 링크 transaction에서 `QuestionnaireSession.inquiry`를 설정한다.
3. 한 릴리스 동안 기존 `questionnaire_session_public_id`도 dual-write한다.
4. 조회를 `inquiry.questionnaire_session` 역관계로 전환한다.
5. backfill·불일치 0건을 검증한 뒤 bridge 필드를 제거한다.
6. 역Migration은 정식 FK의 `QuestionnaireSession.public_id`로 bridge를
   복원해야 한다.

## 4. VisitResult 전환

[CareRecord](../../../../../backend/apps/care/models/care_history.py)의 기존
`visit_result_public_id`를
[VisitResult](../../../../../backend/apps/visits/models/visit_result.py) 정수
FK로 바꾸려면 먼저 완료 Visit 3건의 결과 행을 만들 수 있어야 한다.

현재 승인되지 않은 매핑:

- `inspection_summary`
- `resolved_on_site`
- 재방문 사유
- 결과 생성 idempotency key
- 결정적 공개 UUID 생성 규칙

권장 순서:

1. 데이터·방문 업무 담당자가 위 매핑을 승인한다.
2. 완료 Visit 3건에 대한 VisitResult를 생성하고 제약을 검증한다.
3. CareRecord에 nullable `visit_result_id bigint` FK를 추가한다.
4. Visit을 통해 확인되는 CareRecord 예상 1건만 backfill한다.
5. 서비스 dual-read·dual-write 후 UUID bridge를 제거한다.

나머지 CareRecord 24건이 `NULL`인 것은 방문 결과와 무관한 정상 범위다.

## 5. HandoffReport 전환

[HandoffReport](../../../../../backend/apps/visits/models/technician_report.py)는
사전 인계 자료다. 방문 후 기록인 `confirmed_cause`나 `action_taken`으로
이를 backfill하면 미래 정보를 과거 입력으로 사용하는 시간 누수가 된다.

현재 누락된 선행 계약:

- 승인된 Handoff 상태 코드와 전이 규칙
- 제품·증상·시도 조치·위험·근거·우선순위 payload 원천
- AI 초안 생성 여부와 AIRun 연결 규칙
- 실제 상담사 확인자와 확인 시각
- [367건 Importer](../../../../../backend/apps/operations/services/operations_service.py)의
  source·crosswalk 매핑

승인 후 순서는 HandoffReport 생성, Visit nullable FK 추가, 같은 Inquiry와
확정 상태 검증, backfill 검증, 필요 시 NOT NULL 강화, 복합 무결성 제약
적용이다.

## 6. 담당·협업 경계

| 작업 | 주담당 | 필수 협업 |
| --- | --- | --- |
| 문진 링크 서비스·Migration | 최지용 Backend/DB | Inquiry·Questionnaire API 담당, PM, 데이터 QA |
| VisitResult 생성·Care FK | 최지용 Backend/DB | 데이터 매핑 담당, 방문 업무 담당, PM |
| Handoff 계약·Visit 연결 | PM·AI 담당 선행 | 최지용 DB, Importer·QA 담당, 상담·기사 API 담당 |

이 감사에서는 코드, Migration, Seed, Importer, PostgreSQL 데이터 어느 것도
변경하지 않았다.

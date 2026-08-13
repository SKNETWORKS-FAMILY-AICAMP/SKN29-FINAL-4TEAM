# D04 행 단위 Parent·Child 전처리 핵심 요약

> 작성일: 2026-08-12 KST
> 상태: `EXECUTED_DATA_GENERATION_ONLY`

## 무엇을 만들었나

JAC104/JCC104 공식 매뉴얼의 5·7·37·38·39쪽만 대상으로 실험용 Parent·Child 데이터를 만든다.

- Parent: 페이지 전체 5건
- Child: 실제 안전 문단·표 행 기준 15건
- Evidence Group: 기존 7개 ID 재사용
- 출력: Parent JSONL, Child JSONL, Manifest, QA JSON 총 4개
- 기존 B1 v1·MVP·Gold·AI Runner는 변경하지 않음

데이터 생성과 QA까지 실행했으며, AI Runner 연결·B1 재실행·운영 적용은 실행하지 않았다.

생성 결과 Hash:

- Parent: `FDE0EFE1275114F8BE3DE190055251D411C1A38A705E8E929F08998675DDC05D`
- Child: `8949C6DD03EE57C87F73E8740F82BD26DAE17259DAF0E85D80D62C4B8FC97ACA`
- Manifest: `B47A1C61A7C2B0EDBE5AB1113D44E13C255D847F05FB473F4B0573DDED38576A`
- QA: `AE013B1FB4A25CA2C5EF51D2A38590B99696B711B39CAB3834541AB39D4D4162`

QA는 15개 항목 모두 `PASS`였고, 동일 입력으로 재생성한 결과 Hash도 동일했다. 기존 data 영역 단위 테스트 76건도 `OK`였다.

## 회신 반영 결론

- 이동윤이 선택한 C안을 사용한다.
- 검색과 평가는 Child만 사용한다.
- 선택된 Child의 Parent는 답변 문맥으로만 한 번 확장한다.
- `child_only_v2`는 대조군으로 남긴다.
- 누수 5·7·38쪽은 서로 다른 정답 3개가 아니라 Evidence 하나의 Source Variant 3개다.
- 운영 적용은 승인되지 않았으며 experimental Adapter 검증 후 다시 결정한다.

## 원본을 보고 수정한 Child 수

PM 예시만 따르면 Child 수가 적게 보이지만 실제 PDF 표의 행은 더 나뉜다.

| 페이지 | Child 수 | 구분 |
|---:|---:|---|
| 5 | 1 | 누수 안전조치 |
| 7 | 1 | 누수 안전조치 |
| 37 | 4 | 냉수 정상 조건, 냉각부 고장, 무출수, 소음 |
| 38 | 5 | 누수, 맛·냄새, 출수량 저하, 스팀, 온수 끊김 |
| 39 | 4 | 미지근한 온수, 온수 미출수, 모듈 점검 표시, 점검 중 온수 중단 |
| 합계 | 15 | 7개 Evidence Group |

38쪽 `정수된 물에 미세한 입자 발생` 행은 PM 요청 범위가 아니므로 Child에서는 제외한다. 페이지 전체 Parent에는 남는다.

## ID를 어떻게 정리할 것인가

두 회신의 누수 Variant 표기가 다르므로 다음처럼 양쪽을 보존한다.

| 용도 | 값 예시 |
|---|---|
| 검색 정답 Group | `EVD-WPUJAC104DWH-LEAK-001` |
| 데이터 canonical Variant | `LEAK-001-P005` |
| PM 지정 전체 Variant 별칭 | `EVD-WPUJAC104DWH-LEAK-001-P005` |

짧은 ID는 Child의 `source_variant_id`에 사용하고, 전체 ID는 Manifest의 별칭 매핑에 기록한다. 7·38쪽도 같은 규칙을 적용한다.

## 실행 승인 후 순서

1. 시작 HEAD와 입력 Hash 재확인
2. Parent 5건 생성
3. Child 15건 생성
4. Child마다 기존 Evidence Group 1개만 연결
5. 원본 위치를 페이지·줄·행 라벨·텍스트 anchor로 기록
6. 출력 Hash와 ID 별칭을 Manifest에 기록
7. QA로 건수·연결·중복·누락·Gold 오염·결정성을 검사
8. 기존 파일에 예상 밖 diff가 없는지 확인
9. 산출물 4개를 이동윤에게 전달
10. 이동윤이 두 대조군을 연결하고 B1을 다시 실행

## 완료 Gate

- Parent 5건, Child 15건
- 고아 Child 0건
- Child당 Evidence Group 정확히 1개
- 누수 P005·P007·P038 Variant 모두 보존
- 모든 Child의 원본 위치 역추적 가능
- 38쪽 미세입자 Child 0건
- Gold 질문 문장 전체 복사 0건
- 동일 입력 재생성 시 출력 Hash 동일
- 기존 B1·MVP·Gold·`ai/**` 변경 0건

## 아직 결정되지 않은 것

데이터 생성은 끝났지만, 다음 항목은 후속 실험 결과로 결정해야 한다.

1. 페이지 전체 Parent가 답변 Context에 불필요한 행을 너무 많이 넣는지
2. `child_parent_context_v2`가 `child_only_v2`보다 답변 관련성과 안전 문구 보존에서 실제로 나은지
3. Parent 확장에 드는 Token과 지연시간이 허용 가능한지
4. 영향 11건과 정상 통제 표본에서 회귀가 없는지
5. 조건을 통과한 v2를 정식 Runner와 운영 후보로 승격할지

세부 Child 15건의 행 범위, 필드, QA와 중지 조건은 [상세 계획](./d04-row-child-preprocessing-plan_20260812.md)에 기록했다.

# 3모델 RAG 평가 기준·Capability Rule 결정 요청

> 상태: `RESOLVED` (2026-08-19). Evidence Group 단위 Top-5, 총 50건,
> 모델별 Capability Rule이 승인되어 구현·재평가까지 완료했다.

3모델 RAG 데이터를 실제 pgvector에 적재해 49개 Case를 평가했습니다. 정상 질문은
43건 모두 기대 Evidence Group이 Top-5에 포함됐고 교차 모델 검색은 없었습니다.
부정 질문은 6건 중 4건만 No Evidence로 처리되어 최종 결과는 47/49입니다.

남은 두 건은 IAC425와 IAC606에서 다른 모델의 조작 방법을 묻는 경우입니다. 평가
정답을 코드에 직접 넣어 차단하지 않으려면 모델별로 허용되지 않는 조작·기능과
Rule ID를 확정해 주셔야 합니다.

함께 결정이 필요한 내용은 다음 세 가지입니다.

1. 정상 합격 기준을 “기대 Evidence Group의 검증된 Variant 중 하나가 Top-5에
   포함”으로 확정해 주세요. 한 Group에 Variant가 6개인 사례가 있어 모든 Variant를
   Top-5에 포함하는 현재 조건은 충족할 수 없습니다.
2. 현재 빠져 있는 존재하지 않는 모델 Negative Case를 추가해 총 50건으로 늘릴지,
   기존 부정 Case 하나와 교체해 49건을 유지할지 결정해 주세요.
3. IAC425·IAC606의 모델별 조작 불일치 차단 Rule ID와 차단 기준을 전달해 주세요.

결정 내용을 받으면 해당 Rule을 검색 전 Gate에 반영하고 전체 Case를 다시
검증하겠습니다. 그전까지 현재 결과는 성능 PASS나 Runtime 활성화로 표시하지
않습니다.

## 결정 반영 결과

- 평가 계약: 정상 43건 + 부정 7건 = 총 50건
- 검색 전 Gate: `RAG-GATE-MODEL-CAPABILITY-001`
- 모델별 Rule: `CAP-WPUIAC425SNW-DISPENSE-CONTROL-001`,
  `CAP-WPUIAC606SNW-DISPENSE-CONTROL-001`
- 실제 Disposable pgvector 평가: `50/50`, 교차 모델·Parent 직접 반환·미검증
  Evidence 각 0건
- Runtime 활성화: `NOT_APPROVED` — Backend·Public API 계약 확장 대기

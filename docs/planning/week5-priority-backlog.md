# 5주차 우선순위 Backlog

> 기준일: **2026-08-07 KST**
> 기간: **2026-08-10 ~ 2026-08-14**
> 진입 기준: [5주차 진입 조건](week5-entry-criteria.md)
> 운영 원칙: **Gate 복구 → 최소 수직 연결 → AI·RAG 안전 기능 → 소비자 연결**

## 1. P0 — 진입 Gate와 이관 결함

| 순서 | Backlog | 담당 | 선행 | 결과물·완료 증거 | 목표 | 상태 |
|---:|---|---|---|---|---|---|
| 1 | `W5-G01` 3.3·3.6 기준선 Commit과 Issue 대조 | 윤승혁·김은진 | - | Commit, WBS·Issue 링크, 담당자 회신 | 8/10 | 준비 중 |
| 2 | `W5-G06` Backend Python·Test·Migration Gate 복구 | 최지용·김은진 | 기준 Commit | Python 3.13.13, pytest 집계, Migration Drift | 8/10 | 차단 |
| 3 | `W5-G04` AI Test·팀 DB pgvector 재현 | 이동윤·김은진 | 대표 Data·DB 접속 | AI Test, Index 로그, 제품·증상 Filter 평가 | 8/10 | 차단 |
| 4 | `W5-G09` Mobile SDK Platform Gate 복구 | 양정현·김은진 | 기준 Commit | Core·Customer·Technician Test, APK | 8/10 | 차단 |
| 5 | `W5-G05` AI Schema–State Event Mapping 확정 | 이동윤·최지용 | 계약 1.0.0 | 요청·응답 Schema, Event·오류·Fallback Mapping Test | 8/10 | 검토 대기 |
| 6 | `W5-G07` Backend–AI 최소 수직 연결 | 최지용·이동윤 | `W5-G05`, `W5-G06` | 증상 제출→HTTP→검증→Event→DB 저장·추적 ID E2E | 8/11 | 미착수 |
| 7 | `T-019`·`T-022`·`T-023` 잔여 Runtime 재계획 | 최지용 | `W5-G06`, 계약 Gate | Care·Inquiry·Action별 구현 범위, Test와 5주차 목표일 | 8/11 | 인계 준비 |
| 8 | `T-040`·`T-041` 상담·방문 Operation 인계 확정 | 최지용·한예나 | `T-023` 대상 Action Runtime | OpenAPI·DB·409·멱등 Test와 Web Remote 연결 순서 | 8/14 | 계약 전용 |

## 2. P0 — 5주차 AI·RAG·안전 구현

| 순서 | WBS | 담당 | 선행 산출물 | 완료 증거 | 목표 | 상태 |
|---:|---|---|---|---|---|---|
| 9 | `T-025` 단일 RAG·선택형 책임 분리 비교 | 이동윤 | `W5-G02`, `W5-G05` | 동일 입력·출력 Fixture, 비교 결과, 선택 결정 | 8/10~8/11 | 미착수 |
| 10 | `T-027` 위험·사용 안내 분류 | 이동윤 | 안전 규칙·구조화 Schema | 위험 조합·표현 변형·금지 출력 Test | 8/11~8/12 | 미착수 |
| 11 | `T-026` 추가 질문 소비자 연동 | 이동윤·최지용 | `W5-G07`, 질문 Schema | Backend Event·DB, Web·Mobile DTO Test | 8/12 | 부분 구현 |
| 12 | `T-028A` 제품·세대 기반 검색 | 이동윤 | `W5-G03`, `W5-G04`, `T-027` | 공식 근거·페이지·관리 이력 구조화 출력 | 8/12~8/13 | 미착수 |
| 13 | `T-028B` `EvidenceCardDTO` Backend 조립 | 최지용 | `T-028A`, 계약 Example | 응답 DTO, 내부 경로·원문 비노출 Test | 8/13~8/14 | 미착수 |
| 14 | `T-031` 근거 없음 Guard | 이동윤 | `T-027`, `T-028A` | 임의 자가조치 차단·상담 필요 상태 Test | 8/13~8/14 | 미착수 |
| 15 | `T-032` Timeout·Retry·Fallback E2E | 이동윤·최지용 | `W5-G07`, `T-031` | Timeout·1회 재시도·안전 Template·상담 Event·DB Test | 8/14 | 부분 구현 |

## 3. P1 — 발표 피드백 대응

| Backlog | 담당 | 결과물 | 범위 통제 |
|---|---|---|---|
| 역할별 기대효과와 KPI 산식 | 윤승혁·김은진 | 고객·상담사·기사·기업 KPI 정의 | 실측 전 절감률 주장 금지 |
| 임베딩 후보 비교 계획 | 이동윤·김은진 | Recall·MRR/nDCG·지연·메모리·Hard Negative 표 | 비교 전 `bge-m3` 최적 주장 금지 |
| 생성 모델 성능·비용 비교 계획 | 이동윤 | Schema 성공률·안전·지연·비용 평가안 | 실제 연결 전 후보 모델로 표현 |
| 대표 문의 1건과 사용자 Label | 윤승혁·한예나·양정현 | 역할·상태 Label이 있는 최종 발표 흐름 | 미구현 화면은 설계안 표시 |
| Migration 범위 설명 | 최지용·김은진 | 계약·적용·활성·제외 Table 수와 이유 | 코드 검산 전 숫자 사용 금지 |
| 경쟁·배포 방식 검토 | 윤승혁·이동윤 | 공개 근거 Benchmark, 외부·로컬·Hybrid 비교 | 경쟁사 내부 시스템 단정 금지 |

## 4. 주간 Exit 조건

- `W5-G04`~`W5-G07`의 실행 증거가 확보됐다.
- `T-025` 비교 결정과 `T-027` 안전 분류 Test가 있다.
- `T-028A` 검색 결과가 `T-028B` DTO로 전달되는 계약·Runtime 경계가 확인된다.
- Timeout·근거 없음 실패가 안전 Template 또는 상담 전환으로 종료된다.
- WBS·Issue·인계 문서가 같은 담당자·상태·목표일을 나타낸다.

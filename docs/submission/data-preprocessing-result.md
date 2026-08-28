# WaterBridge 데이터 전처리 결과서

## 현재 기준

- 최신 문서일: 2026-08-28
- 데이터셋 버전: `1.3.0`
- 원격 main 문서 HEAD: `7a12f676437dd077c8e29e3c7163673163bd1cf3`
- 코드·Runtime 검증 기준: `95f90f843124373fc97c6cd9e258b1427e0cbde8`
- 공식 매뉴얼: 3종, 144쪽
- 3모델 RAG: Parent 15건, Child 53건, Evidence Group 43건
- 평가 계약: 50건(양성 43건, 음성 7건)
- Full Corpus v3: 검색 후보 132건
- 합성 원본 시나리오: 24건
- 활성 문의: 22건
- 합성 Fixture: 369건
- 상태이력·Audit: 각각 125건

지원 데이터·평가 판매 코드는 `WPUJAC104DWH`, `WPUIAC425SNW`,
`WPUIAC606SNW`다. 검색 전에 `exact_sales_code`를 적용하며 교차 모델
Fallback을 금지한다. `WPU-IAC506`은 신규 데이터·검색·화면·시연에서
사용하지 않는다.

## 전처리 결과

| 구분 | 결과 |
|---|---:|
| JAC104 공식 매뉴얼 | 44쪽 |
| IAC425 공식 매뉴얼 | 52쪽 |
| IAC606 공식 매뉴얼 | 48쪽 |
| RAG Parent | 15건 |
| RAG Child | 53건 — 제품별 15/19/19 |
| Evidence Group | 43건 |
| 검색 평가 | Positive 43/43, Negative 7/7, 교차 모델 Hit 0 |
| 공식 FAQ | 정규화 119, 후보 20, OCR 5, 자산 10 |
| Full Corpus v3 | 132건 — Child 37, Context Parent 11, Evidence Group 34 |

공식 PDF 원문은 Git에 저장하지 않는다. URL, 문서 버전, 페이지,
SHA-256과 Source Span 검수 기록으로 계보를 관리한다.

## 품질·재현성

`data/processed/validation/latest_qa_summary.json`의 저장된 정규 Pipeline
QA는 2026-07-29 기준 60개 파일·990개 레코드, 오류 0건·경고 0건이다.

2026-08-28 현재 데이터 단위 테스트는 142개가 통과했다. 검증 범위는
Schema, ID/FK, 상태이력, 멱등성, 3모델 격리, Full Corpus v3, 대표 E2E와
byte 결정성을 포함한다.

`SYN-JAC104-012`, `SYN-JAC104-016`은 원본에 보존하지만 기존 State
Machine 계약과 충돌하므로 활성 projection에서 제외한다. 기존 방문 Fixture는
P1 회귀 자료로 보존하며 P0 핵심 MVP 완료 증거와 구분한다.

## DB·RAG 판정

- Disposable pgvector 후보 검색은 50/50 PASS이며 교차 모델 Hit는 0건이다.
- `ai/configs/index_manifest_3model.json`에는 53건 Index가 기록되어 있다.
- Public Runtime 계약에서는 `WPUJAC104DWH`만 `INDEXED_MVP`다.
- `WPUIAC425SNW`, `WPUIAC606SNW`는 `CONTRACT_BLOCKED_NOT_INDEXED`이며
  Backend QA·AI `SELECT_ONLY` 조회와 Activation Gate 전까지 활성화 완료로
  표시하지 않는다.
- Full Corpus v3 Source Span은 Data QA 인계 완료지만 Gold 승인과 AI Runner
  연결은 후속 Gate다.

데이터 전달 완료는 운영 DB 적재, Public API 활성화 또는 Production 배포 완료를
뜻하지 않는다.

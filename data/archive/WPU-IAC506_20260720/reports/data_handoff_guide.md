# WPU-IAC506 데이터 인계 안내서

> 기준일: 2026-07-20  
> 인계 상태: 저장소 내 자료 준비 완료, 실제 전달·수신 확인 전  
> 범위: WPU-IAC506 단일 모델과 대표 증상 4종

## 1. 공통 주의사항

- 공식 사실, 팀 설계 데이터와 합성 데이터를 혼합하지 않는다.
- WPU-IAC506 매뉴얼을 1차 근거로 사용한다.
- 공식 모델 검색에 직접 연결된 FAQ는 밝기 설정 1건뿐이며 핵심 4개 증상 FAQ는 공통 후보이므로 보조 근거로만 사용한다.
- 다른 모델 전용 FAQ를 WPU-IAC506 고객 안내에 사용하지 않는다.
- 공식 근거가 없으면 `판단 보류·상담 필요`로 처리한다.
- 제품 분해, 부품 교체, 전기 계통 직접 점검을 고객에게 안내하지 않는다.
- 외부 공개·배포 전에는 원본 재배포 허용 범위를 별도로 확인한다.
- 공식 매뉴얼·FAQ 원본과 원본 포함 ZIP은 팀 내부 개발·검토용이며 공개 저장소에 업로드하지 않는다.

## 2. 공통 인계 파일

| 자료 | 경로 | 용도 |
|---|---|---|
| 수집 데이터 보고서 | [`data_collection_report.md`](data_collection_report.md) | 전체 수집 현황·수량·품질·법적 검토 |
| 원본 자료 목록 | [`source_inventory.csv`](../processed/metadata/source_inventory.csv) | 파일별 출처·모델·버전·해시 |
| 수집 로그 | [`collection_log.csv`](../processed/metadata/collection_log.csv) | 수집 방식·성공·오류 기록 |
| 품질 검수표 | [`quality_review.csv`](../processed/metadata/quality_review.csv) | 파일 열림·텍스트·모델·FAQ 제한 |
| 공식 근거 범위표 | [`source_coverage_matrix.csv`](../processed/metadata/source_coverage_matrix.csv) | 요구사항·페이지·확보 상태 연결 |
| 오류·미확보 목록 | [`error_missing_list.csv`](../processed/metadata/error_missing_list.csv) | 미확보 자료·영향·대응 |
| 공식 보완 후보 목록 | [`official_support_candidates.csv`](../processed/metadata/official_support_candidates.csv) | 모델 검색결과·공식 제목·콘텐츠 ID·적용 제한 |
| 공식 보완 조사 기록 | [`official_gap_research.md`](official_gap_research.md) | 크롤링 없이 수행한 수동 확인 결과와 판정 변경 |
| PM 최종 결정 | [`pm_final_decisions_20260720.md`](pm_final_decisions_20260720.md) | 모델·FAQ·팀 설계·오류 코드·외부 공유·다음 단계 승인 |
| 최종 제출 체크리스트 | [`final_submission_checklist.csv`](../processed/metadata/final_submission_checklist.csv) | 제출 준비 상태와 남은 승인 |

## 3. 팀원 B - RAG 담당 인계

### 3.1 전달 파일

- 원본 매뉴얼: [`SK매직_WPU-IAC506_사용설명서_REV00.pdf`](../raw/manuals/SK매직_WPU-IAC506_사용설명서_REV00.pdf)
- FAQ 원본: [`SK매직_정수기공통_FAQ_20260715.md`](../raw/faq/SK매직_정수기공통_FAQ_20260715.md)
- 전처리 설계: [`preprocessing_spec.md`](../processed/metadata/preprocessing_spec.md)
- RAG 대표 샘플: [`rag_sample.jsonl`](../processed/structured/rag_sample.jsonl)
- 공식 근거 범위: [`source_coverage_matrix.csv`](../processed/metadata/source_coverage_matrix.csv)
- 공식 보완 후보: [`official_support_candidates.csv`](../processed/metadata/official_support_candidates.csv)

### 3.2 사용 가능한 샘플

| 주제 | chunk_id | 페이지 |
|---|---|---:|
| 필터 주기 | `MAN-WPU-IAC506-P35-FILTER-CYCLE` | 35 |
| 출수량 저하 | `MAN-WPU-IAC506-P31-P43-LOW-FLOW` | 31, 43 |
| 물맛·냄새 | `MAN-WPU-IAC506-P44-TASTE-ODOR` | 44 |
| 누수 | `MAN-WPU-IAC506-P5-P44-LEAK` | 5, 44 |
| 냉수 이상 | `MAN-WPU-IAC506-P42-COLD-WATER` | 42 |
| 온수·히터 경고 | `MAN-WPU-IAC506-P45-HOT-WATER` | 45 |

### 3.3 적용 규칙

1. `model_exact` 매뉴얼 청크를 우선 검색한다.
2. FAQ는 매뉴얼과 내용이 일치할 때만 `common_unverified` 보조 후보로 사용한다.
3. FAQ 단독으로 자가조치나 사용 가능 여부를 확정하지 않는다.
4. FAQ를 채택하면 공식 제목과 콘텐츠 ID를 메타데이터에 함께 저장한다.
5. 검색 결과에는 문서명·모델·버전·`page_refs`를 표시한다.
6. 위험 청크는 일반 생성 결과보다 안전 규칙을 우선한다.

### 3.4 팀원 B 결정 사항

- 실제 청크 크기와 중첩 범위
- 임베딩 모델과 벡터 저장소
- 검색·재순위화 방식
- 근거 검색 실패 처리
- 대표 증상별 검색 평가 세트

이번 인계 자료는 위 구현 결정을 대신하지 않는다.

## 4. 팀원 D - 파일·필드·데이터 구조 담당 인계

### 4.1 전달 파일

- [`source_inventory.csv`](../processed/metadata/source_inventory.csv)
- [`quality_review.csv`](../processed/metadata/quality_review.csv)
- [`source_coverage_matrix.csv`](../processed/metadata/source_coverage_matrix.csv)
- [`rag_sample.jsonl`](../processed/structured/rag_sample.jsonl)
- [`demo_scenarios.json`](../synthetic/demo_scenarios.json)

### 4.2 데이터 분류

| 분류 | 예시 | 저장 원칙 |
|---|---|---|
| `official` | 매뉴얼 모델·페이지·필터 주기·안전 조치 | 원본 ID와 페이지 필수 |
| `team_designed` | 문의 상태·방문 후보·가상 관리 유형 | 공식 정책과 분리 |
| `synthetic` | DEMO 고객·문의·추가 답변 | 실제 개인정보 금지 |

### 4.3 핵심 식별자

- `data_id`: 공식 원본 식별자
- `chunk_id`: RAG 청크 식별자
- `customer_id`, `subscription_id`, `product_id`: 합성 업무 데이터 식별자
- `inquiry_id`: 문의 흐름 식별자
- `scenario_id`: 시연 시나리오 식별자

### 4.4 구조 주의사항

- `page_start`·`page_end`와 함께 실제 인용 페이지인 `page_refs`를 저장한다.
- 비연속 페이지를 단순 범위로 오해하지 않는다.
- `current_use_guidance`는 표준 코드만 허용한다.
- `visit_candidate`는 공식 방문 확정이 아닌 팀 설계 상태다.
- 공통 FAQ 콘텐츠 ID가 확보됐더라도 WPU-IAC506 직접 적용 근거는 아니므로 `model_exact`로 저장하지 않는다.

## 5. 팀원 E - 화면·시연 담당 인계

### 5.1 전달 파일

- 시연 시나리오: [`demo_scenarios.json`](../synthetic/demo_scenarios.json)
- RAG 대표 샘플: [`rag_sample.jsonl`](../processed/structured/rag_sample.jsonl)
- 공식 근거 범위: [`source_coverage_matrix.csv`](../processed/metadata/source_coverage_matrix.csv)

### 5.2 화면 표시 필수값

- 제품 모델 `WPU-IAC506`
- 문서명과 페이지
- 위험도와 처리 우선순위
- 현재 사용 안내 상태
- 현재 담당 주체와 다음 단계
- 고객 행동 필요 여부
- 공식 근거 없음·판단 보류 상태
- 합성 데이터 표시

### 5.3 대표 시연 흐름

| 시나리오 | 화면 핵심 상태 |
|---|---|
| 출수량 저하 | 필터 주기 근거·상담 권고 |
| 물맛·냄새 | 공식 자가조치·고객 확인 대기 |
| 누수 | 전체 사용 중지·우선 상담·방문 후보 |
| 온수 히터 경고 | 일부 사용 중지·비음용·우선 상담 |

### 5.4 화면에서 피할 표현

- `고장 확정`, `수리 필요 확정`
- 공식 정책처럼 보이는 가상 방문 확정일
- 근거가 없는 정상 사용 가능 안내
- WPU-IAC506 적용이 확인되지 않은 FAQ 버튼 조작
- 실제 고객 정보로 오해할 수 있는 이름·전화번호·주소

## 6. PM 최종 결정

### 6.1 검토 자료

- [`data_collection_report.md`](data_collection_report.md)
- [`official_gap_research.md`](official_gap_research.md)
- [`pm_final_decisions_20260720.md`](pm_final_decisions_20260720.md)
- [`official_support_candidates.csv`](../processed/metadata/official_support_candidates.csv)
- [`error_missing_list.csv`](../processed/metadata/error_missing_list.csv)
- [`final_submission_checklist.csv`](../processed/metadata/final_submission_checklist.csv)

### 6.2 결정 결과

1. WPU-IAC506 단일 모델 범위 최종 승인
2. REV.00 매뉴얼 우선과 공통 FAQ 조건부 보조 사용 승인
3. 방문관리·셀프관리 시연 규칙을 `team_designed`로 유지
4. 전체 오류 코드 추가 조사는 현재 단계에서 진행하지 않음
5. 원본 문서는 팀 내부 개발·검토용으로 제한하고 공개 저장소 업로드 금지
6. 팀원 B·D·E 인계와 다음 구현 단계 진행 승인
7. 온수 일반 점검과 히터 경고 청크 분리는 후속 안전성 보완 항목으로 관리

### 6.3 구현 전 별도 협의

- 위험도와 현재 사용 안내를 독립 코드로 관리
- 분기형 문의 상태 전이와 화면 표시명 매핑
- 합성 고객명·연락처·기사명 표시·마스킹 방식
- 공식 원문과 공식 근거 기반 가공 요약 분류
- FAQ 콘텐츠 ID와 문서 메타데이터 저장 위치

## 7. 인계 상태

| 대상 | 자료 준비 | 실제 전달 | 수신 확인 |
|---|---|---|---|
| 팀원 B | PM 승인 완료 | 미실행 | 미확인 |
| 팀원 D | PM 승인 완료 | 미실행 | 미확인 |
| 팀원 E | PM 승인 완료 | 미실행 | 미확인 |
| PM | 결정 반영 완료 | 미실행 | 미확인 |

실제 전달과 수신 확인은 이 문서 작성 범위에 포함되지 않는다.

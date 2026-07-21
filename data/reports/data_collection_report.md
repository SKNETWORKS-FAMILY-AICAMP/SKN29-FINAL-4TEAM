# WPU-JAC104D 기본 MVP 공식 데이터 수집 보고서

> 담당 역할: 팀원 C - 공식 데이터 수집·수집 절차 설계·보고서 취합  
> 기준일: 2026-07-21  
> 문서 상태: PM 승인 범위 반영 최종본  
> 대상 서비스: SK매직 정수기 구독 고객 케어·상담·A/S 지원

## 1. 보고서 목적

본 보고서는 프로젝트에 실제로 사용할 공식 데이터의 출처, 모델, 버전, 수집 방법, 실제 확보 수량, 품질, 활용 범위와 제한사항을 재현 가능한 형태로 기록한다. 공식 원본, 공식 자료 기반 가공본, 팀 설계 데이터, 합성 시연 데이터를 분리하고 팀원 B·D·E가 GitHub의 동일 경로에서 데이터를 확인할 수 있도록 하는 것이 목적이다.

## 2. PM 승인 범위

| 역할 | 제품·모델 | 적용 시점 | 데이터 정책 |
|---|---|---|---|
| 기본 MVP | 초소형 직수 정수기 `WPUJAC104DWH` / 매뉴얼 계열 `WPU-JAC104D` | 현재 | 공식 REV.00 매뉴얼을 1차 근거로 사용 |
| 후속 확장 | 원코크 플러스 얼음물 정수기 `WPUIAC425SNW` / `WPU-IAC425` | 기본 MVP 안정화 후 | 얼음 특화 청크만 별도 확장 |
| 폐기·이력 | `WPU-IAC506` | 사용 중단 | `data/archive/WPU-IAC506_20260720/`에 보관, 신규 구현 사용 금지 |

PM 승인 기록은 [`pm_scope_change_20260721.md`](pm_scope_change_20260721.md)에 있다.

## 3. 대표 문의 범위

### 기본 MVP

- 물이 나오지 않음
- 출수량 저하
- 냉수가 차갑지 않음
- 정상 작동음과 과도한 소음 구분
- 제품 누수
- 물맛·냄새 이상
- 온수 이상 및 순간온수 모듈 안전 경고

### 후속 확장

- 제빙수 공급·순환 및 탈빙 소음
- 얼음이 나오지 않음
- 아이스룸·얼음 토출구 위생관리
- 얼음이 깨지거나 단단하지 않음

## 4. 목표 수량과 실제 확보 수량

| 데이터셋 | 목적 | 출처 | 형식 | 목표 | 실제 | 상태 | 활용 기능 |
|---|---|---|---|---:|---:|---|---|
| 제품 사용설명서 | 모델별 사용·증상·안전 근거 | SK인텔릭스서비스 | PDF | 2개 모델 / 2파일 | 2개 모델 / 2파일 / 96쪽 | 완료 | RAG·제품 식별·안전 분기 |
| 정수기 FAQ 원문 | 공식 상담 후보 탐색 | SK매직 | Markdown | 원본 1파일 | 119건 / 1파일 | 완료·조건부 | FAQ 후보 선별 |
| FAQ 재선별 | JAC104·IAC425 관련 항목 분류 | 공식 FAQ 원문 | JSONL | 20건 후보 | 20건 후보 | 완료 | 적용성 필터 |
| 직접·조건부 FAQ | 실제 답변 보조 근거 | 공식 FAQ 원문 | JSONL | 대표 증상별 근거 확보 | 직접 1건 / 안전 조건부 3건 | 부분 충족 | 매뉴얼 보조 |
| 검증 완료 RAG 청크 | 상담 답변 근거 | 공식 매뉴얼 | JSONL | 기본 6건 이상 / 확장 4건 | 기본 7건 / 확장 4건 | 완료 | 검색·답변·출처 표시 |
| 합성 시연 시나리오 | 문의·상담·안전 분기 검증 | 팀 합성 | JSON | 기본 6건 | JAC104 6건 | 완료 | UI·업무 흐름 |
| 팀원별 확인 가이드 | GitHub 데이터 인계 | 팀 작성 | Markdown | B·D·E·PM 4개 | 4개 | 완료 | 협업 인계 |

FAQ 후보 20건은 사용 가능한 공식 답변 20건을 의미하지 않는다. 적용성 분포는 다음과 같다.

| 적용성 | 수량 | 사용 정책 |
|---|---:|---|
| `model_family_direct` | 1 | 모델 계열 직접 근거, 세부 조치는 D 세대 매뉴얼 우선 |
| `category_common_safety` | 3 | 매뉴얼과 일치하는 안전 분기에만 보조 사용 |
| `category_common_unverified` | 11 | 검증 전 RAG 제외 |
| `image_only_unverified` | 2 | OCR·매뉴얼 대조 전 제외 |
| `other_model_only`·`other_product_family` | 3 | 사용 금지 |

## 5. 자료별 상세 기록

### 5.1 WPU-JAC104D / JCC104D REV.00 사용설명서

| 항목 | 내용 |
|---|---|
| data_id | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00` |
| 제공 기관 | SK인텔릭스 / SK매직 |
| 적용 모델 | `WPU-JAC104D`, `WPU-JCC104D` |
| 공식 파일명 | `(rev00) WPU-JAC104 (D), JCC104 (D)_User_KO_260428.pdf` |
| 공식 게시일 | 2026-05-13 |
| 페이지 | 44쪽 |
| 파일 크기 | 5,131,906 bytes |
| SHA-256 | `0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C` |
| 공식 접근 경로 | [SK인텔릭스서비스 WPUJAC104DWH 검색](https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUJAC104DWH&tabIndex=3) |
| 원본 저장 경로 | `data/raw/manuals/SK매직_WPU-JAC104D_JCC104D_사용설명서_REV00.pdf` |
| 상태 | 확보·추출 완료, 핵심 37~39쪽 시각 검증 완료 |

확인된 핵심 근거는 다음과 같다.

- 37쪽: 냉수 온도, 무출수, 소음
- 38쪽: 누수, 물맛·냄새, 출수량 저하
- 39쪽: 온수 이상, 순간온수 모듈 경고와 음용 금지

현재 상품 코드 `WPUJAC104DWH`와 구형 `WPU-JAC104S`는 기능 세대가 다르므로 구형 S 세대의 IoT 안내를 D 세대 답변에 혼합하지 않는다.

### 5.2 WPU-IAC425 REV.02 사용설명서

| 항목 | 내용 |
|---|---|
| data_id | `MAN-SKMAGIC-WPU-IAC425-REV02` |
| 제공 기관 | SK인텔릭스 / SK매직 |
| 적용 모델 | `WPU-IAC425` |
| 공식 파일명 | `(rev02) WPU-IAC425_User_KO_251224.pdf` |
| 공식 게시일 | 2026-01-05 |
| 페이지 | 52쪽 |
| 파일 크기 | 8,571,676 bytes |
| SHA-256 | `97C027CE75BEC40386307C867DD3983513CB70FAC687F2D2DB6F1167EC9CAEC8` |
| 공식 접근 경로 | [SK인텔릭스서비스 WPUIAC425 검색](https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUIAC425&tabIndex=3) |
| 원본 저장 경로 | `data/raw/manuals/SK매직_WPU-IAC425_사용설명서_REV02.pdf` |
| 상태 | 확보·추출 완료, 핵심 37~40쪽·43~46쪽 시각 검증 완료 |

IAC425 데이터는 `expansion_secondary`로 분류하며 기본 MVP 검색 인덱스에는 포함하지 않는다.

### 5.3 SK매직 정수기 FAQ

| 항목 | 내용 |
|---|---|
| 원본 data_id | `FAQ-SKMAGIC-WATER-PURIFIER-20260715` |
| 재선별 data_id | `FAQ-SKMAGIC-SELECTED-JAC104-IAC425-20260721` |
| 제공 기관 | SK매직 |
| 원본 수집량 | 119건 |
| 재선별량 | 20건 |
| 직접 적용 | WPUJAC104·WPUJCC104 출수량 FAQ 1건 |
| 공식 접근 경로 | [SK매직 공식 FAQ](https://www.skmagic.com/customer/faq/indexFaqList) |
| 제한 | 고정 개별 URL 없음, 이미지 답변 포함, 다른 모델 항목 혼재 |

FAQ는 `applicability`와 `allowed_use`를 반드시 함께 조회한다. `WPUI100·110·200·210` 전용 미출빙 FAQ를 WPU-IAC425에 적용하지 않는다.

## 6. 수집·가공 방법

| 단계 | 방식 | 자동화 | 결과 |
|---|---|---|---|
| 공식 매뉴얼 탐색 | 공식 상품 페이지에서 서비스 검색 경로 진입 후 모델 검색 | 수동 | 대상 모델·매뉴얼 건수 확인 |
| 공식 매뉴얼 수집 | 공식 다운로드 버튼 사용 | 수동 | PDF 2파일 확보 |
| 무결성 확인 | SHA-256·페이지·암호화·파일 크기 검사 | 자동 | 정상 |
| 페이지 텍스트 추출 | `scripts/extract_selected_model_data.py`, pypdf | 자동 | 96쪽 JSONL |
| 키워드 후보 탐색 | 문의 주제별 키워드 매칭 | 자동 | 페이지 후보 CSV |
| FAQ 재선별 | FAQ 번호별 적용 규칙과 모델 범위 부여 | 자동+수동 판정 | 20건 JSONL |
| 핵심 페이지 검수 | Poppler PNG 렌더링과 텍스트 대조 | 수동 | JAC104 3쪽·IAC425 8쪽 검증 |
| 구조 검증 | Python JSON·CSV 전체 파싱 | 자동 | 오류 0건 |

상세 실행 기록은 [`collection_log.csv`](../processed/metadata/collection_log.csv)에 있다.

## 7. 표준 파일 구조

```text
data/
├── raw/                         # 공식 원문, Git 제외
├── processed/
│   ├── documents/
│   │   └── manual_pages.jsonl
│   ├── metadata/
│   │   ├── collection_log.csv
│   │   ├── error_missing_list.csv
│   │   ├── final_submission_checklist.csv
│   │   ├── manual_keyword_hits.csv
│   │   ├── model_scope.csv
│   │   ├── preprocessing_spec.md
│   │   ├── quality_review.csv
│   │   ├── source_coverage_matrix.csv
│   │   └── source_inventory.csv
│   └── structured/
│       ├── rag_verified_sample.jsonl
│       └── selected_faq_candidates.jsonl
├── synthetic/
│   └── demo_scenarios.json
├── reports/
├── handoff_guides/
└── archive/WPU-IAC506_20260720/
```

## 8. 품질 검수 결과

| 검수 항목 | 결과 | 조치 |
|---|---|---|
| PDF 열림·암호화 | 2파일 정상·암호화 없음 | 없음 |
| 페이지 수 | JAC104 44쪽·IAC425 52쪽 | 원본과 추출 행 일치 |
| 텍스트 추출 | 94/96쪽 내용 추출, 각 PDF 마지막 빈 면 1쪽 | 빈 면 청킹 제외 |
| 핵심 표·주의 문구 | 시각 검수 결과 정상 | 검증 청크만 RAG 사용 |
| 모델·버전 | 대상 모델과 일치 | 세대 혼합 방지 필드 유지 |
| FAQ 적용성 | 직접·공통·타 모델 구분 완료 | 허용 상태 필터 적용 |
| JSONL·CSV 문법 | 전체 파싱 오류 0건 | 없음 |
| 실제 개인정보 | 합성 데이터 내 0건 | 합성 식별자만 사용 |
| 원본 공개 위험 | `data/raw/` Git 제외 | PDF·ZIP 공개 금지 |

세부 검수값은 [`quality_review.csv`](../processed/metadata/quality_review.csv)에 기록했다.

## 9. 공식·팀 설계·합성 데이터 구분

| 구분 | 내용 | 저장 예시 |
|---|---|---|
| 공식 | 매뉴얼·FAQ에 있는 사실, 안전 조치, 상담 조건 | RAG 청크·FAQ 후보 |
| 팀 설계 | 문의 상태, 담당 주체, 상담·방문 전환 | 합성 시나리오의 workflow |
| 합성 | 고객 문의 원문, 가상 식별자, 처리 예시 | `demo_scenarios.json` |

방문 후보, 처리 우선순위, 관리 일정은 공식 정책으로 표현하지 않고 `team_designed`로 표시한다.

## 10. 개인정보·저작권·라이선스 검토

### 개인정보

- 합성 데이터에는 실제 이름·전화번호·주소·고객번호·주민등록번호·결제정보를 포함하지 않았다.
- `DEMO-*` 형식의 합성 식별자만 사용한다.

### 저작권·재배포

- 공식 매뉴얼과 FAQ의 명시적 원문 재배포 라이선스는 확보하지 못했다.
- PDF 원본과 원본 포함 ZIP은 GitHub에 업로드하지 않는다.
- 공개 저장소에는 문서명, 제공기관, 버전, 해시, 페이지, 출처 URL과 필요한 구조화 요약만 올린다.
- 공식 원문 전체를 외부 배포해야 할 경우 제공기관 권한을 별도로 확인한다.

### 안전

- 제품 분해·배관 수리·냉각부·히터 직접 수리를 안내하지 않는다.
- 누수와 순간온수 모듈 경고는 사용 중지 또는 상담 연결을 우선한다.

## 11. 오류·미확보 자료와 영향

| 항목 | 상태 | 영향 | 대응 |
|---|---|---|---|
| FAQ 개별 고정 URL | 부분 미확보 | 개별 링크 인용 제한 | 제목·번호·목록 URL·원본 해시 사용 |
| 이미지 답변 2건 | 사용 보류 | 텍스트 검색 불가 | RAG 제외, 필요 시 OCR 후 검증 |
| 공통 미검증 FAQ 11건 | 사용 보류 | 모델 오안내 위험 | 매뉴얼 일치 검증 전 제외 |
| 전체 96쪽 시각 검수 | 핵심 페이지만 완료 | 추가 기능 청킹 시 검수 필요 | 채택 페이지 단위로 추가 검수 |
| 방문관리 운영 기준 | 부분 미확보 | 일정·방문 확정 자동화 제한 | team_designed 표시 또는 상담 연결 |
| 기존 FAQ 크롤링 실행 로그 | 미확보 | 동일 조건 재수집 제한 | 원본 해시 보존, 갱신 시 수집기 재작성 |

전체 목록은 [`error_missing_list.csv`](../processed/metadata/error_missing_list.csv)에 있다.

## 12. 팀 인계

인계 ZIP은 생성하지 않는다. GitHub의 표준 경로를 단일 공유 원본으로 사용한다.

| 대상 | 확인 가이드 | 핵심 확인 사항 |
|---|---|---|
| 팀원 B | `data/handoff_guides/team_B_rag_data_guide.md` | 허용 applicability, 청크·출처·위험 필드 |
| 팀원 D | `data/handoff_guides/team_D_data_structure_guide.md` | 공식·설계·합성 구분, 참조 키·결측 처리 |
| 팀원 E | `data/handoff_guides/team_E_ui_demo_guide.md` | JAC104 시나리오, 페이지 근거, 위험 안내 |
| PM | `data/handoff_guides/PM_data_review_guide.md` | 범위·수량·법적 제한·최종 체크리스트 |

## 13. 최종 판단

기본 MVP 구현에 필요한 WPU-JAC104D 공식 매뉴얼, 대표 증상 7개 검증 청크, 모델 계열 직접 FAQ, 합성 시연 6건과 메타데이터를 확보했다. IAC425는 얼음 특화 4개 검증 청크를 후속 확장 상태로 분리했다. 이전 IAC506 산출물은 archive로 격리했으며 현재 표준 경로에는 신규 모델 데이터만 존재한다.

남은 작업은 새 자료를 더 늘리는 것이 아니라 팀원 B·D·E가 각 가이드에 따라 동일한 모델·적용성·안전 정책을 구현하는지 확인하는 것이다.


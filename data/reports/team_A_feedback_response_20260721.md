# 팀원 A 피드백 반영 결과

> 확인일: 2026-07-21
> 기본 MVP: `WPUJAC104DWH` / `WPU-JAC104D`
> 후속 확장: `WPUIAC425SNW` / `WPU-IAC425`

## 1. 결론

JAC104D 공식 사용설명서의 실제 다운로드 파일, 문서 개정, 공식 첨부 정보, SHA-256과 핵심 페이지를 다시 검증했다. D 세대와 S 세대 문서 계보를 분리했고, 출수량 편차 FAQ는 현재 판매 코드의 직접 근거가 아니라 계열 조건부 근거로 하향 조정했다. IAC425 청크는 별도 확장 파일로 분리했다.

## 2. WPUJAC104DWH 공식 문서 검증

| 항목 | 확인 결과 |
|---|---|
| 현재 판매 코드 | `WPUJAC104DWH` |
| 공식 상품 | [SK매직몰 초소형 직수 정수기](https://www.skmagic.com/goods/indexGoodsDetail?goodsId=G000070005) |
| 매뉴얼 적용 모델 | `WPU-JAC104 (D)`, `WPU-JCC104 (D)` |
| 문서 개정 | `REV.00` |
| 공식 파일명 | `(rev00) WPU-JAC104 (D), JCC104 (D)_User_KO_260428.pdf` |
| 공식 첨부 등록·수정일 | 2026-05-13 / 2026-05-13 |
| PDF 메타데이터 생성·수정 | 2026-04-28 11:42:25 / 11:42:28 KST |
| 페이지 | 44쪽 |
| 파일 크기 | 5,131,906 bytes |
| SHA-256 | `0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C` |
| 공식 검색 화면 | [SK인텔릭스서비스 WPUJAC104DWH 검색](https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUJAC104DWH&tabIndex=3) |
| 공식 원본 | [사용설명서 직접 다운로드](<https://www.skintellixservice.com/common/fileDownloadS3.do?atchPath=cnts&atchNm=50f504a46a3843beb767baa6f9f94548&atchOrgNm=(rev00)%20WPU-JAC104%20(D)%2C%20JCC104%20(D)_User_KO_260428.pdf&atchExtNm=pdf>) |

공식 직접 다운로드 응답의 크기와 SHA-256은 로컬 `data/raw` 원본과 일치했다. 표지에서 모델명과 `REV.00`을 시각 확인했다.

## 3. 정확한 증상·안전 위치

| 주제 | 페이지 | 문서 구간 | 사용 정책 |
|---|---:|---|---|
| 무출수 | 37 | 고장 신고 전 확인하기 > 물이 출수되지 않음 | D 세대 공식 1차 근거 |
| 냉수 온도 | 37 | 고장 신고 전 확인하기 > 냉수가 차갑지 않음 | D 세대 공식 1차 근거 |
| 소음 | 37 | 고장 신고 전 확인하기 > 소음 발생 | 정상음과 이상음을 구분 |
| 누수 | 38 | 고장 신고 전 확인하기 > 제품 누수 발생 | 밸브 잠금·전원 분리·상담 연결 |
| 물맛·냄새 | 38 | 고장 신고 전 확인하기 > 불쾌한 맛과 냄새 발생 | 수질 안전 단정 금지 |
| 출수량 저하 | 38 | 고장 신고 전 확인하기 > 출수량이 적을 경우 | D 세대 공식 1차 근거 |
| 온수·순간온수 안전 | 39 | 고장 신고 전 확인하기 > 온수 이상 및 순간온수 모듈 점검 | 모듈 점검 시 음용 금지·상담 연결 |

행 단위 메타데이터는 `data/processed/structured/jac104_evidence_registry.jsonl`에 있다.

## 4. D 세대와 S 세대 분리 결과

| 검색 코드 | 공식 검색 결과 | MVP 처리 |
|---|---|---|
| `WPUJAC104DWH` | D 세대 REV.00 제품 사용설명서 1건 | 사용 |
| `WPUJAC104SWH` | REV.01 IoT 가이드 1건 | D 세대 사용 금지 |
| `WPUJAC104SWW/SPP/SDG` | REV.02 JAC104 제품 설명서와 REV.01 IoT 가이드 | S 세대 별도 보관, 현재 미수집 |
| `WPUJAC104SPB` | REV.01 IoT 가이드 | D 세대 사용 금지 |
| `WPU-JAC104S` | 하이픈 포함 검색 0건 | 실패 기록 후 하이픈 없는 판매 코드로 재검색 |

세부 첨부 ID와 content key는 `data/processed/metadata/model_document_lineage.csv`에 기록했다. 현재 공식 상품 페이지는 `WPUJAC104DWH`의 IoT 케어를 미지원으로 표시하므로 S 세대 IoT 설명을 D 세대에 적용하지 않는다.

## 5. FAQ 메타데이터화

### 설정량과 실제 출수량 편차

- 공식 섹션: [FAQ > 정수기 > 초소형 직수정수기 출수 용량이 달라요](https://www.skmagic.com/customer/faq/indexFaqList)
- 게시자가 명시한 코드: `WPUJAC104`, `WPUJCC104`
- 현재 판매 코드 직접 일치: `false`
- 세대 범위: D/S 미표기
- 정책: `WPU-JAC104D` 38쪽 출수량 저하 근거와 함께만 조건부 보조 사용

### 출수량 저하 공통 FAQ

- 스냅샷 섹션: `FAQ > 정수기 > 냉,온수 취수량이 적어요`
- 게시자가 명시한 모델 코드: 없음
- 개별 영구 URL: 미확보
- 정책: 정확 모델 검증 전 MVP RAG 제외

FAQ JSONL에는 `publisher_model_codes`, `project_candidate_models`, `exact_sales_code_match`, `generation_scope`, `source_locator`, `rag_policy`를 추가했다.

## 6. DEMO_METADATA와 실패 처리

저장소 전체 검색에서는 `DEMO_METADATA`를 찾지 못했다. 따라서 현재 구조를 검증했다는 주장은 할 수 없다. 해당 값이 다른 브랜치나 별도 목업에 있다면 위치를 전달받아야 한다. 위치가 확인되기 전에는 공식 근거로 사용하지 않고 `demo_or_team_designed`로 취급한다.

검색 실패, 정확 모델 설명서 미확보, FAQ 개별 URL 부재, 모델 미표기와 대체 처리는 `data/processed/metadata/error_missing_list.csv`와 `collection_log.csv`에 기록했다.

## 7. IAC425 후속 확장 분리

- 기본 MVP: `data/processed/structured/rag_verified_sample.jsonl` - JAC104D 7건만 포함
- 후속 확장: `data/processed/structured/rag_expansion_iac425.jsonl` - IAC425 4건
- IAC425는 PM이 확장 시작을 승인하기 전 기본 검색·UI·시연 대상에 포함하지 않는다.

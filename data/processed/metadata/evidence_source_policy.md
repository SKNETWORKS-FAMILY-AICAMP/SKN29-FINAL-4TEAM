# 공식 근거 사용 정책

## 적용 우선순위

1. 현재 판매 코드 `WPUJAC104DWH`와 연결된 `WPU-JAC104D / WPU-JCC104D REV.00` 공식 사용설명서
2. 모델 계열이 명시된 공식 FAQ 중 D 세대 매뉴얼과 충돌하지 않는 항목
3. 모델 코드가 없는 공통 FAQ는 검증 후보로만 보관하고 MVP RAG에서 제외
4. 팀 설계 데이터와 합성 시연 데이터는 공식 근거와 분리

## 모델 세대 분리

- `WPUJAC104DWH`는 D 세대이며 공식 상품 페이지에서 IoT 케어 미지원으로 표시된다.
- `WPUJAC104SWH`, `WPUJAC104SWW`, `WPUJAC104SPP`, `WPUJAC104SDG`, `WPUJAC104SPB`는 S 세대 자료로 분리한다.
- S 세대의 제품 사용설명서와 IoT 가이드는 D 세대 답변, 검색 인덱스, 화면 출처에 사용하지 않는다.
- FAQ가 `WPUJAC104`처럼 세대 접미사 없이 표기한 경우 `family_only`로 취급하고 D 매뉴얼을 우선한다.

## `DEMO_METADATA` 처리

- 현재 저장소 전체 검색에서 `DEMO_METADATA`라는 필드·상수·파일을 확인하지 못했다.
- 향후 목업에서 발견되더라도 `source_classification=demo_or_team_designed`로 분류한다.
- 공식 URL, 문서 ID, 모델 코드, 개정, 페이지 또는 섹션 위치, 검증 상태를 갖춘 레지스트리와 연결되지 않은 `DEMO_METADATA`는 공식 답변 근거로 사용하지 않는다.
- 화면 표시는 `공식 근거`, `팀 설계`, `합성 시연`을 구분해야 한다.

## 실패·미확보 처리

- 공식 PDF 직접 URL 실패: 공식 검색 화면 URL, 첨부 ID, content key, 공식 파일명, 로컬 SHA-256을 남기고 답변 근거 사용을 보류한다.
- 모델 검색 0건: 하이픈 제거 등 공식 판매 코드 형식으로 한 차례 재검색하고 결과를 로그에 남긴다.
- 정확 모델의 제품 설명서 대신 공통 가이드만 확인된 경우: 해당 문서를 다른 세대 근거로 대체하지 않는다.
- FAQ 개별 URL 미확보: 목록 URL, 카테고리, 제목, 스냅샷 해시와 확인일을 사용하고 페이지 번호는 `null`로 둔다.
- 모델 코드 미표기 FAQ: `exact_sales_code_match=false`, `generation_scope=unspecified`, `rag_policy=exclude_until_exact_model_verified`로 처리한다.

# D04 행 단위 Parent·Child 전처리 상세 계획

> 작성일: 2026-08-12 KST
> 작성 역할: 김은진 / Data·QA·DevOps
> 기준 HEAD: `880bef7f26b9a5cad70832f3c1cfe6de4b1f41c5`
> 상태: `EXECUTED_DATA_GENERATION_ONLY`
> 실행 승인 상태: 실험용 데이터 생성·QA·결정성 검증 완료; AI Runner·B1·운영 적용 미실행

## 1. 목적과 결론

이번 작업은 JAC104/JCC104 매뉴얼 전체 재전처리가 아니다. 원본 PDF의 5·7·37·38·39쪽만 대상으로 검색 단위를 행 또는 안전 문단 단위로 분리하는 experimental v2 계획이다.

구조는 이동윤 회신의 C안을 적용한다.

```text
Child 검색 및 Child 기준 평가
        ↓
선택된 Child의 Parent를 중복 없이 답변 Context로 확장
```

- 검색 후보와 Top-K·Hit·MRR·ANY·ALL 계산 단위는 Child다.
- Parent는 답변 문맥에만 쓰며 검색 적중으로 다시 계산하지 않는다.
- 같은 Parent에 연결된 Child가 여러 개 검색돼도 Parent는 한 번만 확장한다.
- B안인 `child_only_v2`는 동일 Child 검색 결과를 사용하는 대조군으로 유지한다.
- 기존 B1 v1 입력·결과는 수정하지 않는다.
- 이 계획은 experimental v2 데이터 생성 준비를 위한 것이며 운영 적용 승인이 아니다.

## 2. 검토한 기준 자료

| 구분 | 기준 | SHA-256 또는 상태 |
|---|---|---|
| AI 담당자 구조 결정 회신 | `20260812_이동윤_to_김은진_B1_행단위ParentChild_구조결정_회신_v0.1.md` | `AD46902EBE1956B1684132D23107A2DD20A199D50B1CF89872924D026E37D36E` |
| PM 전처리 요청 | `d04-0-은진님_전달용_데이터전처리_요청.md` | `30392770C82836345EF8808B3F6B0F0601DE8B7147689CD48B0095C778564ED6` |
| 공식 원본 | 바탕화면 지정 폴더의 `WPU-JAC104,WPU-JCC104-냉온정수기메뉴얼.pdf` | `0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C` |
| 현행 페이지 추출본 | `data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl` | `9E13354A7A0838EF825F1D401A6C999C33A24C2F811523F85B7E29D3C032E29F` |
| 현행 Evidence Registry | `data/processed/structured/evidence/jac104_evidence_registry.jsonl` | `40A1B328F86FF6E57A3EFD1F5EBD63051DCDE06AB32E0A08CC6C6D5BE638F61F` |

공식 PDF는 44쪽이며, 지정된 5개 페이지를 렌더링해 표의 시각적 행 경계와 추출 텍스트를 대조했다. 원본 PDF의 SHA-256은 현행 페이지 추출본과 Evidence Registry에 기록된 `source_file_sha256`과 일치한다.

| page | 기존 `page_id` | 기존 `text_sha256` |
|---:|---|---|
| 5 | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P005` | `1B24A915B848CA62081D5D4830F6B159D26604621669FA1735896B0300E82B5C` |
| 7 | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P007` | `E1E46F9F0E85A064DDC1819CABCF2C3C14D0CF5BBAA65C88B37461641FF293FE` |
| 37 | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P037` | `4EC2179AF9EBC72BA3886559D93B587A0FC1D0C159786147D90F8D5C182298FA` |
| 38 | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P038` | `5022E426F7C9EAE0B1C72A0BC1B7C8A9DD92960138C79071CB01B33A0E47FC16` |
| 39 | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P039` | `C43D6C4EB020B9EE5AC75DACB01D31643C9D6A7787414F384583B701914F00CD` |

PM 회신이 참고하라고 한 `docs/testing/rag/d04-0-row-child-preprocessing-evaluation-contract.md`는 현재 HEAD에 없다. 따라서 새 필드를 정식 계약으로 확정하지 않고, 이 문서에 experimental v2용 제안 스키마와 ID 매핑을 고정한다. 계약 파일이 추가되면 생성 전에 차이를 다시 점검한다.

## 3. 범위

### 포함

- Parent 5건: 5·7·37·38·39쪽의 기존 추출 텍스트 전체
- Child 15건: 아래 행 목록에 지정한 안전 문단 또는 증상 표 행
- 기존 Evidence Group 7개 재사용
- 누수 3개 Source Variant 보존
- Parent·Child·원본 간 lineage와 SHA-256 검증 계획
- 실험용 산출물 4개 생성 계획과 QA Gate

### 제외

- 매뉴얼 나머지 39쪽 재전처리
- 38쪽 `정수된 물에 미세한 입자 발생` 행의 Child 생성
- Gold 질문 문장을 검색용 `child_text`에 추가하는 작업
- 기존 B1 v1 데이터와 결과 수정
- `ai/**` Runner·평가 코드 수정 또는 실행
- 운영용 `parent_child_v2` 승격

38쪽 미세입자 행은 Parent에는 원문 그대로 포함되지만 PM 요청 범위의 검색 Child에서는 제외한다. Parent는 검색 후보가 아니므로 이 제외가 Child 검색 평가를 직접 오염시키지는 않지만, C안의 Parent Context 확장 때는 함께 노출될 수 있다. 이 위험은 후속 `child_only_v2` 대조에서 답변 관련성·추가 Token·지연시간으로 확인한다.

## 4. 원본 범위와 Child 15건 설계

`source_span`의 줄 번호는 현행 `manual_pages_jac104d.jsonl` 각 레코드의 `text`를 LF로 분리한 1부터 시작하는 줄 번호다. PDF 표는 텍스트 추출 순서가 행 좌우 열과 완전히 일치하지 않을 수 있으므로 줄 번호만 저장하지 않고 `start_anchor`, `end_anchor`, `row_label`을 함께 저장한다.

| # | page | proposed `child_id` | 원본 범위 | `evidence_group_id` | canonical `source_variant_id` |
|---:|---:|---|---|---|---|
| 1 | 5 | `CHILD-WPUJAC104DWH-P005-LEAK-001` | 안전 문단, L05-L07 | `EVD-WPUJAC104DWH-LEAK-001` | `LEAK-001-P005` |
| 2 | 7 | `CHILD-WPUJAC104DWH-P007-LEAK-001` | 안전 문단, L12-L14 | `EVD-WPUJAC104DWH-LEAK-001` | `LEAK-001-P007` |
| 3 | 37 | `CHILD-WPUJAC104DWH-P037-COLD-NORMAL-001` | 냉수가 차갑지 않음·제품 고장 아님, L05-L15 | `EVD-WPUJAC104DWH-COLD-TEMPERATURE-001` | `COLD-TEMPERATURE-001-P037-NORMAL` |
| 4 | 37 | `CHILD-WPUJAC104DWH-P037-COLD-FAULT-001` | 냉수가 차갑지 않음·제품 고장, L16-L20 | `EVD-WPUJAC104DWH-COLD-TEMPERATURE-001` | `COLD-TEMPERATURE-001-P037-FAULT` |
| 5 | 37 | `CHILD-WPUJAC104DWH-P037-NO-WATER-001` | 물이 출수되지 않음, L21-L29 | `EVD-WPUJAC104DWH-NO-WATER-001` | `NO-WATER-001-P037` |
| 6 | 37 | `CHILD-WPUJAC104DWH-P037-NOISE-001` | 소음 발생, L30-L40 | `EVD-WPUJAC104DWH-NOISE-001` | `NOISE-001-P037` |
| 7 | 38 | `CHILD-WPUJAC104DWH-P038-LEAK-001` | 제품 누수 발생, L02-L04 | `EVD-WPUJAC104DWH-LEAK-001` | `LEAK-001-P038` |
| 8 | 38 | `CHILD-WPUJAC104DWH-P038-TASTE-ODOR-001` | 불쾌한 맛과 냄새 발생, L05-L11 | `EVD-WPUJAC104DWH-TASTE-ODOR-001` | `TASTE-ODOR-001-P038` |
| 9 | 38 | `CHILD-WPUJAC104DWH-P038-LOW-FLOW-001` | 출수량이 적을 경우, L19-L28 | `EVD-WPUJAC104DWH-LOW-FLOW-001` | `LOW-FLOW-001-P038` |
| 10 | 38 | `CHILD-WPUJAC104DWH-P038-HOT-STEAM-001` | 온수 사용 중 스팀 분사, L29-L35 | `EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001` | `INSTANT-HOT-WATER-SAFETY-001-P038-STEAM` |
| 11 | 38 | `CHILD-WPUJAC104DWH-P038-HOT-INTERRUPTION-001` | 온수 사용 중 물 끊김, L36-L38 | `EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001` | `INSTANT-HOT-WATER-SAFETY-001-P038-INTERRUPTION` |
| 12 | 39 | `CHILD-WPUJAC104DWH-P039-HOT-LUKEWARM-001` | 온수 사용 시 미지근한 물, L02-L11 | `EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001` | `INSTANT-HOT-WATER-SAFETY-001-P039-LUKEWARM` |
| 13 | 39 | `CHILD-WPUJAC104DWH-P039-HOT-NO-OUTPUT-001` | 온수가 나오지 않음, L12-L18 | `EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001` | `INSTANT-HOT-WATER-SAFETY-001-P039-NO-OUTPUT` |
| 14 | 39 | `CHILD-WPUJAC104DWH-P039-HOT-MODULE-CHECK-001` | LCD 순간온수 모듈 점검, L19-L25 | `EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001` | `INSTANT-HOT-WATER-SAFETY-001-P039-MODULE-CHECK` |
| 15 | 39 | `CHILD-WPUJAC104DWH-P039-HOT-CHECK-PROCESS-001` | 점검 과정 중 온수 중단, L26-L30 | `EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001` | `INSTANT-HOT-WATER-SAFETY-001-P039-CHECK-PROCESS` |

### 범위 판단에서 보정한 점

1. 7쪽 누수 Child는 L12-L14까지만 포함한다. L15-L17의 이상음·탄 냄새·연기 조치는 별도 안전 항목이므로 섞지 않는다.
2. 37쪽 `냉수가 차갑지 않음`은 정상 조건과 냉각부 고장 행이 분리되어 있어 Child 2건으로 만든다. 두 Child는 같은 Evidence Group으로 평가한다.
3. 38쪽 `출수량이 적을 경우`에는 순간온수 가동 조건도 같은 표 행의 원인으로 포함한다. 이를 순간온수 안전 Evidence로 분리하지 않는다.
4. 38쪽 순간온수는 스팀과 물 끊김의 증상·조치가 다르므로 Child 2건으로 만든다.
5. 39쪽 순간온수 관련 표는 서로 다른 조치 4행이므로 Child 4건으로 만든다.

## 5. ID 표기 충돌 해결 계획

두 회신의 누수 Variant 표기가 다르다.

- PM 요청: `EVD-WPUJAC104DWH-LEAK-001-P005` 형식
- AI 담당자 결정: `evidence_group_id=EVD-WPUJAC104DWH-LEAK-001`, `source_variant_id=LEAK-001-P005` 형식

experimental v2 레코드에는 AI Adapter가 요구한 짧은 `source_variant_id`를 canonical 값으로 사용한다. PM의 전체 Variant ID는 Manifest의 별칭 매핑으로 보존한다.

```text
LEAK-001-P005 -> EVD-WPUJAC104DWH-LEAK-001-P005
LEAK-001-P007 -> EVD-WPUJAC104DWH-LEAK-001-P007
LEAK-001-P038 -> EVD-WPUJAC104DWH-LEAK-001-P038
```

이 방식은 Evidence Group을 정답 판정 단위로 유지하면서 PM이 지정한 페이지별 식별자도 잃지 않는다. 정식 계약이 나중에 다른 필드명을 요구하면 데이터 생성 전에 이 매핑만 조정하고 Evidence Group 자체는 바꾸지 않는다.

## 6. experimental v2 제안 스키마

### Parent 레코드

| 필드 | 계획 |
|---|---|
| `parent_id` | 문서 ID와 페이지로 결정적으로 생성 |
| `document_id` | 기존 `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00` 재사용 |
| `page_refs` | 한 페이지만 가진 배열 |
| `parent_text` | 현행 페이지 추출본의 `text` 전체를 정규화 없이 사용 |
| `parent_text_sha256` | UTF-8 직렬화 규칙을 Manifest에 명시하고 계산 |
| `source_file_sha256` | 공식 PDF SHA-256 |
| `source_page_text_sha256` | 기존 페이지 레코드의 `text_sha256` 재사용 |

### Child 레코드

| 필드 | 계획 |
|---|---|
| `child_id`, `parent_id` | 고유 Child와 Parent 연결 |
| `document_id`, `page_refs` | 문서·페이지 lineage |
| `source_span` | `type`, `line_start`, `line_end`, `row_label`, `start_anchor`, `end_anchor` |
| `evidence_group_id` | 기존 Evidence Registry의 ID 정확히 1개 |
| `source_variant_id` | 페이지·행 표현 구분용 canonical ID |
| `child_text` | 원문의 증상·원인·조치를 읽기 순서로 재배열한 검색 텍스트 |
| `child_text_sha256` | Child 텍스트 SHA-256 |
| `parent_text_sha256` | Parent 레코드와 동일성 확인 |
| `source_file_sha256` | 공식 PDF SHA-256 |

`child_text`는 PDF 표의 시각적 읽기 순서로 조립하되 원문에 없는 설명, Gold 질문 표현, 동의어 확장은 추가하지 않는다. 줄바꿈 합치기, 불필요한 페이지 번호 제거 같은 정규화 규칙은 Manifest에 기록하고 같은 입력에서 같은 결과가 나오도록 한다.

## 7. 생성된 산출물 4개

계획에 따라 다음 4개 파일을 생성했다.

```text
data/processed/structured/rag/experimental/
├─ rag_parent_pages_v2.jsonl
├─ rag_child_chunks_v2.jsonl
└─ rag_child_chunks_v2_manifest.json

data/processed/validation/rag_experiments/
└─ rag_child_chunks_v2_qa.json
```

| 파일 | 예정 건수·내용 |
|---|---|
| `rag_parent_pages_v2.jsonl` | Parent 5건 |
| `rag_child_chunks_v2.jsonl` | Child 15건 |
| `rag_child_chunks_v2_manifest.json` | 입력·출력 Hash, 정규화 규칙, ID 별칭, 건수, HEAD |
| `rag_child_chunks_v2_qa.json` | 연결·ID·범위·중복·누락·Gold 복사 방지 검사 결과 |

## 8. 실행 순서

아래 순서로 실행했다.

1. 시작 직전에 `git status --short`, 전체 HEAD, 입력 3종의 SHA-256을 다시 확인한다.
2. HEAD 또는 입력 Hash가 이 계획과 다르면 이전 결과와 합치지 않고 범위 표부터 재검토한다.
3. 5개 Parent를 현행 페이지 추출본에서 결정적으로 생성한다.
4. 위 15개 범위에서 Child를 생성하고 각각 기존 Evidence Group 하나만 연결한다.
5. 누수 canonical Variant와 PM 전체 Variant 별칭 매핑을 Manifest에 기록한다.
6. Parent·Child 출력 후 SHA-256을 계산해 Manifest에 기록한다.
7. QA를 실행해 아래 Gate를 확인한다.
8. 데이터 diff와 QA 결과를 사람이 다시 읽고, 원본·B1·Gold·AI 파일이 변경되지 않았는지 확인한다.
9. 산출물 4개와 QA 보고를 이동윤에게 전달한다.
10. 이동윤이 experimental Adapter로 `child_only_v2`와 `child_parent_context_v2`를 비교한다.

## 9. 데이터 QA Gate

| Gate | 통과 조건 |
|---|---|
| 입력 고정 | PDF·페이지 추출본·Evidence Registry Hash가 Manifest와 일치 |
| 건수 | Parent 5건, Child 15건 |
| Parent 연결 | 고아 Child 0건, Parent당 예상 Child 수 `1/1/4/5/4` |
| Evidence 단일성 | 모든 Child의 `evidence_group_id` 정확히 1개 |
| Evidence 유효성 | 7개 Group 모두 기존 Registry에 존재 |
| 누수 Variant | P005·P007·P038 3종 모두 존재, 동일 Group으로 집계 |
| Source span | 모든 Child에 페이지·줄·행 라벨·시작/종료 anchor 존재 |
| 범위 역추적 | anchor가 해당 Parent 원문에서 발견되고 지정 행과 시각적으로 일치 |
| 제외 범위 | 38쪽 미세입자 Child 0건 |
| Gold 오염 방지 | Gold 질문 문장 전체 복사 0건; 입력 Gold를 생성 텍스트 원천으로 사용하지 않음 |
| 중복 | `child_id`, `source_variant_id` 중복 0건 |
| 결정성 | 동일 입력·규칙으로 재생성 시 4개 출력 Hash 동일 |
| 변경 격리 | 기존 B1, MVP 데이터, Gold, `ai/**` diff 0건 |

## 10. 실행 결과

### 처리 흐름과 주요 명령

계획에 고정한 HEAD와 입력 Hash를 먼저 확인한 뒤, Python 3.13.13 Base Python으로 임시 생성기를 문법 검사하고 실행했다. `ai/.venv`는 연결된 Base Python 실행 거부로 직접 실행할 수 없어, 동일한 `watercare-bootstrap` Python 3.13.13을 사용했다.

```powershell
$basePython = 'C:\Users\Playdata\AppData\Local\miniconda3\envs\watercare-bootstrap\python.exe'
& $basePython --version
& $basePython -m py_compile '.\data\.runtime\generate_d04_v2.py'
& $basePython -B '.\data\.runtime\generate_d04_v2.py'
& $basePython -B '.\data\.runtime\generate_d04_v2.py' --force  # 결정성 재생성 검증
& $basePython -B -m unittest discover -s data/tools/tests -v
```

실행 결과:

- Python: `3.13.13`
- Parent: 5건
- Child: 15건
- QA: 15개 검사, `PASS 15 / FAIL 0`
- 재생성 전후 Parent·Child·Manifest·QA Hash 동일
- 기존 data 영역 단위 테스트: `Ran 76 tests`, `OK`
- 기존 B1·MVP·Gold·`ai/**` 파일은 변경하지 않음
- 참조 계약서 `docs/testing/rag/d04-0-row-child-preprocessing-evaluation-contract.md`는 현재 HEAD에 없어 경고로 기록

### 생성된 산출물 Hash

| 산출물 | SHA-256 |
|---|---|
| `data/processed/structured/rag/experimental/rag_parent_pages_v2.jsonl` | `FDE0EFE1275114F8BE3DE190055251D411C1A38A705E8E929F08998675DDC05D` |
| `data/processed/structured/rag/experimental/rag_child_chunks_v2.jsonl` | `8949C6DD03EE57C87F73E8740F82BD26DAE17259DAF0E85D80D62C4B8FC97ACA` |
| `data/processed/structured/rag/experimental/rag_child_chunks_v2_manifest.json` | `B47A1C61A7C2B0EDBE5AB1113D44E13C255D847F05FB473F4B0573DDED38576A` |
| `data/processed/validation/rag_experiments/rag_child_chunks_v2_qa.json` | `AE013B1FB4A25CA2C5EF51D2A38590B99696B711B39CAB3834541AB39D4D4162` |

임시 생성기는 `data/.runtime/generate_d04_v2.py`에서 실행했으며, 산출물 4개와 달리 Git 추적 대상이 아니다. 후속 재현에 필요한 입력·규칙·명령은 이 문서와 Manifest에 남겼다.

## 11. 후속 실험 인계 조건

데이터 QA를 통과해도 운영 승격으로 판단하지 않는다. 다음은 이동윤 및 공동 검수 단계다.

1. `child_only_v2`와 `child_parent_context_v2`가 동일한 Child 순위 결과를 사용하는지 확인
2. Parent Context 중복 제거 확인
3. Parent 추가 Token과 지연시간 기록
4. `RAGV2-GOLD-0025`, `RAGV2-GOLD-0027` Top-5 별도 분석
5. `RAGV2-GOLD-0036`~`0038` Evidence Group 기준 Completion Rank 분석
6. 결론에 영향 주는 11건과 정상 통제 표본의 사람 검수
7. 기존 B1 v1 대비 검색 성능·정상 통제 회귀·답변 문맥 관련성 비교

특히 Parent가 페이지 전체이므로, 검색 지표는 좋아져도 답변 Context에 무관한 행이 다시 들어갈 수 있다. C안의 채택 근거는 검색 지표만이 아니라 Parent 확장 후 답변 관련성, 안전 문구 보존, 추가 Token과 지연시간까지 함께 검증해야 성립한다.

## 12. 작업 중지 조건

다음 중 하나라도 발생하면 산출물을 확정하지 않고 논의로 돌린다.

- 기준 HEAD 또는 입력 Hash가 작업 중 변경됨
- 누수 Group·Variant 매핑이 Adapter 계약과 불일치
- Child 하나에 Evidence Group이 둘 이상 필요해짐
- 행 경계를 원본 PDF에서 한 가지로 판단할 수 없음
- 기존 Registry ID 변경이 필요함
- PM 참고 계약서가 추가됐고 이 계획의 스키마와 충돌함
- Gold 질문 표현을 넣어야만 검색 성능이 나오는 상황
- 원본·B1·MVP·Gold·`ai/**`에 예상 밖 diff가 생김

## 13. 현재 결정값

```text
plan_status=EXECUTED_DATA_GENERATION_ONLY
parent_child_option=C
retrieval_unit=CHILD
evaluation_unit=EVIDENCE_GROUP
context_unit=PARENT_DEDUPLICATED
parent_count=5
child_count=15
evidence_group_count=7
leak_variant_count=3
option_b=KEEP_AS_RETRIEVAL_CONTROL
variant_canonical_format=SHORT_SOURCE_VARIANT_ID
pm_variant_format=MANIFEST_ALIAS
runner_owner=LEE_DONGYOON
production_adoption=NOT_APPROVED
```

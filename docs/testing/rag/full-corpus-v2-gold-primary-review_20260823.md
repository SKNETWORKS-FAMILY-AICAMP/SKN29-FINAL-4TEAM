# Full Corpus v2 데이터 인계·Gold 1차 검수 결과

> 실행일: 2026-08-24 KST
> 역할: 김은진 — 데이터·QA·DevOps
> 기준 HEAD: `e99cf78faa58a40f2cec49281119c437b594e470`
> Corpus 상태: `FULL_CORPUS_V2_DATA_HANDOFF_READY`
> Gold 상태: `GOLD_REVIEW_PACKET_READY_HUMAN_SIGNOFF_PENDING`
> IAC425 후보 상태: `IAC425_GOLD_CANDIDATES_READY`

## 결론

현재 96개 페이지 기준 Corpus에서 JAC104 5·7·37·38·39쪽을 행 단위 Child와
누락 구간 보존 Chunk로 교체하는 데이터 인계본을 생성했다. 검색 후보는 기존
페이지 91건, 검증된 Child 15건, 보존 Chunk 5건으로 총 111건이다. Parent 5건은
`CONTEXT_ONLY`이며 검색 후보에 포함하지 않았다.

이 산출물은 AI Runner와 운영 설정에 연결되지 않았다. 따라서 Full B1 성능,
운영 청킹 채택 또는 Runtime 적용 완료를 의미하지 않는다.

## Corpus v2 구성과 완전성

| 구분 | 건수 |
|---|---:|
| 기존 Source Page | 91 |
| JAC104 Child | 15 |
| 보존 Chunk | 5 |
| 검색 후보 합계 | 111 |
| Context 전용 Parent | 5 |

제품별 검색 후보는 `WPUJAC104DWH` 59건, `WPUIAC425SNW` 52건이다.

보존 Chunk는 5쪽 1~4·8~21행, 7쪽 1~11·15~31행, 38쪽 12~18행이다.
Coverage Map은 교체 대상 5개 페이지의 모든 행을 `CHILD`, `PRESERVATION`,
`NON_SEARCHABLE_STRUCTURE` 중 정확히 하나로 분류한다. 페이지 번호와 순수
Section·표 Header만 검색 후보에서 제외했다.

## Gold 60건 1차 검수

Gold 원본과 검수 상태는 변경하지 않았다. 자동 계보·정책 대조 결과는 다음과 같다.

| 판정 | 건수 | 의미 |
|---|---:|---|
| `SUPPORTED` | 40 | Registry·문서·페이지·Section·위험도·안내 정책이 일치 |
| `SOURCE_CHECK_REQUIRED` | 18 | Page 단위 Safety 근거 또는 무근거·교차제품 Case라 사람 확인 필요 |
| `CHANGE_PROPOSED` | 2 | 0045·0049는 인용 Page가 사후 중단 조치를 완전히 뒷받침하지 않아 근거 변경 제안 |
| `REJECT_PROPOSED` | 0 | 자동 반려 제안 없음 |

모든 검수 행은 `human_signoff_status=PENDING`이다. 이 결과는 사람 1인 검수나
2인 승인을 대체하지 않으며 `ONE_PERSON_REVIEWED`, `TWO_PERSON_APPROVED`로
승격하지 않는다.

질문 문구 60건의 1차 결정은 별도 Working Log에 기록했다. 제안문 승인 23건,
문구 변경 승인 36건, 질문 제외 제안 1건(`RAGV2-GOLD-0040`)이며 의미 변경
표시는 19건이다. 질문 제외는 확정 삭제가 아니며 Gold 원본과 자동 검수 Packet은
변경하지 않았다. 질문 확정에 따라 Evidence, `ANY/ALL/NONE`, 위험도와 안내
정책을 다시 대조한 후속 Packet도 별도로 생성했다. 후속 판정은 `SUPPORTED` 33건,
`CHANGE_PROPOSED` 7건, `SOURCE_CHECK_REQUIRED` 19건, `REJECT_PROPOSED` 1건이며
모든 사람 서명 상태는 계속 `PENDING`이다.

검수 Packet에는 60건의 질문 Snapshot, 자동 판정 사유, 검수 우선순위,
Evidence Registry 또는 Manual Page 상대 경로, 사람이 확인해야 할 항목을 함께
기록했다. 0045는 제품 내부에 이미 물이 들어간 상황인데 P004가 예방 문구만
제공하고, 0049는 가연성 스프레이 사용 후 이상 냄새 상황인데 P004가 사용 금지만
제공한다. 두 Case 모두 실제 중단 조치를 직접 뒷받침하는 P005 포함 여부를 사람이
결정해야 한다.

## IAC425 후보 범위 보정

기존 3모델 평가 데이터에는 IAC425 관련 Case가 19건 있지만 양성은 18건이고
부정은 1건이다. 부정 Case를 양성 Gold 후보로 바꾸지 않고, 기존 양성 질문 18건만
그대로 재사용했다. 각 후보에는 검증된 Child·Evidence Group·문서·페이지·Section
Variant를 연결하고 `proposed_split=DEV`, `HUMAN_REVIEW_PENDING`을 유지했다.

최종 Gold Case ID 부여, Dataset Version 변경과 원본 병합은 이동윤 및 두 번째
검수자 승인 전에는 수행하지 않는다.

## 실행·검증

```powershell
.\ai\.venv\Scripts\python.exe -B `
  -m data.tools.rag_experiments.build_full_corpus_v2_review

.\ai\.venv\Scripts\python.exe -B `
  -m data.tools.rag_experiments.qa_full_corpus_v2_review

.\ai\.venv\Scripts\python.exe -B `
  -m data.tools.rag_experiments.build_gold_query_label_revalidation

.\ai\.venv\Scripts\python.exe -B -m unittest discover `
  -s data/tools/tests -v

.\ai\.venv\Scripts\python.exe -B data/tools/pipeline.py qa --verify-rebuild
```

생성기 전용 QA 기준은 Corpus 111건, Gold 검수 60건, IAC425 양성 후보 18건,
오류 0건이다. 기준 HEAD에서 전체 데이터 단위 테스트 135건, Pipeline QA
60파일·990레코드, 기존 AI 청킹 표적 테스트 6건을 실행해 모두 통과했다.
`--verify-rebuild`의 changed file과 canonical drift는 모두 0건이다.

## 담당자 인계

이동윤은 이 인계본을 별도 실험 Profile에 연결해 Child-only와 제한된 Context
확장을 비교해야 한다. 기존 D04의 전체 페이지 Parent 기본 확장 방식은 재사용하지
않는다. 전체 DEV·NO_EVIDENCE를 포함한 B1을 다시 실행하고 현재 Corpus Hash,
BGE-M3 Revision과 결과 Manifest를 고정해야 한다.

윤승혁은 Gold 사람 검수와 B1 재실행 뒤에만 운영 청킹 Profile Gate를 판정한다.
현재 산출물로 운영 채택이나 성능 PASS를 선언하지 않는다.

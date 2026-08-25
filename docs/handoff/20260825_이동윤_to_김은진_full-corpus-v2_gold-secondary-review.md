# Full Corpus v2·Gold 독립 2차 기술 검수 회신

> 회신자: 이동윤 — AI·RAG 담당 2차 검수
> 인계자: 김은진 — 데이터·QA·DevOps 1차 검수
> 검수일: 2026-08-25 KST
> 검수 브랜치: `dongyoon`
> 검수 기준 HEAD: `c0784240227933eb632715dd3c2889e0425e2ce2`
> 인계 문서: `docs/handoff/20260824_김은진_to_이동윤_full-corpus-v2_gold-primary-review.md`

## 한 줄 요약

**Full Corpus v2 구조·재현 QA는 PASS지만 Gold 변경안은 7건 중 1건만 승인하며, 0040은 현 평가에서 제외하고 0055는 무근거 판정을 반려하며, 0045·0049와 IAC425 18건의 Gold 병합은 Evidence ID–Corpus–Runner 계약 불일치가 해소될 때까지 HOLD한다.**

## 1. 최종 판정

| 검수 항목 | 상태 | 2차 검수 결론 |
|---|---|---|
| 고정 입력과 SHA-256 | `PASS` | 인계 Manifest와 현재 파일이 일치한다. |
| Full Corpus v2 구조·결정성 QA | `PASS` | 검색 후보 111건, JAC104 59건, IAC425 52건과 QA 오류·경고 0건을 재확인했다. |
| Gold 60건 2차 기술 검수 | `PARTIAL` | Case별 결론은 냈지만 P004·P005 원본 화면의 독립 시각 검증과 사람 최종 서명이 남았다. |
| 라벨 변경 제안 7건 | `PARTIAL` | `0039`만 승인, 나머지 6건은 제출안 그대로는 반려한다. |
| `0040` | `APPROVE_EXCLUSION` | 현 scored Gold에서 제외하되 레코드 삭제·Case ID 재사용은 금지한다. |
| `0045`, `0049` | `HOLD` | P004·P005를 모두 `ALL`로 요구하는 안을 승인하지 않는다. 좁은 의미 Evidence와 required/supporting 계약이 필요하다. |
| `0051~0060` | `PARTIAL` | 9건 승인, `0055`의 `NO_EVIDENCE_CORPUS_ABSENCE`는 반려한다. |
| IAC425 후보 18건 | `HOLD` | 계보는 유효하지만 현 Corpus에는 후보 Child `0/19`, Evidence Group `0/18`이다. 직접 병합 승인 `0/18`. |
| Gold 원본 반영 | `HOLD/NOT_DONE` | 이 회신에서는 원본을 수정하지 않았다. |
| Full B1 재실행 | `NOT_RUN` | 승인 Dataset·Corpus 계약이 아직 확정되지 않았다. |
| AI Runner Full Corpus v2 연결 | `NOT_RUN` | Gold–Corpus compatibility gate 이후 진행한다. |
| 사람 최종 서명 | `PENDING` | `TWO_PERSON_APPROVED`가 아니다. |

이 판정에서 `PASS`는 데이터 구조와 재현성 범위만 뜻한다. Retrieval 품질,
Provider, Backend 저장·Replay 또는 운영 Runtime PASS로 확대하지 않는다.

## 2. 검수 기준과 실행 증거

고정 입력 SHA-256은 다음과 같이 일치했다.

| 파일 | SHA-256 |
|---|---|
| `ai/evaluation/corpora/full_corpus_chunks_v1.jsonl` | `4B0890BC079207C8F9AA9DB1208D371F295BD53537A9B692FA6B7D686333FABC` |
| `ai/evaluation/datasets/gold/rag_gold_v1.jsonl` | `9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A` |
| `data/processed/structured/rag/experimental/full_corpus_chunks_v2.jsonl` | `2D4A022A8FEABD376C9F5D42E7D28BA8E18571274D19A05794D066B7113D6FC6` |

실행한 검증은 다음과 같다.

```powershell
.\ai\.venv\Scripts\python.exe --version
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s data\tools\tests -v
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\test_chunking_experiment_v1.py ai\tests\unit\test_row_child_partial_experiment_v2.py -q -p no:cacheprovider
.\ai\.venv\Scripts\python.exe -B -m data.tools.rag_experiments.qa_full_corpus_v2_review --output <OS 임시 파일>
```

| 명령 범위 | 결과 |
|---|---|
| Python | `3.13.13` — `PASS` |
| Data Unit | `136 tests`, `OK`, exit `0` — `PASS` |
| 기존 AI 청킹 표적 Unit | `6 passed in 1.43s`, exit `0` — `PASS` |
| Full Corpus v2 QA 임시 출력 | `status=PASS`, 오류 `0`, 검색 후보 `111`, Gold 검수 `60`, IAC 후보 `18`, Promotion `NOT_APPROVED` |

Data 소유 생성물을 덮어쓰지 않기 위해 QA 출력은 OS 임시 파일로 분리했다.
Builder와 `data\tools\pipeline.py qa --verify-rebuild`는 이 차수에 다시 실행하지
않았으므로 해당 명령 자체의 현 차수 상태는 `NOT_RUN`이다. 검수 시작 전과 원본
대조 직후 Worktree는 Clean이었다. 현재 `git status --short`에는 이 신규 회신문서
1건만 `??`로 나타나며 Gold·Corpus 원본 변경은 0건이다.

## 3. 변경 제안 7건 판정

`expected_guidance_policy`와 상담 필요 여부는 같은 값이 아니다. 현재 Evidence
Registry도 사용 상태와 조건부 상담 전환을 분리한다. 따라서 “상담이 필요할 수
있다”는 이유만으로 제품 사용 상태를 모두 `PENDING_CONSULTATION`으로 바꾸면
Gold 라벨이 질문의 안전·사용 상태가 아니라 서비스 요청 의도에 끌려간다.

| Case | 2차 판정 | 확정 내용과 이유 |
|---|---|---|
| `0001` | `REJECT` | `caution / PARTIAL_STOP`을 유지한다. “빨리 고쳐주세요”는 서비스 의도를 추가했을 뿐 무출수 사용 정책을 바꾸지 않는다. 인계 요약은 유지라고 적었지만 검수 Packet은 `PENDING_CONSULTATION` 변경안이므로 Packet 쪽 불일치도 정정해야 한다. |
| `0016` | `REJECT` | `general / NORMAL` 유지. 2시간 후에도 냉수가 차갑지 않으면 상담 전환 조건은 별도 `expected_requires_consultation=true` 성격이며 사용 상태 자체가 대기 상태는 아니다. COLD 정상·고장 Child가 같은 넓은 Evidence ID를 공유하는 문제도 먼저 분리해야 한다. |
| `0017` | `REJECT` | `general / NORMAL` 유지. 과도한 소음일 때의 상담 조건은 별도 평가 필드로 표현한다. |
| `0028` | `REJECT` | `general / NORMAL` 유지. “어떻게 조치해 주실 건가요”는 고객 의도를 서비스 처리로 바꾼 문구이며 저유량 사용 상태 변경 근거가 아니다. |
| `0033` | `REJECT` | `general / NORMAL` 유지. 큰 소음의 조건부 상담은 사용 상태와 분리한다. |
| `0039` | `APPROVE` | `COMPOUND → DIRECT`, 무출수 Evidence 1건과 `ANY`를 승인한다. “작동 소리”는 무출수 상황의 문맥이지 독립 소음 증상 정답이 아니다. `caution / PARTIAL_STOP`은 유지한다. |
| `0047` | `REJECT_CURRENT_CONTRACT` | 제출된 `caution / PARTIAL_STOP` 변경은 현재 Validator의 `SAFETY → danger / TOTAL_STOP` 계약과 충돌하고, 예방 질문으로 의미도 바뀌었다. 기존 Case를 억지로 완화하지 말고 별도 비사고·예방 Case와 좁은 온수 접촉 방지 Evidence로 재설계한다. |

순수 변경안 집계는 `APPROVE 1 / REJECT 6`이다. 반려는 질문 주제를 폐기한다는
뜻이 아니라 현재 Gold 계약에 그대로 반영하지 않는다는 뜻이다.

## 4. `0040`, `0045`, `0049` 판정

### `0040` — 현 scored Gold 제외 승인

- 질문은 “온수 사용 중 물이 새고 뜨거운 물이 튀었습니다.”로 누수와 온수
  분사 두 조건을 묶는다.
- 현재 넓은 HOT Evidence는 정상 현상, 잠금·재연결, 미지근함, 미출수,
  모듈 점검까지 함께 포함해 이 질문의 정확한 사고 조건을 보증하지 않는다.
- 누수 Evidence만으로는 `danger / TOTAL_STOP`은 설명되지만 복합 질문의 두
  정답을 모두 충족했다고 채점할 수 없다.
- 따라서 현 평가에서는 제외한다. 레코드는 삭제하지 않고
  `EXCLUDED_PENDING_REDRAFT`와 기존 Case ID를 보존한다.
- 재진입은 “누수 + 지속적 증기/온수 분사”를 명시한 질문과 좁은
  `HOT_STEAM`·`LEAK` Evidence의 `ALL` 또는 두 개의 단일 Case로 재설계한 뒤다.

### `0045` — P004·P005 `ALL` 반려, 재설계 HOLD

- P004는 제품 내부로 물이 들어가지 않도록 하고 화재·감전 위험을 경고하는
  예방 근거다.
- P005는 실제 누수·고임·이상 상태 이후의 중단 조치 근거이며 다른 predicate다.
- “물이 들어간 것 같은데 전원이 켜져 있다”는 질문에 두 페이지를 모두
  정답으로 강제해도 P004의 예방 문구가 사고 후 조치 전체를 직접 말해 주지는
  않는다.
- 물 유입 이후의 조치를 공식 근거로 고정한 `WATER_INGRESS_RESPONSE` Evidence를
  만들거나 질문을 “내부에서 물이 흐르고 전원이 켜져 있음”으로 좁힌 뒤 누수
  Evidence를 연결해야 한다.

### `0049` — P005 required, P004 supporting; `ALL` 반려

- P005의 타는 냄새·연기·이상 발생 후 중단 조치가 질문의 필수 정답이다.
- P004의 살충제 사용 금지는 원인·예방 문맥으로는 유효하지만 응답 적합성의
  필수 정답으로 강제할 근거는 약하다.
- 현 Gold Schema에는 required와 supporting Evidence 구분이 없으므로 P004·P005
  `ALL`을 승인하지 않는다.
- 좁은 `BURNING_ODOR_RESPONSE` Evidence를 required로 만들고 P004는 supporting
  또는 completeness-only 근거로 분리한다.

### 현재 Corpus–Runner 차단 사항

Full Corpus v2에서 P004 Page ID는 검색 후보로 존재하지만 P005 원본 Page ID의
정확 일치는 `0건`이다. P005는 누수 Child와 Preservation Chunk로 분할됐고,
Runner는 Gold ID와 `chunk.evidence_unit_ids`를 exact match한다. 따라서 현재
P005를 기대하는 기존 `0041`, `0042`, `0044`, `0046`, `0048`, `0050`과 제안
`0045`, `0049`, 합계 8건은 정답 내용이 Corpus에 있어도 현 ID 계약에서는
채점 불가능하다.

또한 한 개의 넓은 Evidence Group이 의미가 다른 Child 여러 개에 붙어 있다.
현재 확인한 주요 충돌은 HOT 6개, COLD 2개, LEAK 3개 Child다. 이 상태에서는
관련 없는 Child가 검색돼도 정답 Hit로 오인될 수 있다.

P004·P005는 현재 저장소에 원본 PDF가 없어 이 차수에서 독립 화면 시각 검증을
실행하지 못했다. 추출 본문과 계보·Corpus·Runner 대조 결과로 위 기술 판정을
내렸으며, 원본 화면 확인은 `NOT_RUN`이자 사람 최종 서명의 선행 조건이다.

## 5. `0051~0060` 무근거 판정

| Case | 판정 | 정확 모델·Corpus 범위의 결론 |
|---|---|---|
| `0051` | `APPROVE` | 월 렌탈료·제휴카드 할인 정답이 없다. |
| `0052` | `APPROVE` | 소모품 안내와 별개로 현재 필터 판매 가격 정답은 없다. |
| `0053` | `APPROVE` | 기사·서비스 언급은 있지만 실시간 방문 도착시간은 없다. |
| `0054` | `APPROVE` | 출수 LED 색상은 구매 가능한 제품 외관 색상 정답이 아니다. |
| `0055` | `REJECT` | Gold의 모델 필드는 `WPUJAC104DWH`인데 동일 제품 Corpus에 누수 차단·상담 Evidence가 존재한다. Corpus 부재가 아니다. |
| `0056` | `APPROVE` | JAC104 범위에 제빙 기능 정답이 없다. IAC425 근거는 교차 제품이라 금지한다. |
| `0057` | `APPROVE` | JAC104 범위에 얼음 저장고 분리·청소 정답이 없다. |
| `0058` | `APPROVE` | JAC104 범위에 얼음 크기·제빙량 설정 정답이 없다. |
| `0059` | `APPROVE` | 정확 모델 `WPU-IAC506` Corpus가 없으며 정책 차단 대상이다. 질문이 모델명을 생략하므로 Runner의 모델 필터 적용을 함께 검증해야 한다. |
| `0060` | `APPROVE` | 정확 세대 `WPUJAC104SWH` Corpus가 없다. D세대 근거를 재사용하면 안 된다. |

`0055`는 다음 중 하나로 다시 설계한다.

1. 미검증 FAQ 정책 차단 Case: 모델 미확인 질문과 Gold의 정확 모델 필드 모순을
   제거하고 `POLICY_BLOCK_UNVERIFIED_SOURCE`를 검증한다.
2. 정확 JAC104 누수 Case: 양성 누수 Evidence와 안전 라벨을 연결한다.

현재 `general / CONSULTATION_ONLY`도 누수 Safety 의미와 맞지 않으므로 그대로
유지할 수 없다.

## 6. IAC425 후보 18건 판정

원문 계보는 구조적으로 유효하다.

- `RAG3-POS-001~018`과 후보 18건이 1:1이다.
- 정확 제품은 모두 `WPUIAC425SNW`이며 JAC104·IAC606은 금지 모델이다.
- Evidence Group 18개와 검증 Child Variant 19개가 Expansion 자산에 있고
  `TEXT_AND_VISUAL_VERIFIED`다.
- 원문 답 내용은 IAC425 5·43·44·45·46쪽에 있다.

그러나 현 상태의 Gold 직접 병합은 `HOLD`, 승인 수는 `0/18`이다.

1. Full Corpus v2에는 후보 Child ID `0/19`, Evidence Group ID `0/18`이며 관련
   Source Page만 있다. 현재 Runner로는 18건 모두 구조적으로 Miss가 될 수 있다.
2. 후보 JSON은 Gold Schema가 아니다. `case_id`, `dataset_version`,
   `evidence_match_policy`, 금지 문서, Source 계보, 라벨 생성·검수 필드가 부족하다.
3. `CAND-010`은 같은 Evidence Group 아래 P005·P045 두 Variant다. 의미는
   `ANY_VARIANT_PER_GROUP`인데 현재 Runner는 이를 표현하지 못한다.
4. 양성 18건만 추가하면 IAC425 부정·교차 제품 통제가 없다. 기존
   `RAG3-NEG-002`의 포함 여부를 명시하고 별도 Holdout을 추가해야 한다.

후보 내용별 다음 조치는 아래와 같다. 이는 Gold 병합 승인이 아니다.

| 분류 | 후보 | 다음 조치 |
|---|---|---|
| 내용상 전환 가능 | `001`, `004`, `006`, `008`, `009`, `012`, `013`, `014`, `016` | Schema 변환과 Corpus 연결 후 재검수 |
| 관찰 가능한 질문으로 문구 교정 | `002`, `003`, `010` | 원문 표제 복사가 아닌 사용자 관찰 증상으로 수정 |
| 정책 재검토 | `005`, `007`, `011`, `015`, `017`, `018` | 정상/고장 조건, 사용 상태와 상담 조건, JAC104 안전 일관성을 분리 |

특히 `007`은 일반 온수 중단과 빨간 표시·점멸 고장을 분리하고, `011`·`015`·
`017`은 조건부 상담을 단순 증상과 분리하며, `018`은 맛·냄새 정책을 JAC104와
일관되게 다시 정한다. Page ID로 임시 치환하면 한 페이지가 서로 다른 다수
증상의 정답이 되어 청킹 평가가 무의미해지므로 사용하지 않는다.

## 7. 효율적인 청킹·Gold 연결 전략

### 7.1 기존 v2는 고정하고 새 실험 버전에서 보정

현재 v2 Hash를 보존한다. 데이터 소유 Full Corpus v2를 AI가 직접 덮어쓰지
않고, Data/QA와 합의한 새 Corpus Version에서 아래 보정을 수행한다.

- JAC P004: `SPRAY_FIRE_PREVENTION`, `WATER_INGRESS`를 의미 단위 Child로 분리
- JAC P005: 누수와 별도로 `BURNING_ODOR_RESPONSE` Child 생성
- JAC COLD: 정상 조건과 고장·상담 조건의 Evidence ID 분리
- JAC HOT: 6개 증상 Child에 좁은 Evidence ID 부여
- IAC425: 5·43·44·45·46쪽의 19개 검증 Child를 Coverage·Preservation과 함께
  Full Corpus 검색 후보에 연결
- Parent는 검색 정답이 아니라 Evidence Group 또는 Source Span 범위의
  `CONTEXT_ONLY`로 유지

페이지 전체를 한 정답으로 쓰거나 페이지 Metadata에 모든 Evidence ID를 붙여
Metric을 맞추지 않는다.

### 7.2 Gold–Corpus Compatibility Gate 선행

Full B1 전에 자동 Gate를 추가한다.

1. 활성 양성 Gold의 required Evidence ID가 검색 후보에 최소 1회 존재한다.
2. Group형 정답은 허용 Variant 중 하나가 실제 검색 후보에 존재한다.
3. `ALL`의 각 required predicate가 서로 독립적으로 매치 가능하다.
4. 같은 Evidence ID가 의미가 다른 Child에 붙으면 실패하거나 명시한 Variant
   Group 계약으로만 허용한다.
5. 정확 모델·금지 문서·검증 상태가 모두 일치한다.
6. `NONE`은 Answer Corpus 부재와 정책 차단을 다른 이유 코드로 기록한다.

이 Gate가 있었으면 P005 exact ID `0건`과 IAC425 Child `0/19`를 평가 전에
차단할 수 있었다.

### 7.3 Gold 계약 확장

새 Dataset/Schema Version에서 다음을 분리한다.

- `expected_guidance_policy`
- `expected_requires_consultation`
- `required_evidence`
- `supporting_evidence`
- `evidence_group_id`와 `allowed_variant_ids`
- `no_evidence_reason` (`CORPUS_ABSENCE`, `POLICY_BLOCK_MODEL`,
  `POLICY_BLOCK_UNVERIFIED_SOURCE` 등)

`0040` ID는 재사용하지 않는다. IAC425는 새 Case ID를 부여하되 위 계약,
부정 Case와 Holdout이 확정된 뒤에만 Dataset Version을 올린다.

## 8. 담당자·완료 조건·회신 형식

| 담당 | 필요한 작업 | 완료 조건 | 회신 형식 |
|---|---|---|---|
| 이동윤 / AI | 좁은 Evidence·Variant 계약, Gold Schema·Validator·Runner 변경안, Compatibility Gate 설계 | 모든 활성 양성 ID가 검색 후보에서 매치 가능하고 `ALL/ANY/NONE`이 독립 테스트로 검증됨 | 변경 파일, Dataset/Schema Version, 표적 테스트 명령·결과, 40자리 SHA |
| 김은진 / Data·QA | P004·P005 독립 원본 화면 확인, IAC425 19 Child의 Coverage·Preservation 포함 Corpus 생성 | 원본 근거 확인 기록, Child `19/19`, Group `18/18`, 누락/중복 0, 결정성 Hash 재생성 일치 | Case별 승인/반려, Source page·lineage ID, QA 결과와 Hash; 원문·Secret 본문 제외 |
| 이동윤·김은진 공동 | 7개 변경과 0040/45/49/55 최종 사람 서명 | reviewer ID·시각·Case별 결정이 모두 기록되고 `PENDING=0` | 서명 Packet 경로와 SHA-256 |
| PM·관련 검수자 | Dataset Version·공개 평가 범위 승인 | DEV/Holdout 분리, IAC 부정 통제, 운영 주장 범위 승인 | 승인 범위와 결정 기록 |

위 조건을 충족한 뒤에만 승인된 내용을 새 Gold 원본에 반영하고 Full B1을
재실행한다. 그 전 상태는 `PARTIAL/HOLD`이며 `TWO_PERSON_APPROVED`, Gold 반영
완료 또는 성능 개선으로 표시하지 않는다.

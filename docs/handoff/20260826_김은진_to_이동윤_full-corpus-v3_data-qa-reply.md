# Full Corpus v3 Data·QA 인계

> 보내는 사람: 김은진 — Data·QA
>
> 받는 사람: 이동윤 — AI·RAG
>
> 기준 HEAD: `7ea17f55082d7f63ad4497476b33f45b5b6735f6`
>
> 상태: `FULL_CORPUS_V3_DATA_HANDOFF_READY`

## 완료한 내용

P004·P005 원본 구문은 김은진이 다음과 같이 결정했습니다.

- `1-A`: P004 살충제·가연성 스프레이 문구를 별도 예방 카드로 사용
- `2-A`: P004 제품 내부 물 유입 문구를 별도 예방 카드로 사용
- `3-A`: P005 누수 문구를 P007·P038과 같은 누수 Group의 대체 Variant로 사용
- `4-A`: P005 타는 냄새·연기 문구를 별도 긴급 대응 카드로 사용

원본 PDF는 저장소에 넣지 않았습니다. Source Inventory ID는
`SRC-JAC104D-MANUAL`, PDF SHA-256은
`0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C`입니다.

## 전달하는 데이터

| 항목 | 건수 | SHA-256 |
|---|---:|---|
| Full Corpus v3 | 132 | `B92B72E70BD3DCDD0B82EAAA04B707992932E75BEB46748A7369DFDC0F4D9BA8` |
| Child Registry | 37 | `02B4CD0CB140D5FE8485D374BC3E1B7124044E4F5B6ECF72B4A8E528AF5550F5` |
| Evidence Group Registry | 34 | `F16EF48EC8CEB4C810E66D92B2084546479CF21A9D08E6BCC45164DDEED4977E` |
| Context-only Parent | 11 | `16774B82CAE5A7D88D36FFA21A47F1758824275F8B06BB7F38630EEEE6F4616D` |
| Coverage Map | 11쪽 | `D2757EE56A6F214F84E451FC158A6DF4BA5500030E5DF0DD5088A1C957E2F7CC` |
| Data QA | 오류 0 | `116548B2746225D86664DE405291E0900E965BBA2BB41BE17C251C028BDC6F2E` |
| Handoff Manifest | 1 | `234E1397B82DFCBCF7592B0066B884B477213D1EAC460CB4013865CB7A9E3203` |

구성은 JAC104 64건, IAC425 68건입니다. IAC425는 Evidence Group 18/18,
Child 19/19가 Corpus까지 연결됐습니다.

## 확인 결과

- 데이터 단위 테스트: `142 tests`, `OK`
- 데이터 Pipeline QA: 오류 0, 경고 0, 재생성 drift 0
- 기존 청킹 테스트: `6 passed`
- Gold v2 계약 표적 테스트: `78 passed, 30 subtests passed`
- Group–Child–Corpus 구조 검사: Group 34/34, Child 37/37 연결, 오류 0

구조 검사는 Gold v2 파일이 아직 없어 빈 Gold 입력으로 실행했습니다. 따라서 이
PASS는 연결 구조만 뜻하며 실제 Gold Case 채점 PASS는 아닙니다.

## 이동윤이 다음에 할 일

1. 승인할 Case만 `rag_gold_v2.jsonl`로 만듭니다.
2. 실제 Gold v2를 넣어 `validate_gold_corpus_compatibility_v2.py`를 다시 실행합니다.
3. `0049`는 `BURNING_ODOR_RESPONSE`를 Required,
   `SPRAY_FIRE_PREVENTION`을 Supporting으로 연결합니다.
4. `0045`는 예방 근거와 사고 후 대응 근거를 섞지 말고 다시 설계합니다.
5. 조건부 상담 Case를 넣기 전에 Evidence Group의 Condition ID와 Source Child
   연결을 확정합니다. 현재 구조 검사 결과는 `registered_conditions=0`입니다.
6. 실제 Gold 연결이 PASS한 뒤 Full B1 v2를 실행합니다.

현재 상태는 Source Span Data/QA 승인까지입니다. Gold 병합,
`TWO_PERSON_APPROVED`, Full B1 성능 승인과 운영 연결은 아직 완료가 아닙니다.

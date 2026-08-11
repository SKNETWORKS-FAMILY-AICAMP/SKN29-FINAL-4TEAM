# D-02 누수 Gold Evidence 시각 검수·보정 기록

> 검수일: 2026-08-11 KST
> 상태: `TARGETED_VISUAL_REVIEW_COMPLETE_HUMAN_APPROVAL_PENDING`
> 대상: `RAGV2-GOLD-0004`, `RAGV2-GOLD-0027` 및 동일 누수 Evidence Unit 사용 Case

## 결론

JAC104/JCC104 REV.00 매뉴얼 5·7·38페이지는 모두 제품 내부 또는 주변의 물 누수 상황에서 다음 안전조치를 직접 안내한다.

1. 원수 밸브를 잠근다.
2. 전원 플러그를 뺀다.
3. 고객상담센터 또는 서비스센터에 연락한다.

따라서 세 페이지를 모두 `EVD-WPUJAC104DWH-LEAK-001`의 **완전 근거**로 판정했다. 같은 안전조치가 반복된 페이지이므로 별도 Evidence Unit 세 개로 분리하지 않고, 하나의 논리적 Evidence Unit에 `page_refs=[5,7,38]`을 부여했다.

## 원본 확인

검수 원본:

```text
C:/Users/윤승혁/Downloads/(rev00)+WPU-JAC104+(D),+JCC104+(D)_User_KO_260428.pdf
```

원본 PDF SHA-256:

```text
0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C
```

이 Hash는 `manual_pages_jac104d.jsonl`에 기록된 `source_file_sha256`과 일치한다. PDF 전체 페이지 수는 44쪽이며, PDF 물리 페이지와 인쇄 페이지 번호가 일치하는 5·7·38페이지를 PNG로 렌더링해 원문을 확인했다.

| 페이지 | 시각 확인 내용 | 판정 |
|---:|---|---|
| 5 | 제품 안쪽 또는 주변에 물이 고이면 원수 밸브 차단·플러그 분리·상담센터 연락 | 완전 근거 |
| 7 | 같은 누수 상황에서 원수공급밸브 차단·플러그 분리·서비스센터 연락 | 완전 근거 |
| 38 | 제품 누수 발생 시 원수 밸브 차단·플러그 분리·고객상담센터 연락 | 완전 근거 |

## 반영 범위

* 누수 Evidence Registry의 원본 페이지를 38쪽에서 5·7·38쪽으로 보정
* Full Corpus 5·7페이지 Chunk에 `EVD-WPUJAC104DWH-LEAK-001` 연결
* Gold Dataset을 `1.0.0-draft.2`로 갱신
* 누수 Evidence Unit을 사용하는 8개 Case의 `page_refs`를 `[5,7,38]`로 일괄 반영
* 표적 Case `0004`, `0027`에서 5·7·38페이지는 Hit, 관련 없는 6페이지는 Miss가 되도록 회귀 테스트 추가

과거 7청크 기준 파일 `rag_verified_sample.jsonl`은 기존 실행 증빙·Index Hash를 보존하기 위해 38페이지 기반으로 유지한다. D-02 이후 비교 기준은 96페이지 Full Corpus `1.0.1`이며, 레거시 7청크 결과를 새 Gold 성능 수치로 재사용하지 않는다.

## 갱신 Hash

| 산출물 | SHA-256 |
|---|---|
| Gold Dataset | `9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A` |
| Full Corpus | `FE62AF6030045C532BC8E68D11C5461E8C65BD16DCD6758E0C2412C8C37C472C` |
| Evidence Registry | `40A1B328F86FF6E57A3EFD1F5EBD63051DCDE06AB32E0A08CC6C6D5BE638F61F` |

## 승인 제한

이번 판정은 원본과 데이터 Lineage를 대조한 표적 기술 검수다. 60건 전체에 대한 사람 2인 검수를 대체하지 않으며, 모든 Case의 `review_status`는 `UNREVIEWED_DRAFT`로 유지한다. 새 Hash로 Baseline을 재실행할 수는 있지만 결과는 계속 Draft로만 사용한다.

또한 A1의 44페이지 전체 시각 검수가 끝난 것은 아니므로 `manual_pages_jac104d.jsonl`의 페이지 단위 검수 상태를 일괄 승격하지 않았다. D-02의 5·7·38페이지 판정과 원본 Hash는 이 표적 검수 기록 및 Evidence Registry에서 추적한다.

## D-01·D-02 반영 Baseline 재실행

2026-08-11 KST에 BGE-M3 CPU Baseline을 다시 실행했다.

* 상태: `DRAFT_BASELINE_COMPLETE`
* 실행 결과: 3 Corpus × 2 Filter × DEV 35건 = 210건
* 실행 시간: 453.96초
* Manifest SHA-256: `89E713F2A9D5BE423CE33893D88BF59D5D3EB4259BA4FC6F4AD831B8E735828C`
* Case Result SHA-256: `A2A983C4A13220D7A5AC8E7BCA58E56B438B5790B597F08DCFF214675953834E`

표적 확인 결과 `0004`는 7페이지 Rank 1로 성공했고, `0027`은 허용 근거 보정 후에도 5·7·38페이지가 Top-5에 없어 검색 실패로 남았다. 따라서 `0027`은 Gold 오류와 검색 실패를 분리해서 해석할 수 있으며 후속 D-04 비교 대상이다.

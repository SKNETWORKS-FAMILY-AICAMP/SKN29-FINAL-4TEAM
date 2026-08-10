# 이동윤 담당 AI·Evidence·오류 처리 인계

> 발신: 김은진 — 데이터·QA·DevOps
> 수신: 이동윤 — AI·RAG
> 작성일: 2026-08-10 KST
> 검증 기준 Commit: `8854ca7b5226df9766b24ba616067ab27d5add99`
> 현재 상태: `ACTION_REQUIRED / PUBLIC_EVIDENCE_AND_LIVE_AI_BLOCKED`

## 1. 인계 목적

Web에 공개할 공식 근거 allowlist와 내부 비노출 항목을 확정하고, AI 성공·근거
없음·검색 실패·Timeout이 Backend를 통해 저장·전달되는 실제 증거를 요청한다.
김은진은 AI Runtime 코드를 수정하지 않았고, 현재 Data·계약·Backend
소비 경계를 검수했다.

공통 실행 결과는
[Web–Backend 실제 연결 QA 보고서](../../testing/results/week4-web-backend-live-verification-20260810.md)를
참조한다.

## 2. 현재 검증 현황

| 항목 | 현재 결과 | 판정 |
| --- | --- | --- |
| Data 단위 Test | 69 passed | `PASS` |
| Data QA·결정성 | 오류 0, 경고 0, Drift 0 | `PASS` |
| 승인 RAG Chunk | 7개, `WPUJAC104DWH` 범위 | `DATA_BASELINE` |
| Retrieval Case | 12개 계약 검증 | `DATA_BASELINE` |
| Public Evidence Schema | `EvidenceCard`·Source·Verification 모두 빈 객체 | `NOT_READY` |
| Public Evidence Path | `{}` | `NOT_READY` |
| AI Evidence Schema | `chunk_id`, `similarity_score` 포함 | `INTERNAL_CONTRACT` |
| Backend Evidence Route | 없음 | `BLOCKED` |
| 실제 AI 오류 HTTP·DB 흐름 | 실행 경로 없음 | `BLOCKED` |

Data Gate 통과는 실제 AI Runtime이나 팀 DB pgvector 검색 성공을 의미하지
않는다. 이번 검증에서는 AI 공식 실행 명령·가상환경·Live Adapter가 없어
AI 테스트와 실제 검색을 새로 실행하지 않았다.

## 3. 공개·내부 Evidence 경계 요청

### Public DTO 포함 후보

- 공식 문서 제목과 버전
- 대표 페이지와 필요한 다중 페이지 번호
- 화면용 짧은 요약
- 검증 상태
- HTTPS 공식 Landing URL
- 안전 행동·금지 행동이 Public 계약으로 승인되는 경우 승인된 요약만 포함

### Public DTO 비노출 필수

- `chunk_id`, Vector·Embedding 식별자
- `similarity_score`와 내부 Ranking 정보
- 내부 파일 경로, 저장소 경로와 직접 다운로드 경로
- 원문 전체와 고객 원문 전체
- Prompt, Chain 내부 상태, 모델 Cache·Revision 내부 경로
- 검증되지 않은 FAQ와 금지 모델 자료

AI `EvidenceReference`는 내부 계약으로 유지할 수 있지만 Backend에 넘길 때
Public allowlist와 internal-only 필드를 명시해 달라. AI가 최종
`EvidenceCardDTO`나 업무 상태를 직접 확정하지 않는다.

## 4. 요청사항

### P0 — Evidence 계약 입력

- 최지용에게 전달할 AI→Backend Evidence 필드표를 확정한다.
- 각 필드를 `PUBLIC_ALLOWED`, `BACKEND_INTERNAL`, `AI_INTERNAL`로 분류한다.
- 근거 없음일 때 빈 Evidence와 구조화 상태가 어떻게 전달되는지 정의한다.
- `WPU-IAC506`, 다른 세대·모델, 미검증 FAQ가 근거로 승격되지 않게 한다.

### P0 — 실제 오류 흐름

- 정상, 근거 없음, 제품 불일치, 검색 실패, Schema 위반, Timeout Case를
  실제 AI Runtime에서 실행한다.
- Timeout·재시도·취소 경계를 기록하고 같은 요청이 중복 실행·저장되지
  않는지 확인한다.
- Backend가 AI 결과를 검증한 뒤 Event·Evidence·오류를 저장하는 형식을
  최지용과 합의한다.

### P1 — 검색 평가 최신화

- 모델 ID·Revision, Embedding 차원, 거리 함수, Index 또는 Exact Search,
  Filter와 Top-k를 기록한다.
- Recall@5, MRR, 금지 문서·모델 Hit, Case별 결과를 현재 Commit에서
  재실행한다.
- 실제 pgvector 결과와 Mock·Fallback·과거 실험 결과를 분리한다.
- Dataset·Chunk·실행 결과 Hash를 연결한다.

## 5. 완료 증거 요청

- [ ] AI→Backend 필드 분류표와 JSON 예시
- [ ] Public 비노출 필드 목록과 자동 테스트
- [ ] 정상·근거 없음·제품 불일치·검색 실패·Timeout 실행 결과
- [ ] 모델·세대·검증 상태 Filter 결과
- [ ] `WPU-IAC506` 및 미검증 FAQ Hit 0 증거
- [ ] Recall@5·MRR·금지 Hit와 Case별 결과
- [ ] 모델 ID·Revision·환경·명령·Exit code
- [ ] Backend 전달 Schema·correlation ID·저장 결과
- [ ] 실제 pgvector와 Mock 결과의 명시적 구분

## 6. 회신 형식

```text
owner=이동윤
decision=ACCEPT | CHANGE_REQUEST | BLOCKED
target_commit=<SHA>
model_id_revision=<ID·Revision>
runtime_environment=<Python·의존성·Vector DB>
public_allowed_fields=<목록>
internal_only_fields=<목록>
error_cases=<Case별 결과>
retrieval_metrics=<Recall@5·MRR·금지 Hit>
dataset_result_hashes=<Hash 연결>
backend_payload_example=<경로>
commands=<실행 명령과 Exit code>
remaining_blockers=<없음 또는 담당자·필요 입력>
target_date=<YYYY-MM-DD>
```

과거 평가 수치나 Data Schema 통과만으로 Live AI·pgvector를 `VERIFIED`로
회신하지 않는다.

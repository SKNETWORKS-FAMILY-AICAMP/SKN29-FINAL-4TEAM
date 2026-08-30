# 3모델 Readonly 50 Case CI·SSM 검증 요청

- 요청일: 2026-08-30
- 요청자: AI/RAG 담당
- 수신: Infra·CI 담당, Backend·DB 담당, Data·QA 담당
- 승인 검토: 윤승혁(PM·통합 검수)
- 기준 후보 SHA: `d1ffd2739883d8c8fedc934131335ed1b1a28dbc`
- 요청 상태: `REVIEW_REQUESTED`
- 목표 판정: `THREE_MODEL_READONLY_GATE_PASS | FAIL | HOLD`

## 1. 요청 목적

`AI_RAG_RUNTIME_PROFILE=three_model_integration`을 Public Runtime에 적용하기 전에,
동일 Release SHA의 전체 검증 자산과 실제 Backend Readonly View를 사용해 공식
3모델 50 Case Gate를 실행해 주시기 바랍니다.

이번 요청은 3모델 Public 활성화 요청이 아닙니다. 운영 중인 AI 서비스와 보호
환경파일, Backend 제품 활성 플래그 및 RDS 데이터를 변경하지 않고 Readonly
검증 증거만 생성하는 것이 목적입니다.

## 2. 현재 확인 범위

요청자는 EC2에서 다음 두 항목을 확인했다고 보고했습니다.

1. `validate_ai_readonly_runtime.py`를 통한 View 53건·계보·차원·Readonly 권한
   사전검증
2. 일회성 컨테이너에서 `three_model_integration`, 예상 Child 53건,
   `INTEGRATION_VERIFICATION_ONLY` Profile 해석 확인

다만 원시 실행 결과와 SSM Command ID를 독립 대조하지 않았으므로 위 항목은
`CALLER_REPORTED_PASS`이며, 공식 50 Case PASS를 대신하지 않습니다.

현재 Production Runtime Image는 `ai/Dockerfile`의 `runtime` Target을 사용하며
MVP 데이터만 포함합니다. 따라서 실행 중인 AI 컨테이너 또는 EC2 Host에서
아래 명령만 직접 실행하는 방식은 공식 Gate로 인정할 수 없습니다.

```bash
python -m ai.scripts.verify_three_model_readonly_runtime
```

동일 SHA의 `qa` Target 또는 동등한 검증 전용 Image처럼 다음 자산을 모두 가진
실행 환경이 필요합니다.

- `ai/**` 전체
- `data/config/rag/three_model_evaluation_cases.json`
- `data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl`
- 3모델 Canonical Identity와 Index Manifest
- Python `3.13.13` 및 잠금된 Linux 의존성

## 3. 담당별 요청 작업

### 3.1 Infra·CI 담당

1. 승인된 40자리 Release SHA를 입력으로 고정합니다.
2. `ai/Dockerfile`의 `qa` Target 또는 동일 계약의 전용 검증 Image를 빌드합니다.
3. Image를 ECR에 Push하고 실행 시 Tag가 아니라 Digest로 고정합니다.
4. 개인 AWS Key나 직접 SSH가 아니라 기존 GitHub OIDC·SSM 경로를 사용합니다.
5. 승인된 NONPROD EC2에서 일회성 컨테이너로 Gate를 실행합니다.
6. 실행 중인 `ai` 서비스의 재시작·재생성·환경변수 변경을 수행하지 않습니다.
7. 실행 종료 후 일회성 컨테이너를 제거하고 Image Digest와 SSM Command ID만
   비밀값 없는 증거로 보존합니다.

검증 Process에는 보호된 Runtime 경로를 통해 다음 이름만 주입합니다. 값은
Workflow Log, SSM Output 또는 문서에 출력하지 않습니다.

```text
AI_RAG_RUNTIME_PROFILE=three_model_integration
AI_VECTOR_DSN=<protected readonly value>
AI_VECTOR_TABLE_NAME=backend_ai_rag_chunks_v1
AI_EMBEDDING_REVISION=5617a9f61b028005a4858fdac845db406aefb181
```

컨테이너 내부 공식 실행 명령은 다음입니다.

```bash
python -m ai.scripts.verify_three_model_readonly_runtime
```

### 3.2 Backend·DB 담당

실행 대상 RDS가 다음 계약을 만족하는지 읽기 전용으로 확인해 주십시오.

- `backend_ai_rag_chunks_v1` View 53건
- 모델별 `WPUJAC104DWH=15`, `WPUIAC425SNW=19`, `WPUIAC606SNW=19`
- `chunk_id` 고유 53건과 완전한 Lineage 53건
- Embedding Dimension 1024
- AI Role은 승인 View만 `SELECT`
- Base Table SELECT와 모든 DML 및 `public` Schema CREATE 차단

Migration, Seed, Evidence Import, Crosswalk 변경, Grant 우회와 제품 플래그 변경은
이번 요청 범위가 아닙니다. 불일치가 있으면 수정하지 말고 `HOLD`로 회신해
주십시오.

### 3.3 Data·QA 담당

동일 Release SHA, 동일 Image Digest, 동일 RDS 대상에서 결과를 독립 대조하고
다음 오염 지표가 모두 0인지 확인해 주십시오.

- 교차 제품 Evidence Hit
- Parent 직접 Hit
- 미검증 Evidence Hit

후보·로컬 NumPy Dense 결과나 Fake Provider 결과를 실제 pgvector Readonly Gate
PASS로 대체하지 않습니다.

## 4. 정량 완료 조건

공식 실행 결과가 아래 값과 정확히 일치해야 합니다.

```text
status=PASS
activation_scope=INTEGRATION_VERIFICATION_ONLY
public_runtime_activation=HOLD
case_count=50
passed_count=50
positive_group_hit_count=43
negative_no_evidence_count=7
cross_model_hit_count=0
direct_parent_hit_count=0
unverified_evidence_hit_count=0
```

다음 조건도 함께 충족해야 `THREE_MODEL_READONLY_GATE_PASS`로 판정합니다.

- QA Image의 Release SHA가 요청 SHA와 일치
- ECR Image Digest 고정
- Python `3.13.13`
- Index Manifest Version `2.0.0`
- Canonical Child 53건과 Chunk Set Hash 일치
- 실제 `PGVECTOR_QUERY` 실행
- 실행 전후 운영 AI Container ID와 환경 설정 불변
- 실행 전후 RDS Row Count와 권한 불변
- Secret·DSN·질의 원문·Evidence 본문 비노출

## 5. 실패 및 중단 기준

다음 중 하나라도 발생하면 우회하지 말고 `HOLD` 또는 `FAIL`로 종료해 주십시오.

- 전체 평가 데이터가 없는 Runtime Image 사용
- Release SHA 또는 Image Digest 불일치
- 대상 DB·View·Role 식별 불가
- View 53건 또는 모델별 `15/19/19` 불일치
- Manifest·Canonical Identity·Embedding Revision 불일치
- 50 Case 중 1건 이상 실패
- 교차 모델·Parent·미검증 Evidence Hit 발생
- DB 쓰기 권한 또는 Base Table 접근 발견
- Secret이 Log나 SSM Output에 노출될 가능성

실패를 통과시키기 위한 평가 기대값 변경, 테스트 Skip, Runtime 데이터 수동 Mount,
운영 DB 직접 수정과 환경변수 영구 변경은 금지합니다.

## 6. 명시적 비범위

이번 요청으로 다음 항목을 수행하거나 승인한 것으로 간주하지 않습니다.

- Production `AI_RAG_RUNTIME_PROFILE` 영구 변경
- 실행 중인 AI Container 재생성
- IAC425·IAC606 `is_supported_mvp=true` 전환
- 3모델 Public Runtime 활성화
- Provider→AI→Backend 동일 Inquiry E2E
- Backend 저장·Replay와 Web/Mobile 소비 검증
- 독립 QA 최종 승인 또는 PM 활성 결정

Readonly 50 Case PASS 이후 위 항목은 별도 E2E·활성화 요청으로 진행합니다.

## 7. 회신 형식

비밀값 없이 아래 형식으로 회신해 주십시오.

```text
decision=PASS | FAIL | HOLD
release_sha=<40자리 SHA>
qa_image_digest=sha256:<digest>
target_environment=AWS_RDS_NONPROD
ssm_command_id=<id>
python_version=3.13.13
runtime_profile=three_model_integration
index_version=2.0.0
readonly_view_rows=53
model_counts=15/19/19
case_count=50
passed_count=50
positive_group_hit_count=43
negative_no_evidence_count=7
cross_model_hit_count=0
direct_parent_hit_count=0
unverified_evidence_hit_count=0
running_ai_mutated=false
database_mutated=false
secret_exposure=false
blocker_codes=[]
evidence_artifact_sha256=<sanitized result artifact hash>
```

`FAIL` 또는 `HOLD`이면 `blocker_codes`에 실패 단계와 필요한 입력 또는 담당 결정을
추가해 주십시오. 이 회신만으로 Public 활성화를 진행하지 않으며, 윤승혁 PM의 별도
판정 전까지 `public_runtime_activation=HOLD`를 유지합니다.

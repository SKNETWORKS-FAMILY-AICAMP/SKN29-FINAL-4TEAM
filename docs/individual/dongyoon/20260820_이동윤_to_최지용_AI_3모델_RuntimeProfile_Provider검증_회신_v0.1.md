# 이동윤 → 최지용: AI 3모델 Runtime Profile·Provider 검증 회신 v0.1

## 1. 현재 판정

AI 코드 준비는 완료했지만 3모델 Runtime은 아직 `HOLD`다. Public Runtime 활성화로
표시하지 않는다.

- 작업 Branch: `dongyoon`
- 최신 main 동기화 기준:
  `dcbcbf5ad36ecf84ffe4ed640037e4dde1e50350`
- Backend 53건 Importer·Crosswalk 확장 Commit `59258e6d`는 main 이력에 포함됨
- 최지용 Host에서 확인한 View metadata 보완 코드는 현재 원격 main에서 확인되지 않음

## 2. AI 변경

`PipelineRouter`의 고정 `index_manifest.json` 선택을 허용 Profile 방식으로 변경했다.

- 환경변수 이름: `AI_RAG_RUNTIME_PROFILE`
- 기본값: `mvp`
- 3모델 공식 통합검증 값: `three_model_integration`
- `mvp` Manifest: `ai/configs/index_manifest.json`
- 3모델 Manifest: `ai/configs/index_manifest_3model.json`
- 임의 파일 경로나 별칭은 허용하지 않음
- Profile별 Index Version, Child 수, Chunk Set SHA-256, 문서 집합을 불일치 시 차단
- 검색 서비스 Cache Identity에도 Profile과 Manifest Hash를 포함

3모델 정책은 `INTEGRATION_VERIFICATION_ONLY`로만 선택한다. 이때 JAC104·IAC425·
IAC606과 세대 D·IAC425·IAC606, 정확 판매코드 Filter를 사용한다. 기본 `mvp` Process는
계속 JAC104만 허용하며 3모델 Public Runtime 상태는 `HOLD`다.

`verify_local_runtime.py`는 단일 고정 Evidence ID 의존을 제거했다. 선택 Profile의
Canonical Identity 전체를 검증하며, 3모델 Profile에서는 Child 53건과 모델별 Identity
집합을 확인한 뒤 모델별 대표 정상 Case로 Retriever·Provider를 실행한다. 다른 모델의
Canonical ID가 반환되면 실패한다.

최신 main에 들어온 MCP 검색 모듈의 `app.*` Import 때문에 저장소 Root 기준 AI 전체
Unit 수집이 중단되던 문제도 Monorepo 상대 Import 규칙에 맞춰 수정했다.

## 3. 작성자 테스트

- Runtime Profile·Manifest·정책·53 Identity·MCP 표적 테스트:
  `31 passed`
- `pip check`: PASS
- AI 전체 Unit:
  `355 passed / 1 failed / 5 warnings / 7 subtests passed`
- 잔여 실패:
  `test_ai_owned_backend_integration_fixture[F02]`

기존에 전달된 Retry·Fixture 불일치 2건 중 개인정보/Provider 경계 테스트는 수정 후
PASS다. 남은 F02는 정상 검색 결과 0건에서 Fixture가 `retry_count=0`을 기대하지만
Harness가 동일 검색을 한 번 재실행해 실제 `retry_count=1`인 정책 불일치다. 정상
No Evidence를 재시도하지 않고 일시적 연결·Timeout 오류만 1회 재시도하는 권장안에
대한 PM 결정 전에는 Fixture 또는 Harness를 임의 변경하지 않는다.

## 4. 실행환경 확인과 Provider 결과

보호 Loader는 OpenAI Key와 AI Readonly DSN을 현재 Process에 정상 주입했고 Secret
원문은 출력되지 않았다.

이동윤 Host의 실제 Readonly View를 조회한 결과는 다음과 같다.

- View 전체 및 고유 ID: `7 / 7`
- 모델별: `WPUJAC104DWH=7`
- 3모델 검색에 필요한 신규 metadata 3종이 모두 있는 행: `0`
- Runtime Identity: 기존 Index Version `1.0.0`, 기존 7건 Chunk Set

따라서 이 Host는 최지용 Host의 53행·50/50 검증 환경과 아직 동일하지 않다.

같은 보호환경에서 기본 `mvp` Profile의 실제 pgvector·OpenAI Provider 구간은 PASS했다.

- Runtime Profile: `mvp`
- Canonical Identity: `7`
- 검증 모델: `WPUJAC104DWH`
- 공식 Evidence 반환: `5건`
- Provider 모델 계열: `gpt-4.1-mini`
- Prompt Version: `customer_guidance/v2`
- Token 사용 증거: 있음

3모델 Profile은 실제 `index_manifest_3model.json`이 없고 Readonly View가 7행이므로
`BLOCKED`, `INTEGRATION_VERIFICATION_ONLY`, `public_runtime_activation=HOLD`로 종료했다.

## 5. 남은 Blocker와 필요한 입력

1. Backend Import에 실제 사용한 `index_manifest_3model.json` 파일과 SHA-256 전달
2. View metadata 보완 코드 main 병합
3. 이동윤 Host가 사용하는 동일 AI Readonly 환경에 View 53행·모델별 15/19/19와
   `evidence_group_id`, `source_variant_id`, `retrieval_role` 반영
4. PM의 F02 정상 No Evidence Retry 정책 결정
5. 위 조건 반영 후 50 Case Readonly 재검증과 3모델별 실제 Provider 실행

Android Emulator는 AI Runtime·Provider 직접 검증의 선행조건이 아니다. 모바일 설정이
완료된 뒤 구독→문의→AI→해당 모델 Evidence 공동 E2E를 별도 수행한다.

```ini
ai_code_ready=YES
ai_ready=HOLD_THREE_MODEL_RUNTIME_INPUT
manifest_selection=AI_RAG_RUNTIME_PROFILE_ALLOWLIST
three_model_profile=three_model_integration
retrieval_policy=INTEGRATION_VERIFICATION_ONLY
public_runtime_activation=HOLD
targeted_tests=31_PASSED
ai_full_regression=355_PASSED_1_FAILED
retry_fixture_status=HOLD_PM_DECISION_F02
mvp_pgvector_openai_provider=PASS
three_model_pgvector_openai_provider=BLOCKED
remaining_blocker=OFFICIAL_3MODEL_MANIFEST_AND_SAME_HOST_53ROW_VIEW_AND_VIEW_PATCH_MAIN_MERGE_AND_F02_PM_DECISION
```

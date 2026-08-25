# 김은진·윤승혁님께: Web 커밋 중 Data 자동 변경 협업 요청

## 한 줄 요약

Web 작업은 완료됐지만 공용 pre-commit hook이 김은진님 담당 Data 파일을 자동 변경했으므로, 김은진님의 원복 확인과 윤승혁님의 Git Hook 실행 범위 검토가 필요합니다.

## 1. 담당자와 요청 사항

| 이름 | 팀 역할·담당 범위 | 확인을 요청하는 파일 | 요청 내용 |
| --- | --- | --- | --- |
| 김은진 | QA·Data·DevOps, `data/**` 주담당 | `data/processed/metadata/final_dataset_manifest.json` | 자동 변경된 Manifest가 원복 대상인지 확인하고 원복 승인 |
| 이동윤 | AI·RAG, `data/**` 부담당 | 위 Data Manifest | 김은진님 확인 시 필요한 원본·Pipeline 정합성 교차 확인 |
| 윤승혁 | PM·저장소 최상위 공용 설정 주담당 | `.githooks/pre-commit` | Web-only Commit에 Data 변경이 자동 포함되지 않도록 Hook 실행 범위 검토 |
| 한예나 | Web Frontend, `web/**` 주담당 | Web 코드·테스트 12개 | Data·공용 설정은 수정하지 않고 Web Commit 정리와 재검증 수행 |

최지용님은 Backend·DB 담당이지만, 이번 문제는 Backend·DB 코드가 아니라 Data 산출물과 공용 Git Hook에서 발생했으므로 필수 요청 대상이 아닙니다.

## 2. 현재 상태

- 작업 브랜치: `yena`
- 최신 main 기준 SHA: `95c9181804865fa0ee75e1212bdb14ff893083e1`
- 현재 로컬 Commit: `406ffb1e3f9b85803316f02ceb58b9d3cee5f61a`
- 원격 Push: 미실행
- Web 기능·테스트 파일: 정상 커밋됨
- Backend·DB·Migration·Seed: 변경하지 않음

한예나가 Web 파일 12개만 명시적으로 Stage했지만, 공용 pre-commit hook이 Data Pipeline을 실행하고 Data Manifest를 같은 Commit에 자동으로 추가했습니다.

## 3. 김은진님께 요청할 내용

### 확인 파일

- `data/processed/metadata/final_dataset_manifest.json`

### 자동 변경 내용

- 정수기 매뉴얼 PDF 3개 Manifest 항목 삭제
- `retention.raw_policy_files` 값이 `10`에서 `7`로 변경

### 변경 이유

Web 기능 수정 때문이 아니라 `.githooks/pre-commit`이 로컬 Data Pipeline을 자동 실행했기 때문입니다. 현재 PC에 일부 원본 PDF가 없어서 Manifest 재생성 결과가 최신 main과 다르게 나온 것으로 확인됩니다.

### 요청 사항

1. 최신 main의 기존 Manifest를 유지하는 것이 맞는지 확인해 주세요.
2. 유지가 맞다면 현재 미Push Web Commit에서 이 Data 파일 변경만 원복해도 되는지 승인해 주세요.
3. 실제 Data 변경이 필요하다면 김은진님 담당 브랜치에서 원본 파일과 Pipeline 결과를 별도로 검증해 주세요.
4. 필요하면 `data/**` 부담당인 이동윤님과 교차 확인해 주세요.

### 김은진님께 전달할 문구

Web 커밋 과정에서 공용 pre-commit hook이 김은진님 담당 파일인 `data/processed/metadata/final_dataset_manifest.json`을 자동 변경했습니다. 매뉴얼 PDF 3개 항목이 삭제되고 `raw_policy_files`가 10에서 7로 바뀌었으며, 현재 Commit은 아직 Push하지 않았습니다. 최신 main의 Manifest를 유지하는 것이 맞는지 확인해 주시고, 맞다면 이 자동 변경만 원복해도 되는지 승인 부탁드립니다.

## 4. 윤승혁님께 요청할 내용

### 확인 파일

- `.githooks/pre-commit`

### 현재 동작

1. 모든 Commit에서 `python -B data/tools/pipeline.py qa --verify-rebuild` 실행
2. `data/processed/metadata` 전체 자동 Stage
3. `data/processed/validation` 전체 자동 Stage

### 확인이 필요한 이유

- Web 파일만 변경해도 Data 파일이 다시 생성될 수 있습니다.
- 한예나가 선택하지 않은 김은진님 담당 파일이 Web Commit에 자동 포함됩니다.
- 서로 다른 담당 영역이 한 Commit에 섞여 검토와 책임 구분이 어려워집니다.

### 요청 사항

1. Web-only Commit에서는 Data 산출물을 자동 수정·Stage하지 않도록 실행 조건을 검토해 주세요.
2. Data 관련 입력이 변경된 경우에만 Pipeline을 실행하는 경로 조건을 검토해 주세요.
3. 일반 Commit에서는 검증만 수행하고 파일 자동 Stage는 하지 않는 방식도 검토해 주세요.
4. 김은진님과 협의해 공용 Hook 변경 여부를 결정하고, 변경 시 별도 담당 Commit으로 반영해 주세요.

### 윤승혁님께 전달할 문구

윤승혁님 주담당인 저장소 공용 설정 `.githooks/pre-commit`이 모든 Commit에서 Data Pipeline을 실행하고 Data 파일을 자동 Stage하고 있습니다. 이 때문에 Web-only Commit에도 김은진님 담당 Data 변경이 섞였습니다. Data 관련 변경이 있을 때만 실행하거나 자동 Stage를 제거하는 방향을 김은진님과 검토 부탁드립니다. 공용 Hook은 한예나가 직접 수정하지 않겠습니다.

## 5. 담당자 확인 후 한예나가 진행할 작업

1. 김은진님이 원복을 승인하면 현재 미Push Commit에서 해당 Data 파일 변경만 제외
2. Web 파일 12개만 포함된 Commit SHA 재생성
3. 변경 파일 목록을 다시 확인한 뒤 `yena` 브랜치 Push
4. Web Test·Lint·TypeCheck·E2E TypeCheck·Build 결과와 최종 SHA 전달

## 6. 현재 보류 사항

김은진님의 Data Manifest 처리 방향이 확인될 때까지 현재 Commit은 원격에 Push하지 않습니다. 한예나는 `data/**`와 `.githooks/**`를 직접 수정하지 않습니다.

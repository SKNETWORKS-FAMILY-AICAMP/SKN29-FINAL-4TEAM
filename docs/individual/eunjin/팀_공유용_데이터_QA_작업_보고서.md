# WaterCare 데이터·QA 작업 및 파트별 인계 보고서

## 목차

1. [문서 정보](#1-문서-정보)
2. [최신 main 확인과 선별 반영](#2-최신-main-확인과-선별-반영)
3. [완료한 작업](#3-완료한-작업)
4. [검증 결과](#4-검증-결과)
5. [원본 비보관 상태](#5-원본-비보관-상태)
6. [팀 공통 사용 방법](#6-팀-공통-사용-방법)
7. [GitHub 반영 권장 단위](#7-github-반영-권장-단위)
8. [참고 자료 대조와 병합 전 확인](#8-참고-자료-대조와-병합-전-확인)
9. [PM·통합 파트 확인 사항](#9-pm통합-파트-확인-사항)
10. [AI·RAG 파트 확인 사항](#10-airag-파트-확인-사항)
11. [Backend·DB 파트 확인 사항](#11-backenddb-파트-확인-사항)
12. [Web 파트 확인 사항](#12-web-파트-확인-사항)
13. [Mobile 파트 확인 사항](#13-mobile-파트-확인-사항)
14. [파트 공통 최종 체크](#14-파트-공통-최종-체크)
15. [대표 E2E 0.8.0 마이그레이션 결정](#15-대표-e2e-080-마이그레이션-결정)
16. [대표 E2E 마이그레이션 2단계 결과](#16-대표-e2e-마이그레이션-2단계-결과)
17. [대표 E2E 마이그레이션 3단계 결과](#17-대표-e2e-마이그레이션-3단계-결과)
18. [대표 E2E 마이그레이션 4단계 결과](#18-대표-e2e-마이그레이션-4단계-결과)
19. [대표 E2E 마이그레이션 5단계 결과](#19-대표-e2e-마이그레이션-5단계-결과)
20. [대표 E2E 마이그레이션 6단계·0.8.0 릴리스 결과](#20-대표-e2e-마이그레이션-6단계080-릴리스-결과)

## 1. 문서 정보

| 항목 | 내용 |
|---|---|
| 작성자 | 김은진 |
| 기준일 | 2026-07-27 |
| 작업 브랜치 | `eunjin` |
| 계약 버전 | `0.3.0` |
| 데이터 버전 | `0.8.0` |
| MVP 제품 | `WPUJAC104DWH` |
| 공식 문서 | WPU-JAC104D·WPU-JCC104D REV.00 |
| 업무 지침서 | `docs/weekly-task/김은진_3주차_업무_지침서.md` |
| 개인 개발 기록 | 현재 문서 `docs/individual/eunjin/팀_공유용_데이터_QA_작업_보고서.md` |
| Git 상태 | 커밋·푸시 미수행 |

## 2. 최신 main 확인과 선별 반영

확인한 `origin/main`은 `5bae1e3`이고 현재 브랜치와의 공통 분기점은
`0d6a1b3`이다. 공통 분기점 이후 main 변경은 14개 파일이며 구성은 다음과 같다.

- `docs/weekly-task/**`의 팀원별 3주차 업무 지침서 6개
- 개인 산출물 디렉터리용 `.gitkeep` 6개
- 2주차 데일리스크럼 수정 1개
- 2주차 발표 PDF 1개

`contracts/**`와 `data/**`의 main 변경은 0개다. 따라서 데이터 파일이나 계약을
main에서 덮어쓰지 않았다. 대신 최신 업무 지침서에서 아래 항목만 현재 보고서에 반영했다.

- 담당자별 주관 영역과 협업 경계
- 7월 29일 검토 가능 산출물, 7월 30~31일 정합성 검토 원칙
- `contracts/**` 우선, 생성 Fixture 직접 수정 금지, 공개 필드만 노출
- Backend Seed, AI 검색 평가, Web·Mobile Mock 연동에 필요한 데이터 경로

작업 트리에 미커밋 데이터 변경이 많아 merge·rebase·cherry-pick은 하지 않았다.
다른 팀원의 업무 지침서와 발표자료는 중복 복사하지 않았다. 사용자 검토를 거친
김은진 업무 지침서만 `docs/weekly-task/김은진_3주차_업무_지침서.md`에
선별 반영하고, 개인 개발 기록은 현재 보고서 한 파일로 통합했다.

Git 전역 `core.autocrlf=true`가 정식 데이터의 LF를 checkout 시 CRLF로 바꿀 수
있어 Manifest 해시 재현성 위험이 확인되었다. 서비스 영역은 건드리지 않고
`contracts/.gitattributes`와 `data/.gitattributes`에 LF 정책을 추가하고
PDF·이미지는 binary로 지정했다.

## 3. 완료한 작업

### 계약 전환

- 사용 안내 코드를 `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`,
  `PENDING_CONSULTATION` 네 값으로 확정했다.
- `USE_ALLOWED`는 별칭 없이 제거했다.
- 위험도 코드를 `general`, `caution`, `danger`로 통일했다.
- 계약 버전을 `0.2.1`로 갱신하고 변경 이력을 남겼다.

### 공식 데이터와 RAG

- JAC104D 매뉴얼 44쪽과 공식 FAQ 119건을 정규화했다.
- 이미지형 FAQ 중 관련 5건은 OCR 후 사용자 대조 검수를 완료했다.
- 매뉴얼 37~39쪽에서 MVP RAG 청크 7건을 구성했다.
- 근거 레지스트리는 매뉴얼 7건, 조건부 FAQ 1건, 검색 제외 FAQ 1건으로
  총 9건이다.
- IAC425·IAC506·JAC104 S세대·미검증 공통 FAQ는 MVP 검색에서 차단했다.
- IAC425는 REV.02·52쪽 공식 PDF의 크기·해시·표지만 검증했다. 0바이트였던
  확장 페이지·RAG 파일은 삭제했고 실제 processed·RAG 데이터는 후속 생성 예정이다.

### 합성 Fixture

| 데이터 | 건수 |
|---|---:|
| 사용자 | 16 |
| 제품 | 1 |
| 고객 제품 | 12 |
| 구독 | 12 |
| 문의 | 24 |
| 상담 | 16 |
| 방문 | 5 |
| 케어 이력 | 24 |
| 문의 상태 이력 | 110 |
| 감사 이벤트 | 110 |

문의는 8개 주제에 기본·모호·지속/위험 변형을 적용했다. 자가 해결, 추가 정보
수집, 상담 인계, 방문 인계, 위험 전환, 근거 없음 fallback, 재오픈 흐름을 포함한다.
이름은 실제 사람처럼 보이되 정치인·기업인 등 유명 인물과 실제 개인정보를 사용하지 않았다.

### 도구 리팩터링

- 단일 CLI `data/tools/pipeline.py`를 제공했다.
- 기존 `build_step*.py` 6개는 파일당 10줄의 호환 래퍼로 유지했다.
- OCR·RAG·시나리오·상태 규칙을 `data/config/**`로 외부화했다.
- Schema는 `data/schemas/**`, 문서 본문은 `data/templates/**`의 정적 기준본으로 분리했다.
- Python은 총 1,638줄이며 목표 3,500줄 이하를 충족했다.
- 최대 구현 모듈은 361줄, 래퍼 최대는 10줄이다.

## 4. 검증 결과

`python data/tools/pipeline.py qa --verify-rebuild` 기준 결과다.

| 항목 | 결과 |
|---|---|
| 검증 파일 | 28 |
| 검증 레코드 | 646 |
| 오류 | 0 |
| 경고 | 0 |
| 재생성 변경 파일 | 0 |
| 선언형 설정과 정식 출력 drift | 0 |
| 단위 테스트 | 16개 통과 |
| 최종 Manifest 경로 | 108개, 중복 0 |
| Manifest 해시·크기 불일치 | 0 |
| 활성 `USE_ALLOWED` | 0 |
| 개인정보·내부 경로 노출 | 0 |

위험도와 사용 안내 enum은 각각 공통 계약과 데이터 Schema를 교차 비교한다.
대문자 구 위험도 또는 `USE_ALLOWED`가 활성 데이터에 들어오면 검증이 실패한다.

검증 근거:

- `data/processed/validation/latest_qa_summary.json`
- `data/processed/validation/DATA_STATUS_QA.md`
- `data/processed/validation/refactor/latest_equivalence_report.json`
- `data/processed/metadata/final_dataset_manifest.json`

## 5. 원본 비보관 상태

- `data/raw`에는 정책 파일 7개만 남아 있다.
- 공식 PDF·FAQ 원본과 로컬 OCR 이미지는 삭제했다.
- 공식 URL, SHA-256, OCR 전사, 사용자 검수, 삭제 기록은 보존했다.
- `data/.temp`, `data/.work`, `__pycache__`, `.pyc`는 없다.
- 외부 백업 없이 저장소만으로 원문을 재추출하거나 이미지를 로컬 복구할 수 없다.

## 6. 팀 공통 사용 방법

```powershell
python -B -m unittest discover -s data/tools/tests -q
python -B data/tools/pipeline.py build processed
python -B data/tools/pipeline.py build rag
python -B data/tools/pipeline.py build synthetic
python -B data/tools/pipeline.py qa --verify-rebuild
python -B data/tools/pipeline.py inventory
python -B data/tools/pipeline.py finalize
```

서비스별 생성 Fixture를 직접 수정하지 않는다. 변경이 필요하면
`data/config/synthetic/scenarios.json` 또는 `data/config/workflow/state_rules.json`을
수정하고 생성·QA를 다시 실행한다.

위 명령은 Python 3 실행기가 `python`으로 등록된 환경을 전제로 한다. 현재 검수
터미널에서는 `python`이 PATH에 없어 Codex 번들 Python으로 실행했고 테스트와 QA는
통과했다. 팀 개발 환경에서는 프로젝트 Python 또는 컨테이너 실행 경로를 README에
고정해야 한다.

## 7. GitHub 반영 권장 단위

현재 변경은 한 번에 올리기보다 아래 순서로 리뷰하는 편이 안전하다.

1. 계약: `contracts/VERSION`, `contracts/CHANGELOG.md`,
   `contracts/codes/usage-guidance-statuses.yaml`, `contracts/.gitattributes`
2. 선언형 파이프라인: `data/config/**`, `data/schemas/**`,
   `data/templates/**`, `data/tools/**`, `data/.gitattributes`
3. 정식 데이터와 검증 근거: `data/processed/**`, `data/synthetic/**`,
   `data/catalog/**`, `data/README.md`
4. 삭제 정책: 기존 `data/.temp/**`와 raw 원본 삭제, `data/raw/**` 정책 파일
5. 업무 지침서와 개인 기록:
   `docs/weekly-task/김은진_3주차_업무_지침서.md`,
   `docs/individual/eunjin/팀_공유용_데이터_QA_작업_보고서.md`

`.temp` 삭제는 실수로 빠뜨리면 저장소에 폐기 대상 데이터가 남으므로 삭제 변경까지
함께 반영해야 한다. 반대로 main의 `docs/**` 14개는 이미 main에 있으므로 이 브랜치에서
재추가할 필요가 없다.

## 8. 참고 자료 대조와 병합 전 확인

### 공식 원본 대조

Desktop의 `최종 프로젝트 명세, 참고 서류`에 있는 공식 원본을 읽기·해시·시각
대조만 했으며 저장소로 복사하지 않았다.

| 원본 | 확인 결과 | SHA-256 |
|---|---|---|
| JAC104D·JCC104D REV.00 매뉴얼 | 44쪽, MVP 페이지·모델 일치 | `0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C` |
| IAC425 REV.02 매뉴얼 | 52쪽, 후속 확장 원본 무결성만 확인 | `97C027CE75BEC40386307C867DD3983513CB70FAC687F2D2DB6F1167EC9CAEC8` |
| 공식 FAQ 스냅샷 | 119건, Inventory와 일치 | `670C739A69B3ACF811D763FF17F21C53EB661F7BAE1F7D505275B571FF4D3FF8` |

JAC104D 매뉴얼 37~39쪽은 무출수·소음·누수·맛·냄새·저유량·순간온수
안전 청크와 페이지 연결을 다시 확인했다.

### 해결 완료

- 공통 계약·데이터 위험도는 `general/caution/danger`다.
- 사용 안내는 `NORMAL/PARTIAL_STOP/TOTAL_STOP/PENDING_CONSULTATION`이며
  `USE_ALLOWED`는 거부한다.
- 위험도와 사용 안내는 다른 필드이며 서비스별 alias·대소문자 변환을 두지 않는다.
- 합성 데이터는 구 문서의 대표 6건이 아니라 문의 24건을 정식 수량으로 사용한다.
- IAC425 0바이트 확장 파일 2개를 삭제하고 기획·수집·구조 문서에
  `후속 생성 예정`을 표시했다.
- 현재 제품 Fixture는 MVP 제품 1건만 유지한다.

### 외부 참고 자료의 미해결 충돌

Desktop의 7월 24일 Excel과 파생 ERD는 저장소 밖 참고 자료이므로 이번 작업에서
수정하지 않았다. 다음 위치는 Backend Migration 기준으로 사용하면 안 된다.

| 참고 파일·위치 | 남은 구 값 | 필요한 값 |
|---|---|---|
| `00_기술스택_및_DB설계기준.xlsx` `코드값_초안!B38:B40` | `NORMAL/CAUTION/DANGER` | `general/caution/danger` |
| 같은 파일 `코드값_초안!B45` | `USE_ALLOWED` | `NORMAL` |
| `08_support_inquiry.xlsx` `TABLE_SPEC!H25` | 위험도 기본값 `'NORMAL'` | `'general'` |
| 같은 파일 `I26`, `F72` | `USE_ALLOWED` | `NORMAL` |
| 같은 파일 `F59:F60`, `F71` | 대문자 위험도 CHECK | 소문자 CHECK |
| `11_support_symptom_assessment.xlsx` `I17`, `F38:F40`, `F43` | 대문자 위험도 | 소문자 위험도 |
| 같은 파일 `I19`, `F45` | `USE_ALLOWED` | `NORMAL` |

`WaterCare_ERD_계층형_v2.html`과 `WaterCare_ERD_상세.html`도
`support_inquiry.risk_level_code` 기본값이 `'NORMAL'`이다. Excel 수정 후
재생성해야 한다.

Desktop의 프로젝트 구조·업무 지침서는 원본을 `data/raw`에 로컬 보관하는
구 정책을 포함한다. 현재 승인 정책은 외부 백업을 전제로 저장소에는 원본을
보관하지 않는 것이다. 구현 기준은 `data/raw/README.md`와 Manifest다.

### 운영상 제한

공식 원본 비보관은 승인된 정책이지만, 원문 재추출이 필요하면 외부 백업과 보존
해시가 필수다.

현재 루트 Docker Compose, Web Dockerfile·환경변수 예시와 AI·Backend Dockerfile·
환경변수 예시는 0바이트 또는 주석만 있는 자리표시자다. `.github`와 `infra`도
실제 Workflow·배포 설정 없이 `.gitkeep`만 존재한다. 이번 데이터 QA 통과를
서비스 배포 환경 검증 완료로 해석하면 안 된다. 사용자 결정에 따라 이 스캐폴드는
삭제하지 않고 현 상태로 유지했다.

## 9. PM·통합 파트 확인 사항

담당자는 윤승혁이다. 레코드 수만 확인하지 말고 계약 기준본과 서비스 간 코드
일치 여부를 승인해야 한다.

확인할 기준본:

- 계약 버전·변경 이력: `contracts/VERSION`, `contracts/CHANGELOG.md`
- 위험도·사용 안내: `contracts/codes/risk-levels.yaml`,
  `contracts/codes/usage-guidance-statuses.yaml`
- 데이터 상태·처리 명세:
  `data/processed/validation/DATA_STATUS_QA.md`,
  `data/processed/metadata/DATA_PROCESSING_SPEC.md`
- 전체 계보: `data/processed/metadata/final_dataset_manifest.json`
- 업무 규칙: `data/config/workflow/state_rules.json`

확인 체크:

- [ ] 위험도 `general/caution/danger`와 사용 안내 4개 코드를 승인한다.
- [ ] `USE_ALLOWED`가 별칭 없이 폐기됐는지 확인한다.
- [ ] MVP RAG 7건·근거 9건·합성 문의 24건을 공식 수량으로 사용한다.
- [ ] IAC425·IAC506·JAC104 S세대·미검증 FAQ가 MVP 검색에서 차단됐는지 확인한다.
- [ ] IAC425 확장 페이지·RAG가 후속 생성 전까지 완료 산출물로 표시되지 않게 한다.
- [ ] 공식 원본 비보관과 외부 백업 의존성을 운영 위험으로 기록한다.
- [ ] 계약 변경을 서비스 구현보다 먼저 반영하고 생성 Fixture 직접 수정을 차단한다.
- [ ] 8절의 Excel·ERD 충돌을 Backend 문서 갱신 작업으로 관리한다.

금지 사항:

- 서비스별 위험도 대소문자 Mapper나 구 코드 alias 추가
- 위험도 `general`과 사용 안내 `NORMAL`을 같은 코드로 취급
- 데이터 QA 통과를 Docker·CI·배포 검증 완료로 해석

## 10. AI·RAG 파트 확인 사항

담당자는 이동윤이다. 현재 검색 기준은 JAC104D·JCC104D REV.00의 MVP 데이터뿐이다.

바로 사용할 데이터:

- RAG 7건: `data/processed/structured/rag/mvp/rag_verified_sample.jsonl`
- 근거 레지스트리 9건:
  `data/processed/structured/evidence/jac104_evidence_registry.jsonl`
- 매뉴얼 페이지 44건:
  `data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl`
- 검색 평가·오염 차단 결과:
  `data/processed/validation/step3/latest_step3_report.json`
- 합성 문의·기대 결과:
  `data/synthetic/fixtures/inquiries.json`,
  `data/synthetic/expected/evidence_references.json`,
  `data/synthetic/expected/safety_assessments.json`

검색·답변 규칙:

- 37~39쪽의 무출수·저유량·냉수 온도·누수·물맛·냄새·소음·순간온수 안전
  7개 주제만 MVP 검색에 사용한다.
- IAC425·IAC506·JAC104 S세대·미검증 공통 FAQ는 검색 결과에 포함하지 않는다.
- IAC425 processed·RAG 파일은 현재 없다. 52쪽 페이지 추출, 예정 청크 4건의
  시각 검수·Schema·Manifest 등록 후 별도 컬렉션으로 생성한다.
- 근거가 없는 IoT 문의는 가상 근거를 만들지 말고 상담 fallback으로 처리한다.
- 위험 문의는 일반 자가조치보다 사용 제한·상담 안내를 우선한다.
- AI는 문의 상태를 직접 변경하지 않고 제안과 근거만 반환한다.
- 고객 응답에 내부 경로, 전체 원문, 검색 점수, 프롬프트를 포함하지 않는다.
- 생성 JSONL은 직접 수정하지 않고 `data/config/rag/jac104_chunks.json`을 변경한다.

확인 체크:

- [ ] 대표 질의의 정답 문서·페이지가 Top-5에 포함된다.
- [ ] 검색 제외 모델·FAQ의 결과 혼입이 0건이다.
- [ ] 근거 없음 fallback을 검색 실패와 별도 지표로 집계한다.
- [ ] `risk_level`은 소문자 계약을 사용하고 `use_guidance`와 분리한다.
- [ ] RAG 7건·근거 9건·QA 오류·경고 0건을 재현한다.

## 11. Backend·DB 파트 확인 사항

담당자는 최지용이다. Backend Seed의 입력 기준은
`data/synthetic/fixtures/**`이며 제품은 MVP `WPUJAC104DWH` 1건만 사용한다.

적재 규칙:

- 결정적 UUID와 사람이 읽는 `inquiry_number`를 분리한다.
- 공개 UUID·업무 코드를 기준으로 Upsert하여 재적재 중복을 방지한다.
- 사용자·제품·구독·문의·근거 FK를 적재 전에 검증한다.
- 상태 변경에는 `state_version`, `idempotency_key`, `correlation_id`를 보존한다.
- 상태 이력에는 이전·다음 상태, 이벤트, 수행자, 사유, 시각을 함께 저장한다.
- DB는 UTC로 저장하고 API는 계약에 맞는 `+09:00` 시각을 반환한다.
- 상태 변경은 공통 State Machine Service를 사용하고 409 충돌 시 최신 상태·버전·
  허용 행동을 반환한다.
- 생성 Fixture는 직접 수정하지 않고 `data/config/synthetic/scenarios.json`에서
  재생성한다.

계약 확인:

- Serializer·Model·Migration은 위험도 `general/caution/danger`를 사용한다.
- 사용 안내 정상 값은 `NORMAL`이며 `USE_ALLOWED` 입력은 거부한다.
- Desktop Excel·ERD의 구 값은 구현 기준으로 사용하지 않는다.
- IAC425는 후속 확장 전까지 Seed·제품 선택·검색 범위에 추가하지 않는다.

확인 체크:

- [ ] 사용자 16·제품 1·고객 제품 12·구독 12·문의 24건을 적재한다.
- [ ] 상담 16·방문 5·관리 이력 25·후속확인 1·상태 이력 115·감사 이벤트 115건이 일치한다.
- [ ] 동일 Seed를 두 번 적재해도 중복 행이 생기지 않는다.
- [ ] 오래된 `state_version` 요청은 409로 처리한다.
- [ ] 공식 근거 없음·위험 전환·재오픈 상태 흐름을 Fixture 기대값과 대조한다.

## 12. Web 파트 확인 사항

담당자는 한예나다. 화면 Mock은 `data/synthetic/fixtures/**`,
`data/synthetic/expected/**`, `data/synthetic/scenarios/**`를 기준으로 한다.

표시·행동 규칙:

- 문의 상태, 위험도, 담당 주체, `allowed_actions`, `state_version`은 API 값을
  그대로 사용한다.
- 버튼은 `allowed_actions`에 포함된 행동만 노출한다.
- 409 응답 시 최신 상태·버전·허용 행동으로 갱신하고 사용자 입력은 보존한다.
- `inquiry_id`는 Route·API용, `inquiry_number`는 화면용 업무 번호로 구분한다.
- 위험도는 색상뿐 아니라 문구·아이콘·접근성 설명으로 표현한다.
- EvidenceCard에는 문서명·개정·페이지·요약·검증 상태·분류·공식 URL만 표시한다.
- 내부 경로, 원문 전체, 검색 점수, 프롬프트, 내부 해시는 DOM·로그에 남기지 않는다.
- Web 전용 위험도 Mapper를 만들지 않고 알 수 없는 값은 미확인 안전 상태로 처리한다.
- IAC425는 후속 생성 전까지 제품 선택지·근거 카드·검색 결과에 표시하지 않는다.

확인 체크:

- [ ] 정상·추가 입력·위험·근거 없음·부분 실패·409·재오픈 화면을 확인한다.
- [ ] Fixture 필드를 TypeScript 타입에 직접 매핑한다.
- [ ] Web 디렉터리에 Fixture 복사본을 만들어 별도 수정하지 않는다.
- [ ] `+09:00` 시각은 중복 시간대 변환 없이 표시 형식만 변경한다.
- [ ] IAC425 후속 확장을 현재 완료 기능처럼 노출하지 않는다.

## 13. Mobile 파트 확인 사항

담당자는 양정현이다. Android Mock Repository는
`data/synthetic/fixtures/**`, `data/synthetic/expected/**`,
`data/synthetic/scenarios/**`를 변환해 사용하며 원본 JSON을 별도 수정하지 않는다.

표시·행동 규칙:

- 위험·사용 제한·즉시 행동을 일반 해결 안내보다 먼저 표시한다.
- IoT 미지원 문의는 임의 답변 대신 근거 없음·상담 fallback을 표시한다.
- 문의 상태·담당 주체·다음 행동은 Backend 응답을 사용한다.
- `allowed_actions`에 없는 해결·종료 행동을 노출하지 않는다.
- EvidenceCard에는 공개 가능한 문서명·개정·페이지·검증 상태·요약·URL만 표시한다.
- 내부 경로, 전체 원문, 검색 점수, 프롬프트, 내부 해시는 앱에 포함하지 않는다.
- Android 전용 위험도 alias를 만들지 않고 알 수 없는 값은 안전한 오류·상담 상태로
  처리한다.
- IAC425는 후속 생성 전까지 모델 선택지와 EvidenceCard에 노출하지 않는다.

확인 체크:

- [ ] 증상 필수값 오류·무출수 추가 질문·저유량 정상 안내를 확인한다.
- [ ] 누수·순간온수 위험의 사용 제한과 상담 전환을 확인한다.
- [ ] IoT 근거 없음, API 실패·재시도, 409 최신 상태 반영을 확인한다.
- [ ] Fake/Mock Repository와 실제 Repository 교체 지점을 분리한다.
- [ ] 공개 UUID와 `inquiry_number`를 혼용하지 않는다.
- [ ] `+09:00` 시각을 중복 변환하지 않는다.
- [ ] IAC425 후속 확장을 현재 지원 모델처럼 노출하지 않는다.

## 14. 파트 공통 최종 체크

- [ ] 모든 파트가 `contracts/**`를 코드 기준본으로 사용한다.
- [ ] 생성 데이터는 `data/config/**` 변경 후 파이프라인으로 다시 만든다.
- [ ] 위험도와 사용 안내를 서로 다른 필드로 처리한다.
- [ ] 위험·근거 없음·AI 실패·상태 충돌을 서로 다른 흐름으로 처리한다.
- [ ] 외부 공개 응답·화면·로그에 내부 경로·원문 전체·점수·프롬프트·해시를 남기지 않는다.
- [ ] IAC425·IAC506·JAC104 S세대가 MVP 데이터와 UI에 혼입되지 않는다.
- [ ] 단위 테스트 16개, QA 646레코드, 오류·경고 0건을 재현한다.
- [ ] 최종 Manifest 108개 항목의 해시·크기 불일치가 0건이다.
- [ ] Docker·CI·배포 스캐폴드가 아직 실행 가능한 환경이 아님을 공유한다.

## 15. 대표 E2E 0.8.0 마이그레이션 결정

### 15-1. 변경이 필요한 이유

기획서·WBS·화면설계서·3주차 업무 지침서는 대표 E2E를
`SYN-JAC104-002 / DEMO-INQ-002 / 출수량 저하 / 매뉴얼 REV.00 38쪽`으로
고정한다. 현재 합성 데이터의 `SYN-JAC104-002`는 무출수 정보 수집 사례이고
업무 번호는 `INQ-20260701-0002`, 근거는 37쪽이므로 대표 계약과 일치하지 않는다.

화면설계서는 대표 ID뿐 아니라 `SYN-JAC104-001`부터 `SYN-JAC104-006`까지를
각각 무출수, 출수량 저하, 냉수 온도 이상, 누수, 물맛·냄새 이상, 순간온수 이상으로
정의한다. 따라서 002만 덮어쓰거나 001~006을 무출수·저유량 3개 변형으로 재배치하면
003~006의 의미 충돌이 남는다. 0.8.0에서는 24건의 레코드 수와
`8개 주제 × 3개 변형` 구성을 유지하면서 전체 시나리오 ID를 한 번 재정렬한다.

### 15-2. 대표 E2E canonical 계약

| 항목 | 0.8.0 확정값 |
|---|---|
| 시나리오 ID | `SYN-JAC104-002` |
| 화면·업무 문의 번호 | `DEMO-INQ-002` |
| 제품 판매 코드 | `WPUJAC104DWH` |
| 증상 | 출수량 저하 |
| `topic_code` | `symptom_low_flow` |
| 위험도 | `general` |
| 사용 안내 | `NORMAL` |
| 공식 문서 ID | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00` |
| RAG 청크 ID | `RAG-WPUJAC104DWH-LOW-FLOW-001` |
| 근거 ID | `EVD-WPUJAC104DWH-LOW-FLOW-001` |
| 근거 페이지 | `38` |
| 최종 상태 | `RESOLVED` |

화면설계서에 적힌 구형 문서·근거 ID
`MAN-WPU-JAC104D-P38-LOW-FLOW`과 `EVD-JAC104D-MAN-P38-LOW-FLOW`은
현재 데이터 계보를 약화시키므로 데이터에 역반영하지 않는다. 후속 단계에서
화면설계서의 ID를 위 canonical ID로 갱신한다.

### 15-3. 24개 시나리오 ID 재배열표

| 새 ID | 기존 레코드 | 주제 | 변형 | 비고 |
|---|---|---|---|---|
| `SYN-JAC104-001` | 기존 `002` | 무출수 | `AMBIGUOUS` | 화면설계서의 무출수 사례 |
| `SYN-JAC104-002` | 기존 `006` 기반 | 출수량 저하 | `PERSISTENT_OR_RISK` | 대표 E2E로 확장 |
| `SYN-JAC104-003` | 기존 `007` | 냉수 온도 이상 | `CLEAR` | 화면설계서 사례 |
| `SYN-JAC104-004` | 기존 `010` | 누수 | `CLEAR` | 화면설계서 위험 사례 |
| `SYN-JAC104-005` | 기존 `013` | 물맛·냄새 이상 | `CLEAR` | 화면설계서 사례 |
| `SYN-JAC104-006` | 기존 `016` | 순간온수 이상 | `CLEAR` | 화면설계서 위험 사례 |
| `SYN-JAC104-007` | 기존 `001` | 무출수 | `CLEAR` | 잔여 변형 |
| `SYN-JAC104-008` | 기존 `003` | 무출수 | `PERSISTENT_OR_RISK` | 잔여 변형 |
| `SYN-JAC104-009` | 기존 `004` | 출수량 저하 | `CLEAR` | 잔여 변형 |
| `SYN-JAC104-010` | 기존 `005` | 출수량 저하 | `AMBIGUOUS` | 잔여 변형 |
| `SYN-JAC104-011` | 기존 `008` | 냉수 온도 이상 | `AMBIGUOUS` | 잔여 변형 |
| `SYN-JAC104-012` | 기존 `009` | 냉수 온도 이상 | `PERSISTENT_OR_RISK` | 잔여 변형 |
| `SYN-JAC104-013` | 기존 `011` | 누수 | `AMBIGUOUS` | 잔여 변형 |
| `SYN-JAC104-014` | 기존 `012` | 누수 | `PERSISTENT_OR_RISK` | 잔여 변형 |
| `SYN-JAC104-015` | 기존 `014` | 물맛·냄새 이상 | `AMBIGUOUS` | 잔여 변형 |
| `SYN-JAC104-016` | 기존 `015` | 물맛·냄새 이상 | `PERSISTENT_OR_RISK` | 잔여 변형 |
| `SYN-JAC104-017` | 기존 `017` | 순간온수 이상 | `AMBIGUOUS` | ID 유지 |
| `SYN-JAC104-018` | 기존 `018` | 순간온수 이상 | `PERSISTENT_OR_RISK` | ID 유지 |
| `SYN-JAC104-019` | 기존 `019` | 소음 | `CLEAR` | ID 유지 |
| `SYN-JAC104-020` | 기존 `020` | 소음 | `AMBIGUOUS` | ID 유지 |
| `SYN-JAC104-021` | 기존 `021` | 소음 | `PERSISTENT_OR_RISK` | ID 유지 |
| `SYN-JAC104-022` | 기존 `022` | IoT 미지원 | `CLEAR` | ID 유지 |
| `SYN-JAC104-023` | 기존 `023` | IoT 미지원 | `AMBIGUOUS` | ID 유지 |
| `SYN-JAC104-024` | 기존 `024` | IoT 미지원 | `PERSISTENT_OR_RISK` | ID 유지 |

런타임 alias는 두지 않는다. 0.7.2의 ID를 사용하던 팀원이 추적할 수 있도록
위 표를 0.8.0 데이터 변경 이력에도 복사하고, 새 ID를 기준으로 결정적 UUID,
업무 번호, `idempotency_key`, `correlation_id`를 다시 생성한다.

### 15-4. 대표 E2E 상태 전이

| 순서 | 이벤트 | 상태 전이 | 수행 주체 | 검증 의미 |
|---:|---|---|---|---|
| 1 | `START_INQUIRY` | 시작 → `DRAFT` | 고객 | 동일 문의 생성 |
| 2 | `SUBMIT_SYMPTOM` | `DRAFT` → `QUESTIONNAIRE_IN_PROGRESS` | 고객 | 저유량 원문 입력 |
| 3 | `SUBMIT_ANSWERS` | `QUESTIONNAIRE_IN_PROGRESS` 유지 | 고객 | 수전·필터·수압 답변 누적 |
| 4 | `SAFE_GUIDANCE_READY` | `QUESTIONNAIRE_IN_PROGRESS` → `AI_GUIDANCE_READY` | 시스템 | 위험 판정·38쪽 검색·자가확인 안내 |
| 5 | `REQUEST_CONSULTATION` | `AI_GUIDANCE_READY` → `CONSULTATION_PENDING` | 고객 | 자가확인 후 미해결 |
| 6 | `START_CONSULTATION` | `CONSULTATION_PENDING` → `CONSULTATION_IN_PROGRESS` | 배정 상담사 | 상담 시작 |
| 7 | `VISIT_NEEDED` | `CONSULTATION_IN_PROGRESS` → `VISIT_REVIEW_PENDING` | 배정 상담사 | 방문 필요 확정 |
| 8 | `CONFIRM_VISIT` | `VISIT_REVIEW_PENDING` → `VISIT_PENDING` | 배정 상담사 | 방문 일정 확정 |
| 9 | `START_VISIT` | `VISIT_PENDING` → `VISIT_IN_PROGRESS` | 배정 기사 | 방문 시작 |
| 10 | `VISIT_COMPLETED` | `VISIT_IN_PROGRESS` → `COMPLETION_PENDING` | 배정 기사 | 방문 결과·케어 이력 저장 |
| 11 | `SUBMIT_RESOLUTION_FEEDBACK` | `COMPLETION_PENDING` 유지 | 고객 | 해결됨 피드백 저장 |
| 12 | `FINALIZE_INQUIRY` | `COMPLETION_PENDING` → `RESOLVED` | 배정 기사 | 고객 피드백 확인 후 최종 완료 |

현재 `data/config/workflow/state_rules.json`은
`COMPLETION_PENDING`의 고객 행동으로 `SUBMIT_RESOLUTION_FEEDBACK`을 노출하지
않는다. 반면 화면설계서와 API 명세서는 고객 피드백 저장 후 상태를 유지하고,
배정 담당자가 최종 완료하도록 규정한다. 후속 단계에서 이 누락을 보완하되
고객에게 `FINALIZE_INQUIRY` 권한을 주지 않는다.

추가 답변 이벤트도 파이프라인의 `SUBMIT_FOLLOWUP_ANSWER`와
공통 계약·화면설계서의 `SUBMIT_ANSWERS`가 불일치한다. 데이터가 기존 문서를
따르도록 후속 단계에서 파이프라인 값을 `SUBMIT_ANSWERS`로 통일하며,
구 값의 런타임 alias는 두지 않는다.

### 15-5. 버전·호환성·검증 원칙

- 시나리오 ID의 업무 의미와 결정적 UUID가 바뀌므로 데이터 버전은 `0.8.0`으로 올린다.
- `DEMO-INQ-002`를 허용하도록 문의 번호 Schema를 확장하되 기존
  `INQ-YYYYMMDD-NNNN` 형식도 유지한다.
- 24건, 8개 주제, 주제별 3개 변형, 위험·사용 안내 의미와 공식 근거 연결은 유지한다.
- 대표 E2E는 `DEMO-INQ-002` 하나에 고객 입력, 상담, 방문, 케어 이력,
  고객 해결 피드백과 최종 완료를 연결한다.
- 문서·설정·정식 산출물 사이의 대표 ID, 증상, 페이지, 근거 ID, 최종 상태를
  교차 검증하는 테스트를 추가한다.
- 이 절 작성 시점에는 활성 설정·Schema·합성 산출물을 변경하지 않았다.

## 16. 대표 E2E 마이그레이션 2단계 결과

### 16-1. 계약과 선언형 설정 전환

- Inquiry 상태 계약을 API 명세의 canonical 12개 상태로 통일했다.
- 계약 버전을 `0.2.1`에서 `0.3.0`으로 올렸다.
- 데이터 설정 전용 이름 `SUBMIT_FOLLOWUP_ANSWER`를 폐기하고
  `SUBMIT_ANSWERS`로 통일했다.
- `COMPLETION_PENDING`에 고객 행동 `SUBMIT_RESOLUTION_FEEDBACK`을 추가했다.
- 방문 검토·대기 상태에 `UPDATE_VISIT_SCHEDULE`을 추가했다.
- 상담·방문 경로에서 고객 피드백은 상태를 유지하고 snapshot 담당자만
  `FINALIZE_INQUIRY`할 수 있도록 전이·권한·guard를 명시했다.
- `data/config/workflow/state_rules.json`의 설정 버전을 `1.1.0`으로 올렸다.

### 16-2. Schema와 합성 출력

- 문의 번호 Schema가 기존 `INQ-YYYYMMDD-NNNN`과
  `DEMO-INQ-NNN`을 모두 허용하도록 변경됐다.
- `DEMO-INQ-002`는 Schema 검증을 통과하고 `DEMO-002`는 거부된다.
- Workflow 설정 Schema는 12개 상태 키와 허용 행동 enum을 엄격히 검사한다.
- 선언형 합성 설정의 구 이벤트 문자열 24개를 전환했다.
- 상태별 `expected_allowed_actions` 14개 배열을 기준 설정과 다시 동기화했다.
- 합성 출력 22개 파일, 487개 레코드를 다시 생성했다.
- 시나리오 의미·ID·UUID·업무 번호·위험도·사용 안내·근거는 이 단계에서
  변경하지 않았으며 업무 레코드 변경 건수는 0이다.

### 16-3. 검증 결과

| 검사 | 결과 |
|---|---|
| JSON 설정·Schema 문법 | 통과 |
| 계약 상태 | 12개 |
| 계약 이벤트 | 19개 |
| 계약 전이 | 23개 |
| 허용 행동 상태 | 12개 |
| 선언형 설정 Schema 테스트 | 통과 |
| 문의 번호 양성·음성 테스트 | 통과 |
| 상태·이벤트 계약 테스트 | 통과 |
| 전체 단위 테스트 | 18개 통과 |
| 전체 QA | 28개 파일·646개 레코드 |
| 오류·경고 | 0건·0건 |
| 재현성 변경 | 0개 파일 |
| canonical drift | 0개 파일 |
| Manifest 검사 | 108개 항목·불일치 0건 |

Python은 테스트 강화로 1,638줄에서 1,682줄로 44줄 증가했다. 구현 모듈
최대 길이는 361줄, 호환 래퍼 최대 길이는 10줄로 기존 제한을 유지한다.

### 16-4. 보관 상태와 다음 단계

- `data/raw`는 정책 파일 7개만 유지하며 공식 원본은 0개다.
- `data/.temp`, `data/.work`, `__pycache__`는 남기지 않았다.
- 데이터 버전은 아직 `0.7.2`다.
- 실제 `DEMO-INQ-002` 레코드와 24개 시나리오 ID 재배열은 3단계에서 수행한다.
- Git 커밋·스테이징·푸시는 수행하지 않았다.

## 17. 대표 E2E 마이그레이션 3단계 결과

### 17-1. 24개 시나리오와 식별자 재배열

- 15-3의 이전표에 따라 24개 시나리오를 재배열했다.
- 화면설계서의 001~006을 무출수, 출수량 저하, 냉수 온도 이상, 누수,
  물맛·냄새 이상, 순간온수 이상 순서로 맞췄다.
- 001~016의 업무 의미가 이동했고 017~024는 기존 의미를 유지했다.
- 각 새 번호의 고객·구독·기준 시각 슬롯은 유지했다.
- 문의·상담·방문·상태 이력·감사 이벤트 UUID를 새 번호의 UUID v5 seed로
  다시 생성했다.
- 업무 번호, `idempotency_key`, `correlation_id`, 상태 이력 사유와
  모든 FK를 새 ID에 맞춰 갱신했다.
- 사용자 16건, 제품 1건, 고객 제품 12건, 구독 12건과 케어 이력 24건은
  시나리오 재배열의 영향을 받지 않아 그대로 유지했다.

### 17-2. 대표 E2E 현재 상태

| 항목 | 3단계 결과 |
|---|---|
| 시나리오 | `SYN-JAC104-002` |
| 문의 번호 | `DEMO-INQ-002` |
| 원문 | 정수 물줄기가 평소보다 약해졌고 한 컵 받는 시간이 길어졌어요. |
| 주제 | `symptom_low_flow` |
| 변형 | `PERSISTENT_OR_RISK` |
| 위험도 | `general` |
| 사용 안내 | `NORMAL` |
| 근거 | `EVD-WPUJAC104DWH-LOW-FLOW-001` |
| 페이지 | 38쪽 |
| 현재 상태 | `VISIT_PENDING` |
| 현재 상태 이력 | 7건 |

현재 대표 문의는 기존 저유량 방문 인계 흐름을 옮긴 상태다. 4단계에서
`SUBMIT_ANSWERS`, `START_VISIT`, `VISIT_COMPLETED`,
`SUBMIT_RESOLUTION_FEEDBACK`, `FINALIZE_INQUIRY`를 추가해
12단계·`RESOLVED` 흐름으로 완성한다.

### 17-3. 수량과 무결성

| 데이터 | 결과 |
|---|---:|
| 시나리오 | 24 |
| 주제 | 8 |
| 주제별 변형 | 3 |
| 문의 | 24 |
| 상담 | 16 |
| 방문 | 5 |
| 상태 이력 | 110 |
| 감사 이벤트 | 110 |
| 검증한 Workflow Step | 110 |
| 시나리오 부분집합 파일 | 7 |

문의·상담·방문·상태 이력·감사 이벤트의 결정적 UUID 공식, FK,
이벤트·시각·멱등성 키·추적 ID를 상호 대조했으며 중복·누락은 0건이다.
`DEMO-INQ-002`는 1건만 존재하고 기존 `INQ-20260701-0002`는 제거됐다.

### 17-4. 도구 보완과 검증 결과

- 합성 빌드 요약의 `changed_business_records=0` 하드코딩을 제거하고
  전후 `demo_scenarios`를 실제 비교하도록 변경했다.
- 마이그레이션 도중 PowerShell 파이프 인코딩으로 손상된 신규 한글 문자열을
  즉시 발견해 제목·원문·상담 요약·상태 이력 사유를 UTF-8로 복구했다.
- `??` 손상 패턴 재검사 결과는 0건이다.
- `data/catalog/CHANGELOG.md`에 기존 ID→새 ID 이전표를 기록했다.

| 검사 | 결과 |
|---|---|
| 전체 단위 테스트 | 18개 통과 |
| 전체 QA | 28개 파일·646개 레코드 |
| 오류·경고 | 0건·0건 |
| 재현성 변경 | 0개 파일 |
| canonical drift | 0개 파일 |
| Manifest | 108개 항목·불일치 0건 |
| Python | 1,702줄 |
| 최대 구현 모듈 | 361줄 |

### 17-5. 보관·버전 상태

- `data/raw`는 정책 파일 7개, 공식 원본 0개 상태다.
- `data/.temp`, `data/.work`, `__pycache__`는 없다.
- 계약 버전은 `0.3.0`이다.
- 데이터 버전은 최종 교차 검증 전이므로 아직 `0.7.2`다.
- Git 커밋·스테이징·푸시는 수행하지 않았다.

## 18. 대표 E2E 마이그레이션 4단계 결과

### 18-1. 대표 문의의 완결 범위

`SYN-JAC104-002 / DEMO-INQ-002`를 고객 문진부터 최종 해결까지 연결했다.
기존 7단계 방문 예약 상태에 다음 5개 이벤트를 보완했다.

1. `SUBMIT_ANSWERS`
2. `START_VISIT`
3. `VISIT_COMPLETED`
4. `SUBMIT_RESOLUTION_FEEDBACK`
5. `FINALIZE_INQUIRY`

대표 문의의 최종 상태는 `RESOLVED`, `state_version`은 12다. 동일한
12개 이벤트 순서가 기대 Workflow, 문의 상태 이력, 감사 이벤트에 모두
반영됐다.

### 18-2. 상담·방문·후속확인·관리 이력 연결

| 항목 | 대표 데이터 |
|---|---|
| 상담 | `CON-SYN-0002-1` · `VISIT_REQUIRED` · 완료 |
| 방문 | `VIS-SYN-0002` · `COMPLETED` |
| 방문 시작 | `2026-07-04T00:00:00+09:00` |
| 방문 완료 | `2026-07-04T01:00:00+09:00` |
| 후속확인 | 앱 응답 · `RESOLVED` |
| 고객 응답 | 방문 점검 후 출수량 정상화 확인 |
| 최종 확정 | `2026-07-04T03:30:00+09:00` |
| 관리 이력 | `VISIT_SERVICE` · `ISSUE_RESOLVED` |

후속확인은 문의·상담·방문 ID를 모두 참조한다. 관리 이력은 고객 제품,
문의, 방문 ID를 함께 참조하므로 방문 결과를 고객 관리 이력으로
추적할 수 있다. 공식 매뉴얼이 보증하지 않는 고장 원인을 단정하지 않도록
방문 원인과 조치는 합성 기사 점검 결과로만 기록했다.

### 18-3. 수량 변화

| 데이터 | 3단계 | 4단계 |
|---|---:|---:|
| 문의 | 24 | 24 |
| 상담 | 16 | 16 |
| 방문 | 5 | 5 |
| 관리 이력 | 24 | 25 |
| 후속확인 | 0 | 1 |
| 문의 상태 이력 | 110 | 115 |
| 감사 이벤트 | 110 | 115 |
| 대표 Workflow Step | 7 | 12 |

23개 비대표 문의의 업무 의미·ID·수량은 변경하지 않았다.

### 18-4. Schema·QA·재현성

- `syntheticFollowupConfirmation.schema.json`을 추가했다.
- 관리 이력 Schema에 `VISIT_SERVICE`, `ISSUE_RESOLVED`와 선택적
  문의·방문 참조를 추가했다.
- QA에 관리 이력과 후속확인의 FK 검사를 추가했다.
- 단위 테스트 18개가 모두 통과했다.
- 전체 QA는 29개 파일·658개 레코드, 오류 0건·경고 0건이다.
- 선언형 재생성 비교는 32개 파일 모두 바이트 동일이다.
- 최종 Manifest는 111개 항목, 해시 불일치 0건이다.
- `data/raw` 공식 원본 0건, `.temp`·`.work`·`__pycache__` 미존재다.

데이터 버전은 최종 교차 문서 불변식 검사 전이므로 `0.7.2`를 유지한다.
Git 커밋·스테이징·푸시는 수행하지 않았다.

## 19. 대표 E2E 마이그레이션 5단계 결과

### 19-1. 교차 문서 충돌 수정

자동 검사를 작성하기 전에 다음 두 문서 불일치를 먼저 수정했다.

- 화면설계서의 `MAN-WPU-*`, `EVD-JAC104D-MAN-*` 자리표시자를 실제
  `RAG-WPUJAC104DWH-*`, `EVD-WPUJAC104DWH-*` ID로 교체했다.
- 화면설계서의 냉수 온도 이상 위험도를 실제 데이터와 같은 `general`로
  교정하고 순간온수 근거 페이지를 `38~39`로 표시했다.
- 3주차 업무 지침서 산출물 트리에 고객 제품, 후속확인, 문의 상태 이력과
  현재 통합 QA 명령을 반영했다.

### 19-2. 선언형 대표 E2E 계약

`data/config/e2e/representative_contract.json`을 대표 E2E 단일 기준본으로
추가했다. 다음 값을 코드가 아니라 설정으로 관리한다.

- `SYN-JAC104-002 / DEMO-INQ-002`
- `WPUJAC104DWH`
- `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00`
- `RAG-WPUJAC104DWH-LOW-FLOW-001`
- `EVD-WPUJAC104DWH-LOW-FLOW-001`
- 매뉴얼 38쪽
- `general / NORMAL`
- 12개 상태 이벤트와 최종 `RESOLVED`
- Fixture별 기대 수량
- 문서별 검사 섹션과 필수 토큰

### 19-3. 자동 불변식 17개

교차 검사는 다음 범위를 한 번에 확인한다.

1. 지침서·WBS·기획서·화면설계서 지정 섹션의 대표 계약
2. 대표 문의의 유일성과 업무 값
3. 제품·구독·고객 제품 계보
4. RAG 청크·근거·공식 문서·38쪽 연결
5. 기대 Workflow·상태 이력·감사 이벤트의 12단계 순서
6. 상태 전이 계약 포함 여부
7. 상담→방문→후속확인→관리 이력 FK
8. 방문 담당 기사의 최종 완료 권한
9. `correlation_id` 연속성
10. 실제 Fixture와 Manifest 수량

매뉴얼 페이지를 38→37로 바꾸거나 상태 이벤트 순서를 바꾼 음성 테스트도
각각 실패하는 것을 확인했다.

### 19-4. 5단계 검증 결과

| 검사 | 결과 |
|---|---|
| 전체 단위 테스트 | 22개 통과 |
| 대표 E2E 불변식 | 17/17 통과 |
| 검사 문서 | 4개 문서·5개 섹션 |
| 전체 QA | 34개 파일·659개 레코드 |
| 오류·경고 | 0건·0건 |
| 재현성 변경 | 0개 파일 |
| 선언형 동등성 | 32/32파일 바이트 동일 |
| 최종 Manifest | 116개 항목·불일치 0건 |
| Python | 20개 파일·2,146줄 |
| 최대 구현 모듈 | 395줄 |

데이터 버전은 최종 릴리스·Manifest 확정 단계 전이므로 `0.7.2`를 유지한다.
`data/raw`는 정책 파일 7개·공식 원본 0개이며 `.temp`·`.work`·
`__pycache__`는 없다.
Git 커밋·스테이징·푸시는 수행하지 않았다.

## 20. 대표 E2E 마이그레이션 6단계·0.8.0 릴리스 결과

### 20-1. 릴리스 전 불필요 파일·추적 범위 검사

`data/**`의 133개 기존 파일을 Manifest와 대조했다. 임시·백업·로그·
컴파일 캐시는 없었으며 `step3`, `step4`, `latest_*` 보고서는 단계별 승인과
검증 계보이므로 삭제하지 않았다.

대조 과정에서 삭제 대상이 아니라 Manifest 누락인 파일을 발견했다.
`synthetic/scenarios/`의 업무 흐름별 부분집합 7개는 정식 생성 산출물이지만
Dataset Manifest와 카탈로그에 등록되지 않은 상태였다. 전용
`scenarioSubsetItem.schema.json`을 추가하고 다음 7개 파일·37건을 정식
데이터셋으로 편입했다.

- 자가 해결 5건
- 정보 수집 5건
- 상담 인계 14건
- 방문 인계 5건
- 위험 전환 3건
- 근거 없음 fallback 3건
- 재오픈 2건

### 20-2. 최종 Manifest 범위

최종 Manifest는 자기 자신을 제외한 `data/**` 전체를 추적한다.

- 정식 데이터와 시나리오 부분집합
- 카탈로그·설명 문서
- Schema
- 생성·검증 도구와 테스트
- 선언형 설정과 템플릿
- 검증 보고서
- 원본 비보관 정책 파일 7개
- 데이터 `.gitattributes`

Manifest 밖에 남은 파일은 자기 참조 해시를 만들 수 없는
`final_dataset_manifest.json` 자신뿐이다.

### 20-3. 0.8.0 최종 검증

| 검사 | 결과 |
|---|---|
| 데이터 버전 | `0.8.0` |
| 전체 단위 테스트 | 22개 통과 |
| 대표 E2E 불변식 | 17/17 통과 |
| 전체 QA | 41개 파일·696개 레코드 |
| 오류·경고 | 0건·0건 |
| 재현성 변경 | 0개 파일 |
| 선언형 동등성 | 32/32파일 바이트 동일 |
| 최종 Manifest | 133개 항목 |
| Manifest 불일치 | 0건 |
| Python | 20개 파일·2,154줄 |
| 최대 구현 모듈 | 395줄 |
| 최대 호환 래퍼 | 10줄 |

### 20-4. 최종 보관·Git 상태

- `data/raw`: 정책 파일 7개, 공식 PDF·FAQ·이미지 원본 0개
- `data/.temp`, `data/.work`, `__pycache__`: 없음
- 활성 데이터·Schema·설정의 `USE_ALLOWED`: 0건
- 위험도: `general / caution / danger`
- 사용 안내: `NORMAL / PARTIAL_STOP / TOTAL_STOP / PENDING_CONSULTATION`
- Git 커밋·스테이징·푸시: 수행하지 않음

## 21. 팀 전달면 경량화·관할 정리 작업 로그

### 21-1. 작업 결정

데이터 레코드 수는 DB Seed와 RAG 품질 확인에 과하지 않지만, 팀원이
확인해야 하는 파일이 분산되어 적재 대상과 참조 대상을 구분하기 어려웠다.
정식 데이터는 삭제하지 않고 소비자별 Manifest로 전달면만 줄이는 방식으로
정리했다.

`contracts/**`는 김은진 관할이 아니므로 이 PR의 변경을 모두 제거했다.
작업 트리 기준 `contracts/**`는 `origin/main`과 차이가 없다. 데이터 도구도
`contracts/**`를 직접 읽지 않으며, 데이터셋의 상태·분류값은
`dataset_validation_only`와 `pending_owner_confirmation`으로 표시한다.

### 21-2. 처리 로그

| 순서 | 처리 내용 | 결과 |
|---:|---|---|
| 1 | PR 변경 174개를 관할 문서와 재대조 | `contracts/**` 12개 범위 초과 확인 |
| 2 | `contracts/**`를 `origin/main` 기준으로 복구 | 차이 0개 |
| 3 | QA·테스트·대표 E2E의 `contracts/**` 직접 참조 제거 | 활성 참조 0건 |
| 4 | `state_rules.json`을 데이터 전용 `dataset_vocabulary.json`으로 축소 | `allowed_actions` 제거, 서비스 매핑 대기 명시 |
| 5 | 대표 E2E 파일·Schema의 `contract` 명칭을 `case`로 변경 | 데이터 불변식과 서비스 계약 구분 |
| 6 | RAG·DB Smoke·DB Full·QA 전달 프로필 추가 | 프로필 4개 |
| 7 | 파일 경로·역할·레코드 수·크기·SHA-256 Manifest 생성 | 중복 데이터 사본 0개 |
| 8 | 단위·Schema·무결성·재현성·동등성 재검증 | 전체 통과 |

### 21-3. 소비자별 전달 프로필

기준 파일은 `data/config/handoff/consumer_profiles.json`, 생성 결과는
`data/processed/metadata/consumer_handoff_manifest.json`이다.

| 프로필 | 파일 | 기본 범위 | 준비 상태 |
|---|---:|---|---|
| `rag` | 11개 | 검증 RAG 7건 인덱싱, 근거·매뉴얼·FAQ·평가 데이터 참조 | `READY` |
| `db-smoke` | 11개 | 대표 문의 6건과 참조 엔티티, 상태 이력·감사 이벤트 제외 | `READY_FOR_FIELD_MAPPING` |
| `db-full` | 13개 | 문의 24건 전체, 상태 관련 파일은 매핑 후 적재 | `QA_READY_SERVICE_MAPPING_PENDING` |
| `qa` | 6개 | QA 요약·Schema·무결성·품질·Manifest·처리 명세 | `READY` |

RAG 프로필에서 기본 인덱싱 역할 `INGEST`는
`rag_verified_sample.jsonl` 7건 하나뿐이다. FAQ 119건과 후보 20건은
`REFERENCE_ONLY`이며 기본 임베딩 대상이 아니다.

DB Smoke는 `SYN-JAC104-001`부터 `SYN-JAC104-006`까지 6개를 선택한다.
`inquiry_status_histories.json`, `audit_events.json`,
`followup_confirmations.json`과 서비스 State Machine 자동 적용은 제외한다.

### 21-4. 팀 실행 명령

```powershell
python -B data/tools/pipeline.py handoff rag
python -B data/tools/pipeline.py handoff db-smoke
python -B data/tools/pipeline.py handoff db-full
python -B data/tools/pipeline.py handoff qa
```

명령은 데이터를 복제하지 않고 Manifest를 갱신한다. DB 담당자는
`db-smoke`로 필드·FK 적재를 먼저 확인하고, 상태·이벤트 매핑이 확정된 뒤
`db-full`의 `LOAD_AFTER_MAPPING` 파일을 사용한다. RAG 담당자는 `INGEST`
파일만 Vector DB에 넣고 나머지는 출처·평가용으로 사용한다.

### 21-5. 최종 검증

| 검사 | 결과 |
|---|---|
| 단위 테스트 | 26/26 통과 |
| 전체 QA | 42개 파일·697개 레코드 |
| 오류·경고 | 0건·0건 |
| 대표 E2E 데이터 불변식 | 17/17 통과 |
| 재현성 변경 | 0개 파일 |
| 선언형 동등성 | 32/32파일 바이트 동일 |
| 전달 프로필 | 4개·고유 파일 31개 |
| 최종 Manifest | 137개 항목·해시 불일치 0건 |
| Python | 21개 파일·2,240줄 |
| 최대 구현 모듈 | 398줄 |
| `data/.temp`, `data/.work`, `__pycache__` | 없음 |

데이터 버전은 업무 데이터 내용이 바뀌지 않았으므로 `0.8.0`을 유지한다.
서비스 상태·이벤트·공통 코드의 최종 매핑은 윤승혁·최지용 관할 작업에서
확정해야 한다.
## 22. 0.9.0 T-005 정합화·QA 복구 실행 기록

이 절은 0.8.0 당시 기록과 수치를 보존한 채 2026-07-29 현재 결과를 추가한 것이다.

### 22-1. 변경 범위

- 원본 시나리오 24개 보존, 활성 projection 22개
- `SYN-JAC104-012`, `SYN-JAC104-016`의 `BLOCKED_DECISION` 유지
- T-005 통합 상태이력과 Audit 각 125건
- CustomerProfile 12건과 User→Profile→Subscription→Product→Care 추적
- 내부 정수 PK·Public UUID·업무 코드 3계층 분리
- API 멱등성 내부 코드 `IDEMPOTENCY_KEY_REUSE_CONFLICT`와 Public 코드 `DUPLICATE-EVENT-01` 분리
- Backend import crosswalk 추가와 fixture PK 직접 주입 금지
- 미확정 Care mapping의 `BLOCKED_OWNER_CONFIRMATION`·직접 load 제외
- dataset/final/handoff manifest와 상세 QA 리포트 5종의 파이프라인 재생성

### 22-2. 현재 데이터 수치

| 항목 | 0.9.0 |
|---|---:|
| 원본 시나리오 | 24 |
| 활성 Inquiry | 22 |
| CustomerProfile | 12 |
| Consultation | 12 |
| Visit | 4 |
| 통합 상태이력 | 125 |
| Audit | 125 |
| subset | 7파일·33건 |
| API 멱등성 사례 | 3 |

### 22-3. 판정 범위

생성 산출물은 데이터 QA `PASS`까지만 표시한다. PM 상태 계약은 `draft_for_review`이고 Backend import는 실행 검증되지 않았으므로 `service_contracts_used=false`, Service mapping pending, 비-`DB_VERIFIED` 상태를 유지한다. Backend Model·Migration·Service는 이번 변경에 포함하지 않았다.

## 23. State Machine v1.0.0·DB/RAG 후속 개선 기록

이 절은 22절 작성 이후 승인된 State Machine 계약과 최신 외부 진행
상태를 반영한 2026-07-29 당시 기록이다. 과거 0.8.0·0.9.0 실행 기록과
이 절의 당시 수치는 변경하지 않으며, 현재 판정은 24절을 따른다.

### 23-1. 계약·QA

- State Machine `1.0.0/TEAM_APPROVED` source를 데이터 매핑에 고정했다.
- `data-state-crosswalk.yaml`과 대표 14단계 E2E 계약을 추적 source에
  추가했다.
- QA summary에 계약 source commit, 설정 SHA, 오류 분류를 기록한다.
- 데이터 오류, 계약 source drift, 외부 blocker를 별도 분류한다.
- DB handoff는 `BACKEND_RUNTIME_MAPPING_PENDING`으로 표시해 승인 계약과
  실제 Runtime 적재 mapping 상태를 분리한다.

### 23-2. DB·RAG 판정

- Backend DB 적재는 사용자 확인상 성공했다.
- commit·Migration·테이블별 건수·2회 적재 로그가 없으므로 현재 데이터
  판정은 `USER_CONFIRMED_EVIDENCE_PENDING`이며 `DB_VERIFIED`가 아니다.
- RAG는 승인 청크 7건 양성 Case와 범위·출처 차단 부정 Case 5건을
  제공한다. 실제 embedding·Index·Recall@K·MRR 결과는 이동윤 담당자의
  실행 증빙을 기다린다.

### 23-3. 회귀 방지·제출물

- Data 단위 테스트·계약 검증·결정적 rebuild·tracked diff를 실행하는
  Data CI를 추가했다.
- P0 인수 기준과 요구사항–Fixture–Schema–QA 매트릭스를 작성했다.
- 전처리 결과서와 DB·저장소 설계서의 Markdown 기준본을 추가했으며
  외부 증빙이 없는 수치는 pending으로 유지한다.

### 23-4. 최신 실행 결과

| 검사 | 결과 |
|---|---|
| State Machine v1.0.0 계약 검증 | PASS |
| 데이터 단위 테스트 | 55/55 통과 |
| 전체 QA | 48개 파일·740개 레코드 |
| 오류·경고 | 0건·0건 |
| 대표 E2E | 17/17 통과 |
| 결정적 재생성 drift | 0건 |
| 최종 Manifest | 154개 항목 |
| Data CI | Workflow 추가·로컬 동등 명령 통과, 원격 Actions 실행 대기 |

## 24. Crosswalk v2 Data Owner Review

2026-07-30 현재 Crosswalk v2의 Data 소유 변경 19개를 사후 Owner
Review했다. 상세 경로·의미 검토·실행 명령은
[Crosswalk v2 Data Owner Review](20260730_데이터_Owner_Review.md)에
기록했다.

### 24-1. 현재 판정

- Owner Review: `APPROVED`
- 검토 HEAD: `e5cc511189b54060dfafde9215b2cb0799b1bf7a`
- Backend Source: 17/17 Hash 일치
- Fixture Mapping: 12/12, 차단 Mapping 0
- Source Hash 검사: `PASS`, 변경 0
- Data 단위 테스트: 61/61 통과
- QA: 2회 연속 PASS, 오류 0, 경고 0, 대표 E2E 17/17
- 생성물·canonical drift: 0

### 24-2. DB 검증 범위

`DB_FULL_VERIFIED`는 빈 격리 PostgreSQL에서 합성 Handoff `db-full`
프로필 367 Source를 최초 적재하고 같은 입력으로 Replay한 범위다.
T-005 전체 32개 중 구현된 10개 Table과 Handoff용 운영 Table을 사용한
검증이며, 잔여 22개 구현이나 운영 DB·배포 완료를 뜻하지 않는다.

Data Mapping 의미는 변경하지 않았으므로 새 격리 DB 생성 조건은
발생하지 않았다. 최지용은 Owner Review 반환 후 현재 `main` 기준
Backend 397건과 기존 PostgreSQL Import 증거를 재확인한다.

### 24-3. PM 재판정 요청

WBS는 이 검토에서 수정하지 않는다.

- `T-007`: P0 인수 기준과 Case Matrix 증거로 완료 후보
- `T-013`: 합성 Fixture와 격리 PostgreSQL Import 증거로 완료 후보
- `T-012`: 실제 AI 검색·Recall@K·MRR 증거가 없어 진행 중 유지

## 25. JAC104D MVP RAG 실행 증거 확정

24절 이후 이동윤이 RAG 증거 병합 Commit `4adc84d`에 실제
PostgreSQL/pgvector 적재와 검색 결과를 포함하고 Data 적합성 판정을
반환했다. 이번 정합화의 작업 기준 `main`은 `643b23f`다. 23·24절은
당시 판정을 보존하며 현재 RAG 판정은 이 절을 따른다.

### 25-1. 실행 결과

| 항목 | 결과 |
|---|---|
| Canonical dataset | `data/processed/structured/rag/mvp/rag_verified_sample.jsonl` |
| 승인 청크 | 7건, SHA-256 `2BF3582E...4DD0` |
| PostgreSQL·pgvector | 16.14·0.8.6 |
| Embedding | `BAAI/bge-m3`, revision `5617a9f...` |
| Index | exact search, 1024차원, version `1.0.0` |
| 평가 | 12/12 PASS |
| 양성 Recall@5·MRR | `1.0`·`0.8857142857142858` |
| 금지 모델·문서 유입 | 0건 |
| 누수 Case | 기대 청크 5위, MRR `0.2`, P1 품질 후속 |

Data 계약의 `ai_execution`은 `PASS`,
`approval_scope=APPROVED_FOR_MVP_INGEST`로 갱신한다. 실행 결과와
Index Manifest의 경로·SHA·모델 revision·Chunk Set SHA를 Schema와
Data 테스트에서 교차검증한다.

### 25-2. 승인 범위와 후속

승인은 `WPUJAC104DWH`, D세대, 공식 매뉴얼 REV.00 37~39쪽의 7개
증상에 한정한다. 전체 제품군·운영 Vector Store·Backend AI Client
완료를 뜻하지 않는다.

- `TEXT_AND_VISUAL_VERIFIED → official_verified` 의미는 Data·AI가
  동의하되 공통 코드 확정은 윤승혁에게 요청한다.
- 지침서 3.3의 동일 모델 정책 차단 Case와 Case별 Page·Filter·
  수동 검토 결과는 v2 계약으로 분리한다.
- v2는 이동윤의 13개 재실행 전까지
  `DATA_EXPECTATION_READY_AI_REVERIFY_REQUIRED`로 관리한다.
- WBS는 직접 수정하지 않고 `T-012`를 조건부 완료 후보로 PM에게
  재판정 요청한다.

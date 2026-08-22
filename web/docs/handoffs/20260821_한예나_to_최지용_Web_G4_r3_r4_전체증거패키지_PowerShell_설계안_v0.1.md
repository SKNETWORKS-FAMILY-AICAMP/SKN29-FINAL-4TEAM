# Web G4 r3·r4 전체 증거 패키지 PowerShell 설계안

- 작성일: 2026-08-21
- 작성자: 한예나(Web)
- 전달 대상: 최지용(Backend·DB), 김은진(QA)
- 기준 Source SHA: `9ba2b3f6aecf733ad9c601e9ca5d3c90e7d9153b`
- 상태: `DESIGN_ONLY / NOT_IMPLEMENTED / DB_NOT_RERUN`

## 1. 목적

보존된 r3·r4 증거 원본을 다시 실행하거나 수정하지 않고, QA 담당자가 전체
Migration·Snapshot·Replay·409 결과를 독립적으로 재검산할 수 있는 전체 증거
패키지를 만든다.

스크립트는 다음 작업만 수행한다.

1. 기존 r3·r4 Manifest 전체 검증
2. 전체 파일 독립 정제 검사
3. 검증을 통과한 파일의 바이트 동일 복사
4. 전체 증거 ZIP과 패키지 검증 자료 생성

## 2. 실행 금지 범위

이 스크립트는 다음 작업을 실행하지 않는다.

- DB Query 및 DB 연결
- PostgreSQL Container·Volume 시작, 중지, 삭제, 초기화
- Migration·Seed·Fixture 실행
- Backend·Playwright·Django 실행
- r3·r4 원본 수정 또는 덮어쓰기
- 민감정보 발견 파일의 자동 치환 후 통과 처리

민감정보가 발견되면 원본이나 복사본을 수정하지 않고 Fail-closed로 중단한다.
자동 치환을 하지 않는 이유는 파일 내용이 바뀌면 기존 `SHA256SUMS.txt`와
일치하지 않기 때문이다.

## 3. 현재 원본 상태

읽기 전용 사전 확인 결과는 다음과 같다. 이 결과는 패키지 생성 완료를 뜻하지
않으며, 구현될 스크립트가 실행 시점에 다시 독립 검증해야 한다.

| 구분 | Manifest 대상 | 현재 확인 | Manifest 포함 실제 파일 수 |
| --- | ---: | --- | ---: |
| r3 | 8개 | 8/8 존재·Hash 일치 | 9개 |
| r4 | 20개 | 20/20 존재·Hash 일치 | 21개 |
| 합계 | 28개 | 누락·불일치 0건 | 30개 |

기존 정제 검사도 r3·r4 모두 `PASS`, Finding 0건이다.

## 4. 입력 경로와 실행 식별값

### 4.1 입력 경로

```text
web/.runtime/qa-evidence/web-g4-db-r3-r4-20260821-9ba2b3f6/
├─ r3/
│  ├─ Manifest 대상 8개
│  └─ SHA256SUMS.txt
└─ r4/
   ├─ Manifest 대상 20개
   └─ SHA256SUMS.txt
```

### 4.2 식별값

| 구분 | 값 |
| --- | --- |
| Source SHA | `9ba2b3f6aecf733ad9c601e9ca5d3c90e7d9153b` |
| r3 run_id | `web-g4-qa-20260821-8c169e27-r3-01a01c99` |
| r3 inquiry_id | `b221269e-1178-5bab-8cac-d794b55b6a56` |
| r4 run_id | `web-g4-db-r4-20260821-9ba2b3f6-954d3b3d` |
| r4 inquiry_id | `1129ddc4-2cba-570d-b0f7-1a2dd1f35d7e` |

스크립트는 입력 파일의 Context·Snapshot·비교 결과가 위 식별값과 일치하는지
확인한다. 다른 실행의 파일이 하나라도 섞이면 중단한다.

## 5. 제안 스크립트 위치

```text
web/scripts/package-web-g4-db-evidence.ps1
```

웹 담당 범위 안에서 관리하고, DB·Backend·공용 실행 스크립트와 분리한다.

## 6. 출력 구조

```text
web/.runtime/qa-evidence/web-g4-db-r3-r4-full-package-20260821/
├─ sanitized/
│  ├─ r3/
│  │  ├─ 원본 Manifest 대상 8개
│  │  └─ SHA256SUMS.txt
│  ├─ r4/
│  │  ├─ 원본 Manifest 대상 20개
│  │  └─ SHA256SUMS.txt
│  └─ package/
│     ├─ inner-checksum-verification.json
│     ├─ package-redaction-scan.json
│     └─ PACKAGE_SHA256SUMS.txt
├─ web-g4-db-r3-r4-full-sanitized-20260821.zip
├─ web-g4-db-r3-r4-full-sanitized-20260821.zip.sha256
└─ package-summary.json
```

ZIP 내부 파일 수는 33개로 고정한다.

- r3: 증거 8개 + 원본 Manifest 1개
- r4: 증거 20개 + 원본 Manifest 1개
- 패키지 검증 파일 3개

`package-summary.json`은 최종 ZIP 자체의 SHA-256을 기록해야 하므로 ZIP 외부에
둔다. r3·r4 원본 상대경로는 `r3/<파일명>`, `r4/<파일명>` 형태로 보존한다.

## 7. 상세 처리 순서

### 7.1 경로 및 동시 실행 방어

1. `Set-StrictMode -Version Latest`와 `$ErrorActionPreference = 'Stop'`을 사용한다.
2. `$PSScriptRoot`를 기준으로 저장소와 Web 경로를 계산한다.
3. 모든 경로는 `GetFullPath()`와 `-LiteralPath`로 처리한다.
4. 입력과 출력이 서로 다른 경로인지 확인한다.
5. 출력은 정확한 `web/.runtime/qa-evidence/` 아래만 허용한다.
6. Drive Root, 사용자 Home, 저장소 Root, `web/`, `.runtime/` 자체는 출력으로
   허용하지 않는다.
7. Symlink, Junction, Reparse Point, ADS, 절대경로 항목, `..` 경로를 거부한다.
8. 전용 Lock을 사용해 같은 패키징 작업의 동시 실행을 차단한다.
9. 기존 출력 폴더나 동일한 ZIP이 있으면 덮어쓰지 않고 중단한다.

### 7.2 원본 Manifest 검증

1. r3 `SHA256SUMS.txt`가 정확히 8개 대상을 가지는지 확인한다.
2. r4 `SHA256SUMS.txt`가 정확히 20개 대상을 가지는지 확인한다.
3. 각 줄은 `64자리 SHA-256 + 공백 2개 + 상대 파일명` 형식만 허용한다.
4. 중복 파일명과 대소문자만 다른 충돌 파일명을 거부한다.
5. Manifest 대상 전체 파일 존재 여부를 확인한다.
6. r3·r4 폴더에 Manifest에 없는 파일이 있으면 중단한다.
7. 모든 파일의 SHA-256을 다시 계산해 Manifest와 비교한다.
8. 누락·불일치·추가 파일이 모두 0건이어야 다음 단계로 이동한다.

### 7.3 내용 및 계약 검증

다음 결과가 모두 일치해야 한다.

- r3 `evidence_mode=R3_FINAL_ONLY`
- r3 `historical_replay_evidence=NOT_CAPTURED`
- r4 compare `status=PASS`
- Replay 추가 행 0건
- 409 추가 행 0건
- 중복 Consultation 0건
- 중복 Idempotency Scope 0건
- HTTP 409 `STATE-CONFLICT-01`
- Migration 전후 동일
- Schema 전후 동일
- `visits.0005=NOT_APPLIED_P1_HOLD`
- 예상 밖 Pending Migration 0건
- 기존 r3·r4 정제 검사 `PASS`, Finding 0건

r3에는 과거 Replay·Schema 전후 자료를 소급해서 만들거나 PASS로 승격하지 않는다.

### 7.4 독립 정제 검사

원본 30개 파일을 별도로 다시 검사한다.

| 분류 | 검사 항목 |
| --- | --- |
| 인증정보 | Bearer Token, JWT, Access·Refresh Token, Authorization, Cookie |
| 비밀정보 | Password, Secret, API Key, Private Key, DSN |
| 네트워크·환경 | IPv4, IPv6, Windows·Linux·UNC 절대경로 |
| 개인정보 | 이메일, 국내·국제 전화번호, 주민등록번호 형태, 이름·주소·생년월일 필드 |
| 업무 원문 | 상담 기록, 상담 요약, 고객 안내, Raw Text·Answer 문자열 |
| 멱등 정보 | Raw Idempotency-Key 금지, `idempotency_key_sha256`만 허용 |
| 파일 형식 | Strict UTF-8, 허용된 Text 형식, 예상하지 않은 Binary 금지 |

다음 안전 정보는 허용한다.

- 공개 Inquiry·Consultation UUID
- Correlation ID
- SHA-256 값
- `idempotency_key_sha256`
- `access_token_included: false`와 같은 검증용 Boolean
- 원문 존재 여부를 나타내는 Boolean

검출 결과에는 실제 값이나 일치한 문장을 기록하지 않는다. 상대 파일명,
Finding Rule, 건수만 기록한다.

### 7.5 별도 정제 폴더 생성

모든 원본 검증이 끝난 후에만 새 `sanitized/` 폴더를 만든다.

1. Manifest 대상 28개와 원본 Manifest 2개를 바이트 그대로 복사한다.
2. 복사 전후 SHA-256을 다시 비교한다.
3. 원본 전체 Hash를 실행 전후 비교해 작업 중 변경 여부를 확인한다.
4. Source 또는 복사본이 바뀌었으면 중단한다.
5. `inner-checksum-verification.json`에 r3 8/8, r4 20/20 결과를 기록한다.
6. 복사본과 검증 파일을 다시 정제 검사한다.
7. `package-redaction-scan.json`에는 PASS·파일 수·Finding 0건만 기록한다.
8. `PACKAGE_SHA256SUMS.txt`에는 패키지의 모든 파일을 이름순으로 기록하고,
   자기 자신은 제외한다.

### 7.6 ZIP 생성과 재검증

1. `.NET System.IO.Compression`으로 ZIP을 새로 생성한다.
2. Entry는 `/` 구분자와 정렬된 순서를 사용한다.
3. ZIP을 닫은 뒤 다시 열어 Entry가 정확히 33개인지 확인한다.
4. 중복, 대소문자 충돌, 절대경로, `..`, ADS, Backslash Entry를 거부한다.
5. ZIP Entry별 SHA-256을 `PACKAGE_SHA256SUMS.txt`와 비교한다.
6. ZIP 내부 전체 파일을 다시 정제 검사한다.
7. 모든 검증 후에만 최종 이름으로 승격한다.
8. ZIP SHA-256을 계산해 `.zip.sha256`과 `package-summary.json`에 기록한다.

## 8. Fail-closed 조건

다음 중 하나라도 발생하면 최종 ZIP·ZIP Hash·PASS 요약을 생성하지 않는다.

- Manifest 개수가 r3 8개·r4 20개와 다름
- Manifest 문법 오류 또는 중복 경로
- 파일 누락 또는 예상하지 않은 추가 파일
- 원본·복사본·ZIP Hash 불일치
- 실행 중 원본 변경
- Symlink·Junction·경로 이탈 발견
- 민감정보 후보 1건 이상
- JSON 파싱 실패 또는 UTF-8 오류
- 실행 식별값 혼합
- Migration·Schema·r4 compare 계약 불일치
- ZIP Entry 누락·추가·중복
- 기존 출력 폴더 또는 ZIP 존재
- 패키지 검증 중 예상하지 않은 오류

실패 시 콘솔에는 다음처럼 고정 오류 코드와 상대경로만 출력한다.

```text
PACKAGE_STATUS=FAIL
ERROR_CODE=SENSITIVE_CONTENT
RELATIVE_FILE=r4/<파일명>
FINDING_RULE=JWT
```

다음 내용은 출력하지 않는다.

- 일치한 원문 또는 Secret 값
- 환경변수와 DB 접속정보
- 사용자명과 로컬 절대경로
- PowerShell 예외 메시지 원문
- Stack Trace와 Transcript

## 9. package-summary.json 항목

```text
status
source_ref
r3_run_id
r3_inquiry_id
r4_run_id
r4_inquiry_id
r3_manifest_target_count
r4_manifest_target_count
source_file_count
missing_count
hash_mismatch_count
unexpected_file_count
sensitive_finding_count
migration_status
schema_status
r4_compare_status
source_unchanged
original_files_modified
db_accessed
secret_values_printed
zip_entry_count
zip_size_bytes
zip_sha256
generated_at_utc
```

안전 상태는 다음 값으로 기록한다.

```json
{
  "original_files_modified": false,
  "db_accessed": false,
  "secret_values_printed": false
}
```

## 10. 실행 명령

### 10.1 읽기 전용 사전 검사

```powershell
pwsh -NoLogo -NoProfile -NonInteractive `
  -File ".\web\scripts\package-web-g4-db-evidence.ps1" `
  -InputRoot ".\web\.runtime\qa-evidence\web-g4-db-r3-r4-20260821-9ba2b3f6" `
  -OutputRoot ".\web\.runtime\qa-evidence\web-g4-db-r3-r4-full-package-20260821" `
  -ExpectedSourceRef "9ba2b3f6aecf733ad9c601e9ca5d3c90e7d9153b" `
  -ValidateOnly
```

### 10.2 검증 통과 후 패키지 생성

```powershell
pwsh -NoLogo -NoProfile -NonInteractive `
  -File ".\web\scripts\package-web-g4-db-evidence.ps1" `
  -InputRoot ".\web\.runtime\qa-evidence\web-g4-db-r3-r4-20260821-9ba2b3f6" `
  -OutputRoot ".\web\.runtime\qa-evidence\web-g4-db-r3-r4-full-package-20260821" `
  -ExpectedSourceRef "9ba2b3f6aecf733ad9c601e9ca5d3c90e7d9153b"
```

## 11. 최종 산출물

구현과 실행이 승인되면 다음 자료를 전달한다.

1. `web/scripts/package-web-g4-db-evidence.ps1`
2. `web-g4-db-r3-r4-full-sanitized-20260821.zip`
3. `web-g4-db-r3-r4-full-sanitized-20260821.zip.sha256`
4. `package-summary.json`
5. 별도 `sanitized/` 검증 복사본

## 12. 현재 상태

이 문서는 설계 검토용이다.

- PowerShell 스크립트: 미구현
- 전체 정제 출력 폴더: 미생성
- 전체 ZIP: 미생성
- DB·Migration·Seed·Playwright 재실행: 0건
- r3·r4 원본 변경: 0건

## 13. 전달용 핵심 요약

기존 r3·r4 원본은 다시 실행하거나 수정하지 않고, 보존 파일 전체를 대상으로
Manifest 28건 재검산·민감정보 검사·복사본 Hash 재검증·ZIP 내부 재검증을
수행하는 PowerShell 패키징 설계안이다. 하나라도 누락·Hash 불일치·민감정보가
발견되면 최종 ZIP을 만들지 않는 Fail-closed 방식이며, 승인 후에만 스크립트와
전체 패키지를 생성한다.

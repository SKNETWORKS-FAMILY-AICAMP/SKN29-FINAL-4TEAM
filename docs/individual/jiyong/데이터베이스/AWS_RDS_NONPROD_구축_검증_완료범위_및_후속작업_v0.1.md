# AWS RDS NONPROD 구축·검증 완료 범위 및 후속 작업

> 작성일: 2026-08-18 KST  
> 작성자: 최지용(Backend·Database)  
> 대상: WaterBridge AWS RDS NONPROD  
> 비밀정보·RDS Endpoint·Password·DSN은 기록하지 않는다.

## 1. 결론

RDS의 **기반 구축과 현재 데이터 기준선 이관은 완료**됐다.

```text
rds_core_status=READY
rds_data_baseline=READY_AT_31F7340
public_backend_to_rds=PASS
latest_main_full_runtime_smoke=PENDING
full_web_mobile_ai_e2e=PENDING
```

따라서 다음 두 문장을 구분해야 한다.

- `RDS 자체를 Web·Mobile Backend가 사용할 수 있는가?` → **예**
- `최신 main의 Web·Mobile·AI 전체 E2E가 최종 완료됐는가?` → **아니오**

RDS를 다시 처음부터 만들 필요는 없다. 이후에는 최신 코드 반영, 신규 Inquiry
관통 E2E, 운영 점검을 같은 RDS에서 이어간다.

## 2. 현재 구성

```text
Android·Browser
    ↓ HTTPS 443
Nginx on EC2
    ├─ Web 정적 파일
    └─ Django Backend
           ↓ TLS verify-full
AWS Managed RDS PostgreSQL·pgvector
```

- PostgreSQL은 EC2 내부 설치형 DB가 아니다.
- EC2는 Web·Backend 실행 Host이며 DB는 별도 AWS 관리형 RDS다.
- RDS는 Private Endpoint를 사용하고 Backend에서만 연결한다.
- Public Internet에 PostgreSQL 5432를 직접 공개하지 않는다.

## 3. 코드 기준선

| 구분 | Commit | 판정 |
|---|---|---|
| RDS 구축·복원·검증 기준 | `31f73405568637ae545d7f38d635f7a920ec9510` | 실제 적용 기준 |
| 확인 시점 최신 `origin/main` | `35ef876ed97298886864eebce51c5642d9dd4d6b` | 후속 배포 기준 |

두 Commit 사이에는 Web·Mobile·AI를 포함해 50개 파일이 변경됐으나, DB Migration
추가는 확인되지 않았다. 따라서 지금 즉시 RDS Schema를 다시 변경할 필요는 없지만,
실제 최신 배포 직전에는 Migration Plan을 다시 확인한다.

## 4. 완료한 RDS 작업

### 4.1 RDS·Extension

| 항목 | 결과 |
|---|---|
| 환경 | `AWS_RDS_NONPROD` |
| Region | `ap-northeast-2` |
| Database | `waterbridge_team_integration` |
| PostgreSQL | `16.14` |
| pgvector | `0.8.2` 설치·조회 PASS |
| DB TLS | `verify-full`, TLS 1.3 확인 |
| EC2 → RDS TCP | PASS |

### 4.2 전용 Role

| Role | 용도 | 상태 |
|---|---|---|
| `waterbridge_ti_migrator` | Migration·Schema 관리 | 생성·접속 PASS |
| `waterbridge_ti_runtime` | Django Runtime CRUD | 생성·현재 Backend 연결 PASS |
| `waterbridge_ti_readonly` | QA 읽기 전용 | 생성·Read-only PASS |
| `waterbridge_ti_ai_readonly` | AI 승인 View 전용 | 생성·Read-only PASS |

- Runtime과 AI Readonly Credential을 분리했다.
- Role Password는 Git·문서·채팅에 기록하지 않았다.
- Secret은 Git 제외·접근 제한 Runtime 파일로만 관리한다.

### 4.3 Schema·Migration

| 항목 | 결과 |
|---|---|
| Public Table | 52개 |
| 적용 Migration | 85개 |
| 원본·RDS Table Set | 일치 |
| 원본·RDS Migration Set | 일치 |
| `visits.0005` | `NOT_APPLIED_P1_HOLD` |

`visits.0005_replace_visit_result_assignment_fk`는 오류 때문에 빠진 것이 아니다.
방문기사 Runtime이 P1 HOLD이므로 기존 결정에 따라 의도적으로 적용하지 않았다.

### 4.4 데이터 이관

- PostgreSQL 16 호환 Dump로 Single Transaction Restore를 완료했다.
- Restore Exit Code는 0이다.
- 원본과 RDS의 비-Evidence Table Row Count가 일치한다.
- 예상하지 않은 Row Delta는 없다.
- Dump 원문은 EC2에 남기지 않았다.

### 4.5 공식 Evidence·pgvector

| 항목 | 결과 |
|---|---|
| 공식 DocumentChunk | 7건 |
| Embedding | 7건 |
| Crosswalk | 7건 |
| Crosswalk Page Link | 8건 |
| AI Readonly View | 7행 |
| Vector Dimension | 전부 1024 |
| Exact Cosine Self Match | PASS |
| `vector_dims` 명시 Cast Constraint | PASS |
| `full_clean()` DB Warning | 0건 |

### 4.6 Backend → RDS HTTP Smoke

다음 실제 PostgreSQL Runtime 요청이 모두 HTTP 200이었다.

- Health
- 고객·상담사 Demo Login
- 고객·상담사 `/me`
- 고객 구독 조회
- 고객 최신 진행 문의 조회
- 상담사 문의 목록 조회

Token·Password·전체 응답 원문은 증거에 남기지 않았다.

### 4.7 공개 HTTPS

| 항목 | 결과 |
|---|---|
| `http://waterbridge.site` | HTTPS로 301 전환 |
| `https://waterbridge.site` | 200 |
| `https://waterbridge.site/health` | 200 |
| Nginx | Active·설정 검사 PASS |
| 인증서 | Let’s Encrypt ECDSA |
| 만료일 | 2026-11-16 |
| 자동 갱신 Timer | Enabled·Active |

공개 HTTPS는 RDS TLS와 별도다. 브라우저↔EC2는 Let’s Encrypt 인증서,
Backend↔RDS는 AWS RDS CA와 `verify-full`을 사용한다.

## 5. 증거 파일

검증 당시 분리 Worktree의 `backend/.runtime/rds-migration/` 아래에 다음
로컬 증거를 남겼다.

- `rds_provision_verify.json`
- `rds_restore_result.json`
- `rds_restored_state_verify.json`
- `source_rds_row_count_comparison.json`
- `rds_backend_http_smoke.json`
- `rds_pgvector_runtime_verify.json`

위 `.runtime` 파일은 Git 제외 로컬 증거다. Secret은 포함하지 않지만 Git 배포
산출물로 간주하지 않는다. 독립 재검증 시에는 이 문서의 기대값을 복사하지 말고
새 실행 결과를 별도 증거 경로에 남긴다.

## 6. 아직 남은 후속 작업

### 6.1 최신 main Runtime 재배포

1. 배포 시점의 최신 main을 고정한다.
2. 현재 RDS 기준선과 Migration Plan을 비교한다.
3. 새 Migration이 없으면 RDS Schema를 변경하지 않는다.
4. 승인된 Migration이 생겼을 때만 Migrator Role로 적용한다.
5. Backend·Web·Mobile·AI Runtime을 같은 기준으로 다시 Smoke한다.

현재 `31f7340 → 35ef876` 사이에는 DB Migration 추가가 없으므로, 최신 코드 재배포와
소비자 Smoke가 중심이다.

### 6.2 신규 Inquiry 전체 관통 E2E

```text
Mobile 신규 문의 생성
→ Backend가 RDS에 저장
→ 실제 AI·RAG 실행 및 Evidence 저장
→ 상담 요청
→ Web 상담사 조회·상담 처리
→ RDS 상태·상담 기록 저장
→ Mobile 최신 Snapshot 재조회
```

기존 Inquiry 재조회나 Unit Test만으로 전체 E2E PASS를 선언하지 않는다.

### 6.3 AI·RAG 확정 후 재검증

- 최종 Model·Agent·Embedding 정책이 확정되면 실제 Provider로 실행한다.
- AI는 `waterbridge_ti_ai_readonly`로 승인 View만 읽는다.
- AIRun·Guidance·Evidence·Correlation 저장을 확인한다.
- AI Model 변경에 따른 데이터 CRUD는 새 Migration 또는 승인 Import 절차로 누적한다.

### 6.4 운영 점검

- RDS 자동 Backup Retention·Snapshot 정책 확인
- 장애 시 Restore 절차 1회 재현
- DB Connection·Storage·CPU Alarm 확인
- Certbot 갱신 상태 주기 확인
- 작업 종료 후 불필요한 SSH `/32` 규칙 정리

### 6.5 CI/CD·GitHub 배포 자동화 인계 범위

김은진(QA·DevOps)은 이 문서를 기준선으로 삼되, 배포 시점 최신 `main`을 다시
확인하고 다음 자동화·운영 Gate를 구축한다.

1. GitHub Actions에서 Backend 표적 Test와 Web Build를 먼저 실행한다.
2. 승인된 `main`만 EC2 배포 대상으로 사용하고, 실패한 Workflow는 배포하지 않는다.
3. Web 정적 Release 교체와 Backend Service 재시작을 재현 가능한 배포 절차로 만든다.
4. 배포 Secret·PEM·RDS Credential은 GitHub Secrets 또는 EC2 보호 Runtime 환경으로만
   주입하며 Workflow Log에 원문을 출력하지 않는다.
5. Migration은 자동 전체 적용하지 않는다. 배포 전 Plan을 확인하고 승인된 항목만
   Migrator Role로 적용하며 `visits.0005`는 P1 HOLD에서 제외한다.
6. 배포 후 Nginx 설정, HTTPS Redirect, `/health`, Demo Login, 고객·상담사 핵심 조회를
   Smoke하고 실패 시 이전 Release로 되돌릴 수 있게 한다.
7. Certbot 자동 갱신, RDS Backup·Storage·Connection, Backend Service 상태를 운영
   점검 대상으로 둔다.
8. 자동화 결과와 남은 Blocker를 최지용(Backend·DB)과 윤승혁(PM)에게 공유한다.

이 인계는 이미 완료된 RDS를 다시 만드는 요청이 아니다. 최신 코드의 반복 가능한
배포·검증·복구 경로를 만드는 작업이다.

### 6.6 최종 Gate

- Fresh Inquiry 전체 관통 결과
- 동일 Inquiry ID·Correlation ID·RDS Row 대조
- Web·Mobile Mock/Fake 자동 성공 없음
- 독립 QA 결과
- 윤승혁(PM)의 최종 E2E·WBS 판정

## 7. 최종 판정

```ini
rds_managed_service=AWS_RDS
rds_core_provision=PASS
rds_tls=VERIFY_FULL_PASS
rds_schema_baseline=PASS
rds_data_restore=PASS
rds_roles=PASS
rds_pgvector=PASS
rds_evidence_baseline=PASS
backend_rds_smoke=PASS
visits_0005=P1_HOLD_EXCLUDED
latest_main_schema_change=NONE_AS_OF_35EF876
latest_main_runtime_redeploy=PENDING
fresh_full_e2e=PENDING
overall=RDS_CORE_READY_FULL_E2E_PENDING
```

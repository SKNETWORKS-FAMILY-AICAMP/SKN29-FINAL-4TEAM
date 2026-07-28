# 정수기 딜러

<p align="center">
  <img src="assets/water-purifier-dealer.png" alt="정수기 딜러 - AI 상담·맞춤 케어" width="720">
</p>

<p align="center">
  <strong>SKN29-FINAL-4TEAM</strong><br>
  정수기 구독 고객 케어 및 A/S 업무 지원 시스템
</p>

## 프로젝트 소개

SK매직 정수기 구독 고객의 고객케어·상담·A/S 업무를 지원하는 다중 에이전트 프로젝트입니다. 고객의 문의 접수부터 AI 상담, 상담사와 방문기사 인계, 처리 후 고객의 해결 여부 확인까지 이어지는 서비스 흐름을 구축합니다.

## 프로토타입

[워터케어 ONE 정수기 고객케어·A/S 프로토타입](https://github.com/antisdream/water_purifier_prototype)은 고객의 증상 입력부터 상담, 방문 점검, 작업 결과·서명, 해결 확인과 운영 감사 이력까지 동일한 문의 ID로 연결해 체험하는 정적 HTML 프로토타입입니다. 고객용 포털과 상담사·방문기사·운영 담당자용 통합 업무 포털로 구성됩니다.

현재 프로토타입은 실제 운영 서비스가 아니라 가상 데이터와 브라우저 로컬 상태로 업무 흐름을 검증하는 단계입니다. 실제 AI/RAG, 사내 API, 서버 인증·DB와 외부 알림은 아직 연동하지 않았습니다.

## Backend·PostgreSQL 로컬 실행

최지용 담당 Django·PostgreSQL 기준선은
[Backend README](backend/README.md)에 정리되어 있습니다. 로컬 실행은
다음 순서를 따릅니다.

> [!IMPORTANT]
> 현행 실행·Migration 기준은 `backend/**`, 기계 계약 기준은
> `contracts/**`입니다. 루트의 `WaterCareBackend/**`와 이를 호출하는
> `RUN_WATERCARE_MIGRATION_FIXED.bat`, `FIX_MIGRATIONS_AND_START.bat`는
> 구형 Android 연동 starter 참고본이며 현행 API·DB·State 계약이나
> 실행 절차의 기준으로 사용하지 않습니다.

### 새 PC 최초 실행

```powershell
Copy-Item .\backend\.env.example .\backend\.env
# backend/.env의 replace-with-* 두 값을 로컬 난수값으로 교체

python .\scripts\development\bootstrap.py --service backend

docker compose --env-file .\backend\.env up -d postgres

Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo_accounts
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

### 설치 완료 후 일상 실행

`.env`와 `backend/.venv`가 이미 준비된 PC에서는 복사·설치·Seed를
반복하지 않고 저장소 루트에서 다음 순서만 실행합니다.

```powershell
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres

python .\scripts\development\check_environment.py `
  --service backend `
  --postgresql

Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

미적용 Migration이 있을 때만 `manage.py migrate --noinput`을 실행하고,
Demo Seed가 변경되거나 새 DB를 만든 경우에만 `seed_demo_accounts`를
실행합니다. Django 서버는 해당 터미널에서 `Ctrl+C`로 종료하며,
PostgreSQL은 저장소 루트에서 다음 명령으로 데이터를 보존한 채
중지합니다.

```powershell
docker compose --env-file .\backend\.env stop postgres
```

다른 PowerShell에서 Token을 출력하지 않는 Health·Auth Smoke를
실행합니다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe ..\scripts\smoke\check_backend_auth.py
```

실제 `.env`, `.venv`, Runtime 로그와 PostgreSQL Volume은 Git에
공유하지 않습니다.

Backend 기준 Python은 `backend/.python-version`의 `3.13.13`입니다.
VS Code는 저장소를 열면 `backend/.venv`를 기본 Interpreter로 선택하고
빠른 환경 검증 Task를 실행합니다. 새 PC에서 `.venv`가 아직 없다면
Python 3.13.13을 준비한 뒤 `Backend: 환경 최초 생성·동기화` Task 또는
위 bootstrap 명령을 한 번 실행합니다. 자세한 재현·복구 절차는
[Backend 가상환경 재현 가이드](docs/individual/jiyong/technical/backend/backend_venv_reproducibility_guide.md)를
따릅니다.

## 작업 산출물

2026-07-22 기준 프로젝트 기획, 데이터 수집·가공, 사용자별 화면·업무 흐름을 정리한 현재 단계의 주간 산출물입니다.

- [프로젝트 기획서](docs/planning/etc/기획서.docx) — 프로젝트 범위와 대표 시나리오, 문제 정의, 시장·BM 분석, 시스템 구성과 검증 방향을 정리했습니다.
- [수집 데이터 보고서](docs/planning/etc/수집데이터보고서.docx) — MVP·후속 확장 대상의 공식 매뉴얼·FAQ 수집, 자동화 절차, 저장 포맷, 법적·윤리적 검토와 품질 관리 방안을 정리했습니다.
- [화면설계서](docs/planning/etc/화면설계서.docx) — 고객·상담사·방문기사·운영 담당자의 화면 목록과 업무 인계 흐름, 상태·권한 정책, 주요 와이어프레임을 정리했습니다.

## 팀원별 역할 분담

> [!IMPORTANT]
> 아래 역할 분담은 **2026-07-23 최종 확정본**입니다.

최종 역할은 서비스 구현에 필요한 6개 담당 영역을 기준으로 구분했습니다. 각 담당자는 주 담당 업무를 중심으로 협업하며, 통합과 문제 해결이 필요한 경우 역할 간 공동 작업을 진행합니다. WBS의 작업 수와 공수는 기능 영역 기준이며 개인별 배분 수치는 아닙니다.

| 담당자 | 역할 | 설명 및 주요 업무 |
| :---: | --- | --- |
| 윤&#8288;승&#8288;혁 | **PM·기술 통합 담당**<br>PM / Technical Coordinator | 프로젝트의 일정과 개발 범위를 관리하고, 각 담당자의 결과물이 하나의 서비스로 연결되도록 조율합니다.<br><br>**주요 업무**<br>• 전체 일정과 우선순위 관리<br>• 기능 범위 및 변경 사항 정리<br>• 프론트엔드·백엔드·AI 간 협업 조정<br>• API 명세와 공통 개발 규칙 관리<br>• 통합 테스트, 배포, 발표 준비 총괄<br>• 필요 시 공통 기능 개발 및 오류 해결 지원 |
| 양&#8288;정&#8288;현 | **모바일 앱 개발 담당**<br>Mobile Application Developer | 고객과 방문기사가 사용하는 모바일·태블릿 애플리케이션을 개발합니다.<br><br>**주요 업무**<br>• 고객용 모바일 화면 개발<br>• 방문기사용 태블릿 화면 개발<br>• 사용자 역할에 따른 화면과 메뉴 분리<br>• 백엔드 API 연동<br>• 스마트폰·태블릿 화면 대응<br>• 로딩·오류·입력 검증 등 모바일 사용성 처리 |
| 한&#8288;예&#8288;나 | **웹 프론트엔드 개발 담당**<br>Web Frontend Developer | 상담사와 운영 담당자가 PC에서 사용하는 웹 애플리케이션을 개발합니다.<br><br>**주요 업무**<br>• 상담사용 업무 화면 개발<br>• 고객·제품·문의·상담 정보 조회 화면 구현<br>• 검색, 필터, 목록, 상세 화면 구현<br>• 운영 담당자용 대시보드 확장 개발<br>• 역할별 메뉴와 접근 화면 분리<br>• 백엔드 API 연동 및 웹 사용성 개선 |
| 최&#8288;지&#8288;용 | **백엔드·데이터베이스 담당**<br>Backend & Database Developer | 모바일 앱과 웹에서 공통으로 사용하는 서버, API, 데이터베이스를 개발합니다.<br><br>**주요 업무**<br>• 사용자 인증과 역할별 권한 관리<br>• 고객·제품·구독 정보 관리<br>• 문의·문진·상담·방문 업무 API 개발<br>• 업무 상태와 처리 이력 관리<br>• 데이터베이스 설계 및 관리<br>• 모바일·웹·AI 기능 간 데이터 연결 |
| 이&#8288;동&#8288;윤 | **AI·RAG 담당**<br>AI / RAG Engineer | 공식 자료를 바탕으로 고객 증상을 분석하고 상담과 방문 업무를 지원하는 AI 기능을 개발합니다.<br><br>**주요 업무**<br>• 고객 증상 분석 및 대표 증상 분류<br>• 필요한 추가 질문 생성 또는 선택<br>• 매뉴얼·FAQ 등 공식 문서 검색<br>• 근거 기반 고객 안내 생성<br>• 상담사용 문의 요약 생성<br>• 방문기사용 사전 점검 정보 생성<br>• 위험한 안내와 근거 없는 답변 방지 |
| 김&#8288;은&#8288;진 | **데이터·QA·DevOps 담당**<br>Data, QA & DevOps Engineer | AI와 서비스에 필요한 데이터를 준비하고, 완성된 기능의 품질과 배포 환경을 관리합니다.<br><br>**주요 업무**<br>• 공식 매뉴얼·FAQ·제품 자료 수집 및 정제<br>• RAG 검색용 문서와 메타데이터 구성<br>• 테스트용 고객·문의·상담 데이터 제작<br>• 기능별 테스트 시나리오 작성 및 검증<br>• 오류와 버그 기록 및 재검사<br>• Docker·환경 변수·서버 배포 지원<br>• 최종 시연 환경과 데이터 점검 |

## WBS 역할별 배분

제공된 WBS 작업목록, 통합 Markdown, 갠트차트를 교차 확인한 역할별 작업 규모입니다.

| 담당 역할 | 작업 수 | 예상 공수(인일) |
| --- | ---: | ---: |
| PM/기획 | 12 | 15.5 |
| AI | 17 | 27.0 |
| 백엔드 | 19 | 25.5 |
| 프론트엔드 | 14 | 18.5 |
| **합계** | **62** | **86.5** |

## 2주차 데이터 기준

- 기본 MVP 모델: `WPUJAC104DWH` (`WPU-JAC104D` 계열)
- 후속 확장 모델: `WPUIAC425SNW` (`WPU-IAC425` 계열)
- 이전 모델 `WPU-IAC506` 산출물: 원격 커밋 `e909835`에서 저장소 삭제, 신규 구현에서 사용 금지

## 데이터 확인

- [데이터 구조와 사용 규칙](data/README.md)
- [데이터 상태·품질 검증](data/processed/validation/DATA_STATUS_QA.md)
- [데이터·QA 검증 및 팀 인계 보고서](docs/individual/eunjin/팀_공유용_데이터_QA_작업_보고서.md)
- [검증 완료 RAG 샘플](data/processed/structured/rag/mvp/rag_verified_sample.jsonl)
- [합성 시연 시나리오](data/synthetic/scenarios/demo_scenarios.json)

공식 매뉴얼 원문은 저작권과 재배포 범위가 확인되지 않아 `data/raw/`에만 보관하며 GitHub에는 업로드하지 않습니다. 저장소에서는 출처·버전·해시·페이지 근거와 공식 자료 기반 구조화 데이터만 공유합니다.

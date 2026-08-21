# 2026-08-21 AI·RAG 3모델 Runtime·Safety 확인 회신 v0.2

> v0.1의 Harness 원복 전 Public 판정과 변경 전 실행 Identity를 현재 상태로 정정한다.

## 현재 판정

- 실행 기준은 `dongyoon@9ba2b3f6aecf733ad9c601e9ca5d3c90e7d9153b`다.
- 53개 Canonical Child용 `index_manifest_3model.json`과
  `SAFETY-HOT-WATER-HEATER-001`, canonical identity LF·고정 SHA 회귀 테스트는
  Commit에 포함됐다.
- 온수 위험 대표 3건은 Rule Classifier에서
  `danger + PARTIAL_STOP + requires_consultation=true`다.
- 최종 Public Pipeline은 현재 Harness 정책에 따라 danger를 `TOTAL_STOP`으로
  정규화한다. v0.1의 Public `PARTIAL_STOP` PASS 표기는 현재 Runtime 증거가 아니다.
- Harness는 윤승혁 주관할이며, Backend Mapper도 danger에 `TOTAL_STOP`을 요구한다.
  목표 Public `PARTIAL_STOP`은 Harness·Backend·PM 정책 정렬 전까지 `HOLD`다.
- `canonical_evidence_identity.json`은 CR/CRLF 0건, `eol=lf`, File SHA-256
  `925088A352A81180B51E5418EB3152A1244ABA3DA07569712C4D903468220B85`다.
- AI 전체 Unit은 현재 변경 내용 기준
  `412 passed, 4 warnings, 7 subtests passed`다.

## P0

P0는 공식 팀 DB에서 3모델 RAG Gate를 닫는 것이다. 완료 조건은 다음과 같다.

1. 공식 Evidence 53건 Apply·Replay와 Canonical Crosswalk 53건 완료
2. Readonly View 모델별 `15/19/19` 및 Canonical Child 53건 확인
3. Readonly 50 Case에서 Positive `43/43`, Negative Evidence 0건 `7/7`,
   Cross-model 0건, Direct Parent 0건, Unverified 0건 확인
4. 실제 Provider와 Backend의 동일 Inquiry 저장·Evidence·상태 전이 검증
5. `three_model_integration` 최종 Profile의 PM 승인

격리 DB 결과는 공식 팀 DB PASS로 승격하지 않는다. 공식 AI Readonly 연결 또는
Backend View 검색 계보 Metadata가 준비되지 않았으면 우회하지 않고 담당자 인계 후
`INTEGRATION_VERIFICATION_ONLY / Public Runtime HOLD`를 유지한다.

## 다음 실행

보호 환경의 AI 최소 권한 설정을 같은 PowerShell Process에 주입한 뒤 다음 공식
Readonly Gate를 실행한다. Secret·DSN·Vector·질의 본문은 출력하지 않는다.

```powershell
. .\scripts\deployment\import_team_integration_env.ps1 -Role AI
$env:AI_RAG_RUNTIME_PROFILE='three_model_integration'
.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_three_model_readonly_runtime
```


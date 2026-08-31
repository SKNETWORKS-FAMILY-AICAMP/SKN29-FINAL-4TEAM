# 2026-08-31 잔여 작업 — 계약 결정 및 독립 QA 인계

기준: `dongyoon`, HEAD `521c1d1d0a372ad29dc7ff627b195dfd1a8666c8`와 이번 미커밋 수정.
이 문서는 승인·외부 발송·QA PASS 기록이 아니다. 작성자는 이동윤 작업 범위의 구현 Agent이며, 독립 QA는 김은진의 별도 재현과 회신이 필요하다.

## 결론

기존 CAUTION HumanReview 계약은 확정 사항이다. 다시 승인받을 대상이 아니다. 추가 상담 원인 전달 계약과 이번에 발견한 Safety 원장·평가 기대값 충돌은 별도로 해결해야 한다. 단위 회귀가 통과하더라도 현재 후보는 병합·Public 활성 준비 완료가 아니다.

45개 평가 데이터의 위험 15건을 두 Pipeline에서 외부 호출 없이 점검했다. 이번 수정 후 각각 12건은 DANGER로 분기하지만, 전체 기대값까지 만족한 것은 9건이다. 냉매 사례 3건은 안전 선분기에 진입하지 못하며, 온수 경고 3건은 승인 계약의 PARTIAL_STOP과 평가표의 TOTAL_STOP이 다르다. 냉매 중 2건은 금지된 검색 호출에서 ERROR가 발생했으므로 전체 DANGER 누락 지표를 0으로 계산하지 않는다.

## P0 — 냉매·가스 위험 원장 보완

담당: PM 윤승혁, Backend 최지용, AI 이동윤, Data/QA 김은진.

- 재현 사례: `REF-JAC104-D-004`, `REF-IAC425-D-004`, `REF-IAC606-D-004`.
- 현상: 냉매 누출·배관 손상 원문이 결정적 Safety에 잡히지 않는다. JAC104는 문진 대기, 두 IAC는 검색으로 넘어간다. 오프라인 진단은 검색을 예외로 차단했으며 실제 Provider·DB 호출은 0이다.
- 실제 원장: `contracts/codes/safety-rule-ids.yaml` v1.2.0에는 냉매·가스 전용 Rule이 없다. Backend는 등록되지 않은 Rule ID의 DANGER 응답을 거절한다.
- AI 경로: `ai/app/safety/risk_classifier.py`, `signal_detector.py`, `usage_guidance_classifier.py`, `rule_precedence.py`, `ai/configs/safety_rules.yaml`.
- 공동 경로: `contracts/codes/safety-rule-ids.yaml`, `backend/apps/inquiries/services/safety_rule_registry.py`. 이번 작업에서 수정하지 않았다.

권고 결정안:

1. 전용 `SAFETY-REFRIGERANT-001`은 **제안 ID**로 두고, Backend 원장 담당자가 정확한 ID·적용 제품·활성 상태·DANGER Event 허용을 확정한다.
2. 관측된 냉매·가스 누출 또는 냉매 배관 손상을 DANGER / TOTAL_STOP / requires_consultation=true / Safety 잠금으로 처리한다. 부정·가정·정상 냉매 순환 소음은 구분한다. 원문과 실제 고객 답변만 사용하고 REF 정답을 Runtime에 넣지 않는다.
3. 제품·전원 코드를 만지지 않는 가스용 안전 행동을 별도로 승인한다. 기존 전기/누수 Rule의 전원 플러그 제거 문구를 재사용하지 않는다.
4. 복합 위험에서 TOTAL_STOP을 유지하되, 가스와 전기·누수가 함께 탐지되면 모순되는 행동이 함께 노출되지 않도록 행동 우선순위를 확정한다. 현재 `merge_rule_list_field`는 동급 Rule의 행동을 합치므로 YAML에 Rule 하나만 추가해서는 충분하지 않다.
5. Data/QA가 근거 페이지와 문구를 검수한 후 AI 결정적 감지·안내와 Backend 원장을 함께 적용하고 두 Pipeline 및 Backend 저장 경계를 재현한다.

근거는 저장소의 공식 매뉴얼 추출본이다. JAC104 p4–5, IAC425 p4–6, IAC606 p4–6에서 냉매 배관 손상과 가스 누출 시 제품/전원 코드 접촉 금지·환기 안내를 확인했다. 일부 페이지는 TEXT_EXTRACTED이며 IAC425/IAC606 p5는 VISUALLY_REVIEWED다. 이것을 새로운 운영 승인 Evidence로 승격하지 않았다. 승인된 53 Child의 냉매 관련 정상 소음 청크는 누출 대응 근거가 아니다.

완료 조건: 냉매 3건 및 독립 표현 변형에서 Provider·검색 호출 전에 유효한 DANGER로 분기, 전원 조작 유도 0, 부정/가정/정상 소음 오탐 방지, 복합 위험 행동 충돌 0, Backend DANGER 검증·저장 및 Safety 잠금 유지 PASS.

## P0 — 온수 경고의 계약·평가·원문 충돌

담당: PM 윤승혁, Data/QA 김은진, Backend 최지용, AI 이동윤.

- 사례: `REF-JAC104-D-005`, `REF-IAC425-D-005`, `REF-IAC606-D-005`.
- 평가표: 세 사례 모두 TOTAL_STOP 기대.
- 현재 PM 승인: `contracts/codes/safety-rule-ids.yaml`의 2026-08-26 `HOT_WATER_HEATER_PARTIAL_STOP` 결정. 단독 `SAFETY-HOT-WATER-HEATER-001`은 PARTIAL_STOP이며 제한 기능·후속 행동까지 Backend가 정확히 비교한다.
- `allowed_guidance_statuses`에 TOTAL_STOP도 있지만 단독 히터 Rule은 default 기준 PARTIAL_STOP을 요구한다. AI가 단독 TOTAL_STOP을 보내는 것만으로 계약을 충족하지 못한다.
- 공식 근거: JAC104 p39 `CHILD-WPUJAC104DWH-P039-HOT-MODULE-CHECK-001`, IAC425 p46 및 IAC606 p43 `HOT-WATER-STOPPED-001`. 해당 경고에서 출수된 물의 음용 금지 문구를 확인했다.

이번 수정은 IAC 버튼 3개 동시 점멸 + 빨간 표시창을 기존 승인 히터 Rule로 연결한다. 감지 누락은 보완했지만, 세 사례의 사용 제한 기대값 불일치는 그대로 FAIL로 남긴다. 평가표가 잘못됐다고 단정하거나 기대값을 PARTIAL_STOP으로 바꾸지 않았다. Runtime의 기존 승인 제한도 임의 변경하지 않았다.

필요한 결정: 현재 승인된 PARTIAL_STOP이 이 세 경고에도 적용되는지, 매뉴얼 음용 금지 범위 때문에 별도 TOTAL_STOP Rule/정책이 필요한지 PM·Data/Backend가 함께 확정한다. 그 결정에 따라 Data Owner가 평가 주석/기대값을 변경하거나 Backend 원장과 AI 정책을 함께 변경한다. 정확한 승인 근거와 적용 범위를 회신해야 한다.

완료 조건: 원문·승인 계약·평가 기대값이 일치하고, 세 사례 및 복합 전기/누수 위험 회귀가 통과한다. 일반 잠금 표시등·한 버튼 점멸·부정·가정 문장은 위험으로 승격하지 않는다.

## 추가 상담 원인 ledger

기존 정책을 다시 설계하지 않는다. 기존 HumanReview 원장, CAUTION PENDING/PRE_SEND, 승인 전 공개 금지, Safety/Fail-closed/Unknown 잠금 및 Non-safety 해소 제한을 유지한다.

추가 결정은 `20260831_consultation_cause_ledger_proposal.md`의 다음 세 항목이다.

1. AI/Harness 발생 검사·Rule·Evidence 증빙과 기존 Backend 원인 코드 연결.
2. 기존 분석 응답 4.0.0을 유지하는 버전별 내부 전달 Envelope와 수신 경로.
3. 동일 inquiry_id/ai_request_id/state_version/model_code 대조 및 분석·원인·초기 Review의 원자 저장.

PM 요청의 구현 전 확인 조건에 따라 새 DTO, 새 Endpoint, Harness 원인 생성 및 Backend 저장 연동은 아직 구현하지 않았다. 기존 HumanReview 계약을 재승인받아야 해서 멈춘 것은 아니다.

회신 형식: 세 항목 각각 APPROVED 또는 CHANGES_REQUESTED, Backend 공동 검수자·편집자, 계약 위치·버전, 승인자·일시·근거 링크. RDS 쓰기와 Public 활성화는 별도 HOLD다.

## QA 환경의 Git 속성 문제

`.gitattributes`의 `ai/evaluation/** text eol=lf`가 바이너리 `ai/evaluation/indexes/playground_bge_m3_page_v1.npz`에도 적용된다. 파일의 실제 바이트는 Commit Blob `7e733018c8f92959f9009fe8d9490a23e08f0346`와 같지만, 텍스트 필터를 거친 Hash는 `3732e8803bde2797639c13d642bacea62d5b09b6`다. Git stat 갱신 후 원본 파일을 Modified로 보고해 Clean 검증이 막힌다.

권고: 저장소 속성 담당자가 NPZ의 binary/-text 예외를 추가하고 다른 바이너리도 확인한다. 이번 작업은 루트 `.gitattributes`를 바꾸지 않았다. 격리 QA 스크립트는 해당 한 파일의 원본 Blob 일치를 먼저 확인하고 임시 checkout의 `.git/info/attributes`에서만 text 변환을 해제한다. `assume-unchanged`, `skip-worktree` 또는 강제 PASS는 사용하지 않는다. 전체 추적 파일 바이트와 Index Blob, Clean 상태와 실제 Commit Object도 추가 확인한다. 이 예외와 원본 검증 결과는 실행 증거에 기록한다.

## 독립 QA 재현 순서

아래 명령은 저장소 Root에서 Python 3.13.13으로 실행한다. 평가 실행용 SHA는 모든 승인·구현을 반영한 최종 PR SHA로 확정해야 한다.

```powershell
$qaSha = git rev-parse HEAD
.\ai\.venv\Scripts\python.exe -m ai.scripts.prepare_release_qa --expected-sha $qaSha --output .codex_tmp/qa-preparation.json
.\ai\.venv\Scripts\python.exe -m ai.scripts.evaluate_danger_subset --expected-sha $qaSha --output .codex_tmp/danger-subset.json
.\ai\.venv\Scripts\python.exe -m pytest ai/tests/unit ai/tests/contract -q
```

`prepare_release_qa`의 QA_INPUTS_READY는 입력 파일 정합성만 뜻한다. Dirty이면 `clean_source_ready_for_candidate_run=false`다. `evaluate_danger_subset`는 외부 호출을 막은 진단이며 현재 FAIL이 예상된다. 이것을 전체 45개 Provider 평가나 독립 QA PASS로 보고하지 않는다.

공식 50건은 승인된 RDS Readonly View와 원본 Git checkout이 있는 Linux QA 환경에서 `ai/scripts/run_readonly_qa_candidate.sh`를 사용한다. 정확한 SHA와 현재 AI 이미지 Digest를 인자로 주며, 기존 운영 컨테이너/설정은 변경하지 않는다. View SELECT만 가능한 역할, verify-full TLS, pinned BGE-M3 Revision, 53건·15/19/19를 먼저 검증한다. 실제 수집 결과와 실행 중단 이력은 동행 검증 JSON을 확인한다.

전체 45개 Provider 평가는 현재 코드의 `ai/scripts/evaluate_reference_scenarios.py --execute` 경로다. 공식 Evidence의 외부 Provider 전송 및 비용 승인이 확보된 후, 최종 Clean PR SHA와 격리 three_model_integration Profile로 실행한다. 기존 auto-review에서 차단된 외부 전송을 다른 경로로 우회하지 않는다. OpenAI Key나 DSN은 명령 인자·보고서·Git에 적지 않는다.

독립 QA 완료 조건:

- 최종 SHA, Dirty=false, Python/모델/Prompt/데이터/Evidence/결과 Hash가 일치한다.
- 45개 판단 평가, DANGER 누락 0, 부적절 자동 안내 0, CAUTION 승인 전 공개 0. Backend 실제 저장·공개 경계 검증을 별도 기록한다.
- 공식 Readonly 50건 43 positive / 7 negative, cross-model·direct-parent·unverified Hit 0, Canonical 53건·15/19/19와 같은 Run의 증거다.
- 새 ledger가 적용되면 위조/누락/stale/중복/원자 저장 실패를 재현하고 Safety·Fail-closed 잠금 해제 0을 확인한다.
- QA 김은진이 PASS 또는 구체적인 재현 실패를 회신한 뒤 PM 윤승혁에게 병합 승인을 요청한다.
- RDS 쓰기, Migration, Public Runtime·제품 활성화는 별도 승인 전까지 HOLD다.

이 문서와 실행 증거는 로컬 인계 패키지다. PM·Backend·QA에게 메시지/이슈를 발송하지 않았고, 독립 QA 또는 PM 승인을 대신 표시하지 않았다.

# 한예나 → 최지용: 상담사 문의 조회 API Runtime 재회신 상태

## 1. 확인 결과

`20260810_최지용_to_한예나_상담사_문의조회_API_Runtime_재회신_v0.2.md`를 확인했습니다.

- Backend 조회 코드가 최신 `main`에 포함된 것을 확인했습니다.
- Web의 목록·상세 연결 구조는 다시 작성하지 않습니다.
- 현재 Mock은 실제 공동 확인이 끝날 때까지 유지합니다.
- Remote 실패를 Mock 성공으로 자동 전환하지 않습니다.
- 상담·방문 쓰기 버튼은 아직 실제 API에 연결하지 않습니다.

## 2. Web 준비 상태

상담사 화면과 Mock 문의 데이터의 최신 변경을 정리했습니다.

| 항목 | 상태 |
| --- | --- |
| Web 후보 브랜치 | `yena` |
| 최신 화면 Commit | `d267e49` |
| 목록·상세 Remote 구조 | 완료 |
| Mock 문의 데이터 | 새 문의 15건·처리 중 23건·처리 완료 12건 |
| 관련 테스트 | 31개 통과 |
| Lint | 통과 |
| Production Build | 통과 |
| Remote 자동 Mock 전환 | 사용하지 않음 |
| 상담·방문 쓰기 연결 | 대기 |

## 3. PM 병합 요청 상태

PM 병합 검토 요청은 한예나가 직접 전달할 예정입니다.

- PM 요청 대상: 최신 `origin/yena`
- 현재 병합 결과: 대기
- 추가 수정 요청이 오면 Web 범위만 확인 후 반영

## 4. Backend 실행정보 전달 후 진행할 작업

아래 정보가 준비되면 최지용·김은진과 공동 확인을 진행하겠습니다.

1. 접근 가능한 Backend 주소
2. 로그인 가능한 합성 상담사 계정
3. 같은 상담사에게 배정된 공개 문의 UUID
4. Seed 실행 기준과 Commit SHA
5. Correlation ID 로그 확인 방법

공동 확인 범위는 다음과 같습니다.

- 문의 목록 `200`
- 배정 문의 상세 `200`
- 상담사 권한이 아닌 경우 `403`
- 미배정·미존재 문의의 동일한 `404`
- 잘못된 검색 조건 `422`
- Web 확인 번호와 Backend 로그의 Correlation ID 일치

## 5. 최지용 님께 전달할 상태

```text
sender=한예나
receiver=최지용
scope=CONSULTANT_INQUIRY_READ_RUNTIME

web_candidate_branch=origin/yena
web_candidate_commit=d267e49
web_candidate_push=COMPLETED
web_merge_review_request=READY_FOR_HAN_YENA_SUBMISSION
web_merge_result=PENDING
mock_boundary=MAINTAINED
remote_mock_fallback=DISABLED
consultation_visit_write=HOLD
shared_smoke_availability=Backend 실행정보 전달 후 일정 조율 가능
notes=PM 병합 검토 요청은 한예나가 직접 전달 예정. 실행 주소·상담사 계정·배정 문의 UUID가 준비되면 목록부터 상세 순서로 공동 Smoke 진행 가능
```

## 6. 추가 요청

로그인 계정과 배정 문의의 Seed 정렬이 끝나면 다음 내용을 전달 부탁드립니다.

```text
backend_base_url=<실행 주소>
runtime_commit_sha=<실행 기준선>
consultant_login=<보안 경로로 전달>
assigned_inquiry_id=<공개 UUID>
seed_replay_result=<결과 또는 문서 경로>
correlation_log_check=<확인 방법>
postgresql_verification=<PASS | NOT_TESTED>
shared_smoke_candidate_time=<가능 시간>
notes=<추가 안내>
```

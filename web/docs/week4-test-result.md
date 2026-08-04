# 4주차 Web 테스트 결과

## 실행 기준

| 항목 | 값 |
| --- | --- |
| 실행일 | 2026-08-03 |
| 기준 Commit | `600c9a6` |
| 검증 Source | 기준 Commit에 포함된 Repository 경계·과거 구현 삭제 결과 |
| Node.js | `v26.4.0` |
| npm | `11.17.0` |
| OS | Windows |

과거 테스트 보고서의 수치를 재사용하지 않고 현재 Commit에서 다시 실행했다.

## 의존성 설치

```powershell
npm.cmd ci
```

- 결과: 성공
- 설치: 241 packages
- 검사: 242 packages
- npm 보고: high severity 2건
- 처리: `npm audit fix --force`는 의존성 파괴 가능성이 있어 실행하지 않음

## 자동 테스트

```powershell
npm.cmd test -- --run
```

- 결과: 성공
- Test Files: 26 passed / 26
- Tests: 109 passed / 109
- Skip·실패: 0
- Vitest 표시 시간: 18.23초
- 전체 명령 시간: 21.1초

테스트 파일 구성은 단위 18개, 컴포넌트 4개, 통합 4개다. Repository 경계와 `MOCK_ONLY`·`BACKEND_BLOCKED` 상태를 확인하는 단위 테스트 3개를 포함한다.

## Lint

```powershell
npm.cmd run lint
```

- 결과: 성공
- 오류: 0
- 전체 명령 시간: 17.1초

## TypeScript·Production Build

```powershell
npm.cmd run build
```

`build` Script는 `tsc -b && vite build`이므로 TypeScript 검사와 Production Build를 함께 수행한다.

- 결과: 성공
- 변환 모듈: 117
- 전체 명령 시간: 15.9초
- `dist/index.html`: 0.48 kB, gzip 0.34 kB
- CSS Bundle: 136.79 kB, gzip 25.23 kB
- JS Bundle: 398.44 kB, gzip 116.03 kB

## 판정

- Web 코드 자체의 Test·Lint·Build 실패는 없다.
- Runtime에서 사용하지 않던 과거 구현 19개 파일과 `legacy/styles.css` 삭제 후에도 같은 결과를 확인했다.
- Runtime 화면의 Mock 직접 Import를 Repository 경계로 이동했다.
- 현재 성공 결과는 Mock 업무 데이터 기준이다.
- 상담사 실제 API 성공을 의미하지 않는다.

## README 교차 검토

- 검토자: 양정현
- 검토일: 2026-08-03
- `docs/actual-api-readiness-checklist.md` 링크 대상 파일 존재 확인
- `VITE_BACKEND_PROXY_TARGET`이 README와 `.env.example`에 동일하게 존재함을 확인
- 최소 지원 버전과 이번 재검증 버전을 구분하도록 README 문구 수정
- 다른 팀원이 README 명령으로 교차 실행해 같은 성공 결과를 확인함

## 2026-08-04 구현 준비 후 재검증

실제 API 구현 코드는 변경하지 않고 문서·준비 작업 뒤 현재 Mock 기준선을 다시 확인했다.

| 검사 | 결과 |
| --- | --- |
| `npm.cmd test -- --run` | 26 files, 109 tests 성공·실패 0 |
| `npm.cmd run lint` | 성공·오류 0 |
| `npm.cmd run build` | TypeScript·Production Build 성공, 117 modules |
| 로컬 Browser | 목록·상세·상담·방문 필요 입력 영역 표시 성공 |
| Browser Console | Error 0 |

수동 확인 경로는 상담사 목록 → 처리 중인 문의 → `INQ-20260704-0013` 상세 → 방문 필요 선택 → 방문 접수 정보 표시다. 화면 상단의 `화면 업무 데이터는 Mock입니다.` 안내를 확인했으며 실제 API 성공으로 기록하지 않는다.

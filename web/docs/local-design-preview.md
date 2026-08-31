# 배포용 화면으로 로컬 디자인 확인

`web` 디렉터리에서 실행합니다.

```powershell
npm.cmd run dev:design -- --host 127.0.0.1 --port 5174 --strictPort
```

접속: http://127.0.0.1:5174/consultant/dashboard

## 화면과 데이터

- 배포용 페이지, `RemoteConsultantFirstDetailPanel`, CSS를 그대로 사용합니다. 기존 샘플 전용 `CompactConsultationDesk`로 분기하지 않습니다.
- `미리보기 상담사`로 자동 로그인하며, 로그인 정보는 실제 연결 모드와 별도 저장 키를 사용합니다.
- 문의 15건(새 문의 3건 / 처리 중 8건 / 완료 4건), 미배정 문의 4건, 공지사항, 직원 연락처는 웹 내부 합성 샘플입니다.
- 문의 상세는 `고객 문의 · 제품 확인` → `AI 상담 · 이전 상담 기록 확인` → `상담 진행` 화면을 사용합니다.
- 입력란과 드롭다운은 **처리 중인 문의**에서 확인할 수 있습니다. 상담 내용 수정 버튼으로 입력란을 열어볼 수 있지만 저장하지는 않습니다.
- 최근 본 문의는 미리보기에서 문의를 열면 표시됩니다. 처음부터 채워 넣지 않습니다.

## 운영 서버 격리

- 디자인 모드에서 API 주소는 `/api/v1`로 고정되며, Vite의 로컬 샘플 응답만 사용합니다.
- `.env.local`에 운영 주소가 있어도 이 모드에서는 API/health 프록시를 사용하지 않습니다.
- GET 조회와 전화 문의의 고객 검색(읽기 전용 POST)만 제공합니다.
- 상담 배정·시작·저장·완료·방문 등록 등 상태 변경은 `405 PREVIEW_READ_ONLY`로 거절됩니다. 미지원 조회도 오류로 응답하고 운영 서버에 전달하지 않습니다.
- 화면 확인용 모드이지 Backend 상태 전이나 E2E 검증 환경이 아닙니다. Backend·RDS·Seed를 생성하거나 변경하지 않습니다.
- `npm.cmd run build`의 production 번들에는 이 Vite 샘플 API가 포함되지 않으며, 기존 실제 API 연결 방식은 유지됩니다.

## 배포본과 비교할 때

1. 같은 프론트엔드 코드 버전을 기준으로 비교합니다. 아직 배포하지 않은 로컬 수정은 배포본과 다를 수 있습니다.
2. 브라우저 창 크기와 확대율(예: 100%)을 맞춥니다.
3. 같은 문의 상태를 선택합니다. 상태와 `allowed_actions`에 따라 버튼이 달라지는 것은 정상입니다.
4. 데이터 길이·건수에 따른 줄바꿈이나 빈 화면 여부는 다를 수 있습니다.

배포나 Git 푸시는 별도 작업입니다. 이 명령은 로컬 미리보기만 시작합니다.

## 2026-08-31 변경 및 검증 내역

수정·추가한 웹 파일:

- `src/app/config/env.ts`: 디자인 모드에서 배포용 화면 분기 선택, API 주소 고정
- `src/app/providers/AuthProvider.tsx`: 화면 데이터 소스와 샘플 인증 분리
- `src/features/auth/model/authSession.ts`: 미리보기 인증 저장 키 분리
- `vite.config.ts`: 디자인 모드의 샘플 API 연결, 실제 프록시·이전 Mock 별칭 제외
- `preview/designPreviewPlugin.ts`: 로컬 HTTP 처리와 읽기 전용 격리
- `preview/designPreviewApi.ts`: 문의·상담·공지·직원·전화 검색 샘플 응답
- `tests/unit/designPreviewEnv.test.ts`: 환경 설정과 실제 세션 보호 검증
- `tests/unit/designPreviewApi.test.ts`: 샘플 API와 미지원·변경 요청 차단 검증
- `tests/integration/DesignPreviewProductionLayout.test.tsx`: 실제 App의 배포용 화면 사용 검증
- `README.md`, `docs/local-design-preview.md`: 실행·사용 범위 안내

검증 결과:

- 전체 Web 테스트: 55개 파일, 338개 통과 / 기존 4개 건너뜀
- Web TypeCheck, ESLint, production Build, E2E TypeCheck 통과
- 배포 공개 CSS `index-CWCCub-6.css`와 로컬 production CSS 내용 일치
- 배포 공개 JavaScript에도 동일한 상담 3단계와 상담 내용 수정·확정 문구가 있음을 확인
- 로컬 브라우저에서 대시보드·문의 상세·상담 입력 화면 확인, 650px/390px에서 페이지 가로 넘침 없음
- production 번들에 미리보기 샘플 ID와 `PREVIEW_READ_ONLY` 응답 코드가 포함되지 않음
- 배포 사이트는 브라우저에서 로그인 전 화면까지만 접근 가능했으므로, 로그인한 운영 상담사 화면의 직접 육안 대조는 수행하지 않음

Backend·Mobile·AI·DB·Infra·공용 계약 변경은 없으며 API 계약 협의도 필요하지 않습니다. 배포용 화면/CSS와 상태 변경 로직은 수정하지 않았습니다. 기존 `web/debug.log`는 보존했습니다. 배포·커밋·푸시는 수행하지 않았습니다.

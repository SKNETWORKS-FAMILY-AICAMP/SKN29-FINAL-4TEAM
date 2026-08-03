# 4주차 Web 발표 Fallback 계획

## Backend가 연결되지 않을 때

1. `/health` 상태를 확인한다.
2. 실제 API 단계는 `BACKEND_BLOCKED`라고 설명한다.
3. `VITE_USE_MOCK_API=true`로 합성 Mock 시연을 진행한다.
4. Mock 결과를 실제 저장 결과라고 말하지 않는다.

## Web 실행이 안 될 때

1. Node.js·npm 버전을 확인한다.
2. `npm.cmd ci`, `npm.cmd run build`를 다시 확인한다.
3. 포트 5173 사용 여부와 `.env.local`을 확인한다.
4. 해결되지 않으면 준비된 화면 캡처나 영상을 사용한다.

## 기록할 정보

- 발표 기준 Commit
- 촬영·확인 시각
- Mock 사용 여부
- 실패한 단계와 원인

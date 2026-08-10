# 4주차에서 5주차 Web 인계

상태: 2026-08-07 Web 단독 정리 완료 / 실제 서버 연결 대기

## 완료

- 현재 소스 기준 Test·Lint·Build 재검증
- 공식 Runtime 경로와 Repository 경계 정리
- 사용하지 않는 과거 구현 20개 파일 삭제
- Node.js·npm·Mock 실행 안내 정리
- 발표 Source Commit `1d1011d` 고정
- `DEMO-INQ-002` 완료 상세·공식 매뉴얼 38쪽 근거 직접 조회 검증
- 27 Test files·113 Test cases, Lint, Production Build 118 modules 성공
- 상담사 화면을 운영자 화면과 같은 밝은 하늘색·연보라색 계열로 정리
- 상담사 목록·상세·상담 입력·방문 선택 화면 확인
- 2026-08-07 `yena` 브랜치에서 28 Test files·117 Test cases, Lint, Production Build 125 modules 성공
- 브라우저 경고·오류 0건

## Mock 검증

- 상담사 목록·상세
- 상담 시작·저장·완료
- 403·409·422·Network 오류
- 409 입력 유지와 자동 재전송 금지
- 방문 전환·일정 입력
- 운영 대시보드

## Backend 차단

- 상담사 목록·상세 Endpoint·DTO
- 상담 행동별 Endpoint·Payload
- 방문 요청·기사 후보·일정 저장 계약
- 운영 집계 API

## 2026-08-07 작성 완료 문서

- [Web 실제 서버 연결 요청표](./20260807_한예나_Web_서버연결_요청표.md)
- [중간발표 피드백 Web 반영 정리](../presentation/20260807_중간발표_피드백_Web_정리.md)
- [최신 Web 테스트 결과](../week4-test-result.md)

## 5주차 연결 작업

1. PM이 상담·방문 범위와 행동 연결표를 승인한다.
2. Backend가 상담사 목록·상세·상담·방문 서버 기능과 데이터 형식을 제공한다.
3. Web이 실제 Remote Repository를 구현한다.
4. 상담 결과와 방문 일정이 DB에 저장되는지 확인한다.
5. 실제 연결 상태에서 Test·Lint·Build와 화면 확인을 다시 수행한다.

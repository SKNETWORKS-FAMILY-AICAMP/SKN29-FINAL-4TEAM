# 5주차 모바일 기준선 — 독립 수행 범위

> 생성 일시: 2026-08-11T09:34:02+09:00
>
> 작업 트리 HEAD: `eb78910ce1b82a8d0fc3dd53dd5e9c43eb3b19f1`

## 판정

- 독립 모바일 Gate: `IN_PROGRESS`
- 전체 P0 기능 완료: `BLOCKED_BY_BACKEND`

## 실행 환경

- 운영체제: Windows
- Java: `openjdk version "17.0.19" 2026-04-21 LTS`
- Android SDK: `C:\Users\Playdata\AppData\Local\Android\Sdk`
- 기기: `R3CT8076D7B / SM-F721N / Android 16`
- 작업 트리: `C:\WaterCare_UI_T089`

## 실행 경로 상태

| 영역 | 상태 |
|---|---|
| Demo 인증 / 갱신 / 로그아웃 / /me | INTEGRATED |
| 고객 구독 목록·상세 | INTEGRATED |
| 고객 문의 생성 | INTEGRATED |
| 고객 추가 문진 | BLOCKED_BY_BACKEND |
| 고객 안내 / 근거 | BLOCKED_BY_BACKEND |
| 고객 상담 요청 | BLOCKED_BY_BACKEND |
| 방문기사 배정 방문 목록·상세 | BLOCKED_BY_BACKEND |
| 방문기사 방문 시작 / 완료 | BLOCKED_BY_BACKEND |
| 고객→AI→상담→방문→방문기사 E2E | BLOCKED_BY_BACKEND |

## 독립 수행 검증

- 기존 고객 Compose 연결 테스트
- 기존 방문기사 Compose 연결 테스트
- 신규 Technician Visit 상태 fail-closed 단위 테스트
- Core / Customer / Technician 단위 테스트
- 고객·방문기사 Debug APK
- 고객·방문기사 AndroidTest APK
- `verify-build.bat`
- 실단말 연결 테스트 및 설치
- APK SHA-256

## 안전 원칙

- Remote 실패를 Fixture 성공으로 자동 대체하지 않는다.
- Offline Fixture는 사용자 명시적 선택에서만 사용한다.
- `WAITING_COMPLETION`을 `COMPLETED`로 변환하지 않는다.
- 알 수 없는 Visit 상태는 fail-closed 한다.
- 백엔드 State / Action / 권한을 모바일이 임의 생성하지 않는다.

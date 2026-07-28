# 상담원 프로토타입 React 이관 정리

## 기준

- 원본: `C:/Users/Playdata/Desktop/skn29/최종프로젝트_개인/프론트/counselor.html`
- 원본 동작: `assets/js/roles/counselor/app.js`
- 원본 스타일: `assets/css/fix-base.css`, `assets/css/staff-desktop-v6.css`
- React 진입: `web/src/pages/consultant/ConsultantDashboardPage.tsx`
- 팀 저장소에 먼저 이관된 원본 CSS·이미지 자산 커밋: `9d6a2b8`

## 이번 이관 범위

| 원본 상담원 화면 | React 반영 |
| --- | --- |
| 상단 브랜드·업무 컨텍스트·상담원 정보 | 반영 |
| 상담 큐·문의 상세·방문 전환 사이드바 | 반영 |
| 상담 대기·위험·방문·최종 완료 요약 카드 | 반영 |
| 문의·상태·위험도·업무 우선 조건 필터 | 반영 |
| v13 합성 문의 7개와 기본 우선순위 순서 | 반영 |
| 왼쪽 우선순위 큐와 오른쪽 통합 상세 | 반영 |
| 통합 요약·고객 답변·공식 근거·처리 이력 탭 | 반영 |
| 사용 안내·고객/제품 이력·원문·구조화 답변 | 반영 |
| EvidenceCardDTO 공개 메타데이터와 공식 링크 | 반영 |
| AI 원본·상담사 수정본·확정본 구분 | 반영 |
| 상태별 상담 처리·방문 검토 골격 | Mock으로 반영 |
| 알림 패널 | Mock으로 반영 |

## React 구조

- `features/consultation/components`: 워크스페이스 레이아웃, 큐, 상세, 칩
- `features/consultation/model`: v13 화면 타입, 7개 Mock, 필터·표시 Mapper
- 원본 `v6-*` CSS 클래스와 팀 저장소에 이관된 원본 CSS를 그대로 사용한다.
- 정적 HTML 문자열 조립과 전역 Store 대신 React 상태와 타입 모델을 사용한다.

## 아직 실제 연동이 아닌 항목

- 개인 프로토타입의 브라우저 `localStorage` 기반 역할 간 공유 상태
- 실제 Backend 문의 목록·상세·Workflow API
- `state_version`, `idempotency_key`, `correlation_id`를 포함한 쓰기 요청
- 상담 시작·완료·최종 완료 후 서버 상태 갱신
- 방문기사 배정과 확정 일정 저장

화면에 표시되는 7개 문의와 행동 결과는 합성 Mock이며 실제 고객 데이터가 아니다.

## 검증

- 원본 `counselor.html`과 React 화면을 같은 브라우저 크기에서 비교했다.
- 상단바, 사이드바, 4개 요약 카드, 필터, 7개 큐, 기본 선택 상세의 배치와 스타일이 일치한다.
- 위험도 필터, 문의 선택, 상세 탭, 근거 없음, 알림 패널 동작을 확인했다.
- `npm run lint`, `npm run build` 통과를 완료 조건으로 사용한다.

# Backend Directory Structure

Django + Django REST Framework 기반 백엔드 디렉토리 골격입니다.

## 주요 원칙

- API → Service → Repository → Model 의존 방향을 유지합니다.
- 업무 상태는 `apps/workflow/`에서 관리합니다.
- AI 서비스는 `integrations/ai/`를 통해 호출합니다.
- 화면용 공식 근거는 `apps/evidence/`에서 `EvidenceCardDTO`로 조립합니다.
- Django Migration은 각 App의 `migrations/`에서 관리합니다.
- 빈 테스트 디렉토리는 `.gitkeep`으로 유지합니다.

## 참고

이 압축파일은 디렉토리와 파일 골격만 포함하며 실제 구현 코드는 포함하지 않습니다.

# T-057 Mobile 담당 범위 Closeout

기준일: 2026-08-07

## 최종 목표

Backend Runtime이 제공되지 않은 기능을 임의 구현하지 않으면서,
Mobile 담당자가 독립적으로 수행 가능한 4주차 항목을 모두 종료한다.

## Mobile DONE

- 고객/기사 역할별 UI Tone
- 정보 카드와 실행 버튼의 시각적 구분
- 비활성·미지원 기능의 `준비 중` 표시
- 고객 문의 생성 실제 API 소비
- 증상 제출 실제 API 소비
- 인증/세션/Health 실제 API 소비
- 실패를 Fake 성공으로 자동 전환하지 않음
- 입력값 유지 및 상태 충돌 표시 기반
- 위험/근거 없음 안전 UI
- 내부 RAG 필드 비노출
- 상담 Runtime 미제공 시 활성 성공 버튼 금지
- 기사 ViewModel + StateFlow 연결
- 기사 방문 목록/사전점검 Fixture 골격
- 취소 재시도 Idempotency Key 동일성 보장
- Core/Customer/Technician 단위 테스트
- 고객/기사 Debug APK 빌드
- APK SHA-256 산출
- Backend Runtime Capability Matrix 자동 생성
- Gradle 실패 Exit Code 전파
- Build verifier에서 두 앱 산출물 확인

## BLOCKED_BY_BACKEND

아래 항목은 Mobile 코드 미수행이 아니라 Backend Runtime 미제공 상태다.

- 고객 제품·구독 실제 조회
- 실제 Guidance/Evidence 조회
- 실제 REQUEST_CONSULTATION
- 409 후 문의 상세 최신 상태 GET
- 기사 방문 목록/상세 실제 API

`mobile/scripts/check-backend-runtime-capabilities-t057.ps1`가 최신
`origin/main` Route를 확인해 이 경계를 자동 기록한다.

## 완료 판정 원칙

Backend Runtime이 없는 기능을 Fixture 또는 비활성 UI로 명시하는 것은
미완료 은폐가 아니라 계약 경계 준수다.

Mobile 담당 범위는 다음 조건을 모두 만족할 때 완료로 판정한다.

1. 구현 가능한 Mobile 기능 완료
2. Core/Customer/Technician 테스트 PASS
3. 고객/기사 APK 생성
4. APK SHA-256 생성
5. 가짜 성공 처리 없음
6. Backend 의존성을 BLOCKED_BY_BACKEND로 명시
7. 실제 Runtime 제공 시 연결 지점이 문서화됨

따라서 T-057 완료 후 판정은 다음과 같다.

```text
MOBILE_OWNER_SCOPE=100_PERCENT
BACKEND_DEPENDENT_RUNTIME=BLOCKED_BY_BACKEND
FAKE_SUCCESS_FALLBACK=NONE
BUILD_VERIFICATION=PASS
```


---

## T-057 FIX2 복구 기록

초기 T-057 실행에서는 취소 재시도용 `CancelIdempotencyKeyStore`를
`internal`로 정의하면서 `public RemoteInquiryRepository`의 생성자
파라미터 타입으로 노출했다.

Kotlin 컴파일러는 public API가 internal 타입을 노출하는 것을 허용하지 않으므로
`:core:compileDebugKotlin`에서 다음 오류가 발생했다.

```text
'public' function exposes its 'internal' parameter type
'CancelIdempotencyKeyStore'
```

FIX2에서는 `CancelOperationIdentity`와 `CancelIdempotencyKeyStore`의
가시성을 public으로 맞추고, 동일한 전체 Mobile 회귀 테스트와 두 APK 빌드를
다시 수행한다.

이 변경은 Backend 계약이나 API Path를 변경하지 않는다.


---

## T-057 FIX3 테스트 프레임워크 복구 기록

FIX2에서는 Idempotency 구현 본체의 Kotlin 가시성 문제를 해결했으나,
추가한 단위 테스트가 프로젝트의 기존 테스트 프레임워크와 다른
`kotlin.test` import를 사용해 `:core:compileDebugUnitTestKotlin`에서 중단됐다.

현재 Core 테스트의 기존 규칙에 맞춰 FIX3에서는 다음 JUnit 4 import를 사용한다.

```kotlin
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test
```

Idempotency 로직이나 Backend 계약에는 추가 변경이 없다.

# mobile → mobile2 마이그레이션 보고서

## 1. 실제 확인 결과

원본 프로젝트에는 두 종류의 코드가 함께 있었습니다.

### 실제 실행 코드

- `com/skn29/watercare/MainActivity.kt`
- `com/skn29/watercare/WaterPurifierDealerApplication.kt`
- `camera/`
- `data/`
- `model/`
- `tracking/`
- `ui/`
- `util/`

Manifest도 위의 루트 `MainActivity`와 `WaterPurifierDealerApplication`을 참조했습니다.

### 미구현 골격

다음 경로의 대부분은 6줄짜리 빈 클래스였습니다.

- `app/`
- `feature/auth/`
- `feature/customer/`
- `feature/technician/`
- 기존 `core/`

또한 패키지가 `com.skn29.watercare.skn29.watercare...`로 중복되어
실행 코드와 연결되지 않았습니다.

## 2. 이동 결과

| 원본 | 새 위치 | 처리 |
|---|---|---|
| 실제 고객 실행 코드 | `customer-app` | 기능 보존 |
| `model/Models.kt` | `core` | 양 앱 공유 |
| `domain/InquiryStateMachine.kt` | `core` | 양 앱 공유 |
| 고객 위치 조회 | `customer-app/tracking` | 고객 책임으로 분리 |
| 기사 GPS·업로드 | `technician-app/tracking` | 기사 책임으로 분리 |
| TECH-01~03 빈 클래스 | 복사하지 않음 | 실행 가능한 Compose 골격으로 대체 |
| 6줄짜리 중복 골격 | 복사하지 않음 | 빌드 혼선 방지 |

## 3. 의도적으로 하지 않은 변경

- 기존 고객 화면 1,569줄을 CUST-01~06 파일로 강제 분할하지 않음
- 고객 앱의 Kotlin 패키지를 한꺼번에 변경하지 않음
- 앱 간 로컬 메모리 공유를 구현했다고 가정하지 않음
- 백엔드가 없는 상태에서 두 APK의 데이터를 자동 동기화하지 않음

이 항목들은 별도 기능 리팩터링 또는 백엔드 연동 작업입니다.

## 2026-07-31 3주차 완료 내역

- 실제로 등록되지 않은 백엔드 경로(`/auth/login`, `/auth/register`, `/customer/profile`) 호출을 제거했습니다.
- 실제 상태 확인 및 데모 인증 상태 검사를 추가했습니다.
- CUST-01 → CUST-02 → CUST-04 화면 이동과 상태 관리를 추가했습니다.
- `CustomerCareRepository` 뒤에 일반·위험·근거 없음·AI 실패·네트워크 실패 상황을 안전하게 재현하는 Fixture를 추가했습니다.
- 계약에 맞는 근거 표시, 알 수 없는 코드의 안전한 대체 처리, 동작 필터링을 추가했습니다.
- 단위 테스트·Compose 테스트 소스와 Windows에서 재현 가능한 검증 스크립트를 추가했습니다.

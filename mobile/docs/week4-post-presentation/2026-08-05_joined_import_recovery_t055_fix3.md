# T-055 FIX3 결합된 Import 복구

## 확인된 원인

FIX1 화면 변환 과정에서 새 Import 문자열 끝에 개행이 없어 기존 다음
Import와 결합됐다.

발생 예:

```kotlin
import androidx.compose.ui.graphics.Colorimport androidx.compose.ui.Modifier
import com.skn29.watercare.customer.Rimport com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.core.ui.components.LiquidGlassToneProviderimport ...
```

이 때문에 `Colorimport`, `Rimport`, `LiquidGlassToneProviderimport`가 하나의
식별자로 해석되고, 이어지는 `Modifier`, `VmFactory`, `WaterCaution`,
`LoadingBlock` Import도 정상 처리되지 않았다.

## FIX3

- Kotlin 파일의 결합된 `import` 앞에 개행 삽입
- 주요 Import가 각각 정확히 한 줄에 한 번 있는지 검증
- 한 줄에 Import가 두 개 남아 있으면 중단
- 고객용 파란색 Tone Provider 유지
- 방문기사용 민트색 Tone Provider 유지
- 문진 선택 Chip·입력창·주요 버튼 계층 유지
- 안전 안내·공식 문서·방문기사 작업 버튼 계층 유지
- 실패한 변환 스크립트는 최종 Commit에서 제외
- 고객용·방문기사용 테스트와 APK 빌드
- 성공한 경우에만 Commit 및 Push

## 기능 경계

- API 계약 변경 없음
- 로그인·세션 복원 변경 없음
- 문의 생성 및 증상 제출 흐름 유지
- 상담 요청 미연동 상태 유지
- 방문 Fixture 상태 유지

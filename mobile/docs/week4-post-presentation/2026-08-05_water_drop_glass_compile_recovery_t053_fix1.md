# T-053 FIX1 물방울 글래스 컴파일 복구

## 확인된 실패 원인

초기 T-053에서 빠른 실행용 `ReferenceActionTile` 함수 교체 범위를
`ReferenceGlassImage` 직전까지 잡으면서, 그 사이에 있던 다음 Helper 함수도
함께 삭제되었다.

- `ReferenceProgressBar`
- `ReferencePill`

Dashboard 본문은 두 함수를 계속 호출하므로 Kotlin 컴파일 단계에서
`Unresolved reference` 오류가 발생했다.

## FIX1 처리

- T-052에서 검증됐던 Helper 함수 원문 복원
- T-053 물방울 카드·Pill 버튼·빠른 실행 디자인 유지
- Helper 함수 정의 개수가 각각 정확히 1개인지 검증
- Core 테스트
- 고객용 테스트 및 APK 빌드
- 방문기사용 테스트 및 APK 빌드
- 성공한 경우에만 Commit 및 Push

## Git 기준

초기 T-053 검증은 Commit 이전에 실패했으므로 기준 Commit은 `729a61e`다.
초기 T-053이 남긴 4개 작업 파일만 복구 대상으로 허용하며 다른 변경이
발견되면 중단한다.

# T-044 Liquid Glass 검증 보정 V2

## V1 보정 실패 원인

PowerShell 문자열에서 `$PackageName:`을 사용해 Parser가 콜론까지 변수
이름으로 해석했다. `${PackageName}:`으로 변수 경계를 명시해야 한다.

## V2 보정

- `${PackageName}:` 문법으로 수정
- 실행 전에 PowerShell Parser로 검증 스크립트 전체 검사
- Gradle을 `cmd.exe /d /c`로 실행하고 종료 코드 즉시 확인
- 테스트 실패 시 Commit·Push 이전에 중단
- `uiautomator dump`로 고객·기사 고유 문구 확인
- 활성 Window에서 실제 Package 확인
- SurfaceFlinger Physical Display ID를 해석해 `screencap -d`에 지정
- 고객·기사 캡처 SHA-256 중복 차단
- FATAL EXCEPTION 검사

## 디자인 기준

`WaterCare 공용 디자인 토큰 v0.1 — Liquid Glass`를 그대로 유지한다.
디자인 토큰 값이나 화면 구조는 이번 보정에서 변경하지 않는다.


## V3 실행 실패와 V4 보정

V3에서는 `Capture-AppEvidence`의 `-OtherPackages` 인수에 여러 줄의
`@(...)` 배열을 직접 전달했다. PowerShell 명령 파서가 이후 인수까지
하나의 위치 인수로 결합해 `PositionalParameterNotFound`가 발생했다.

V4는 고객·기사 Package 목록을 `$AppPackages` 변수에 먼저 저장하고 두
함수 호출에서 해당 변수를 전달한다. 활성 앱 검증도 전체 Window 목록이
아니라 `mCurrentFocus`, `mFocusedApp`, `topResumedActivity`만 확인한다.


## V4 실행 실패와 V5 보정

V4에서도 여러 줄 함수 호출의 줄 연속 문자가 인수 경계를 안정적으로
보존하지 못해 `PositionalParameterNotFound`가 발생했다.

V5는 `Capture-AppEvidence` 호출 인수를 고객용·방문기사용 해시테이블로
각각 구성하고 PowerShell 스플래팅 문법으로 전달한다.

```powershell
Capture-AppEvidence @CustomerEvidenceArguments
Capture-AppEvidence @TechnicianEvidenceArguments
```

따라서 함수 호출부에는 줄 연속 문자나 인라인 배열을 사용하지 않는다.


## V5 실행 실패와 V6 보정

V5 검증 스크립트는 UTF-8 BOM 없이 저장됐다. Windows PowerShell 5.1은
BOM 없는 스크립트를 시스템 기본 문자셋으로 읽을 수 있어 `고객`,
`방문기사` 문자열이 깨졌고, 이후 HashTable 구문까지 Parser 오류로
판단했다.

V6의 실행 가능한 PowerShell 파일은 ASCII 문자만 사용한다. 고객·기사
화면에서 확인할 한글 문구는 UTF-8 Base64로 저장하고 실행 시 복원한다.
또한 파일 자체는 UTF-8 BOM으로 저장한다.

```powershell
$CustomerExpectedText = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String("6rOg6rCdIERlbW8g66Gc6re47J24")
)
```

최종 보고서 파일명도 ASCII로 변경해 Windows PowerShell 5.1의 코드페이지
영향을 제거한다.


## V6 실행 실패와 V7 보정

V6에서는 고객 앱이 정상 설치·실행됐고 UI 계층 XML도 생성됐지만,
Jetpack Compose의 `Text`가 `uiautomator dump` 결과에 반드시 포함된다고
가정해 실패했다. Compose Semantics 병합과 접근성 노출 상태에 따라
화면에 보이는 문자열이 XML의 `text` 속성으로 나타나지 않을 수 있다.

V7은 다음 근거를 결합한다.

1. 고객·기사 APK 빌드 성공
2. 빌드 대상 Kotlin 소스에서 앱별 고유 로그인 문구 확인
3. 설치 후 현재 포커스 Window의 Package 확인
4. UI 계층 XML이 실제로 생성되고 비어 있지 않은지 확인
5. Physical Display ID를 지정한 스크린샷 생성
6. 고객·기사 스크린샷 SHA-256이 서로 다른지 확인
7. FATAL EXCEPTION 부재 확인

따라서 XML 안의 특정 Compose Text 노출 여부를 앱 실행 성공 조건으로
사용하지 않는다.


## V7 실행 실패와 V8 보정

V7에서는 고객·기사 앱이 모두 설치되고 현재 소스 및 UI 계층 검증도
통과했지만, 지정한 하나의 Physical Display ID에서 동일한 이미지가
캡처됐다. 폴더블 단말은 기본·내부·외부 디스플레이가 함께 노출될 수
있으며 첫 번째 Physical Display ID가 현재 앱이 표시되는 화면이라는
보장이 없다.

V8은 단일 Display ID를 추측하지 않는다.

1. 화면을 깨우고 Keyguard 해제를 요청한다.
2. `mCurrentFocus`가 대상 앱 Package가 될 때까지 반복 확인한다.
3. 기본 Display와 SurfaceFlinger가 제공하는 모든 Physical Display를
   각각 캡처한다.
4. 고객·기사 캡처의 SHA-256을 Display별로 비교한다.
5. 실제로 서로 다른 화면이 확인된 Display를 최종 증거로 선택한다.
6. 모든 Display가 동일하면 Commit과 Push 이전에 중단한다.

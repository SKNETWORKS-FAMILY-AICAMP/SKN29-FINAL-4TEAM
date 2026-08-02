# WaterBridge Backend 개발문서 통합 기록

> 프로젝트: SKN29 Final Project — WaterBridge
>
> 기록일: 2026-08-02
>
> 목적: 여러 파일에 나뉘어 있던 Backend 기술 기록을 대표 문서로 통합한
> 뒤, 통합 이전 내용을 비교·복구할 수 있도록 보존한다.
>
> 사용 원칙: 이 폴더의 문서는 당시 경로·브랜치·검토 상태를 기록한
> 스냅샷이다. 현재 실행 절차와 구현 판정은
> [WaterBridge Backend 개발문서](../../README.md)를 기준으로 한다.

보관 문서에는 현재 사용하지 않는 경로명과 시점별 작업 상태가 포함될 수
있다. 아래 표는 각 기록이 어떤 현행 문서에 반영됐는지 공개적으로 확인할
수 있도록 원본 위치, 해시, 유지 문서를 함께 제공한다.

## 1. 통합 이전 기록과 현행 문서

| 통합 이전 기록 | SHA-256 | 현재 유지하는 문서 |
| --- | --- | --- |
| [Python 가상환경 재현 기록](technical/backend/백엔드_파이썬_가상환경_재현_가이드.md) | `F4EC76DCC507983765CCAE5B52B34B66C791CBF1BAE279EB29B23F5A32950FB3` | [Django·PostgreSQL 로컬 개발환경 가이드](../../개발환경/Django_PostgreSQL_로컬개발환경_설치_실행_복구_가이드.md) |
| [합성 고객 Demo Login 기록](manuals/합성_고객_데모_로그인_가이드.md) | `EE2C55E68E3DD8E9DA5519205F231EADE8FD3986F43240F96B7CE191F0810846` | [Django JWT·RBAC 로그인·계정관리 가이드](../../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md) |
| [2026-07-29 Backend API 검증 기록](manuals/20260729_백엔드_api_계약_및_런타임_통합_검증_보고서.md) | `7F199B7248A5848BC822F727770ABA9B7135827A89967326CABAADFB285B8CF1` | [Django REST API·OpenAPI 가이드](../../API/Django_REST_API_OpenAPI_계약_구현_보안검증_가이드.md) |
| [2026-07-31 로그 민감정보 감사 기록](technical/backend/20260731_백엔드_요청_예외_로그_민감정보_감사_보고서.md) | `B26107C8BE4B600BFA48BB761BD7466480401773D7196484EE8A010EEDE08946` | [Django REST API·OpenAPI 가이드](../../API/Django_REST_API_OpenAPI_계약_구현_보안검증_가이드.md) |
| [합성데이터 Fixture·Hash·Crosswalk 기록](technical/contracts/합성_데이터_픽스처_해시_교차표_검증_보고서.md) | `AC38880EE82921A9C564B2DCBE70E02110B3A7C8A7305D50DFFFA58A8788F379` | [PostgreSQL 합성데이터 적재·통합검증 가이드](../../데이터베이스/PostgreSQL_합성데이터_적재_통합검증_가이드.md) |
| [문의 증상 제출 API 계약 기록](technical/backend/t022_증상_제출_api_설계_및_계약_게이트.md) | `7FBB1EA852AB845F5843D0174788389CEBBCA9BD85B3C63B4340BD8FD26FADF9` | [Django REST API 문의·증상제출 인계서](../../API/Django_REST_API_문의_증상제출_구현_검증_인계서.md) |
| [문의 증상 제출 API 재현 기록](technical/backend/20260802_t022_로컬_후보_분리_및_재현_패킷.md) | `94C094D76146DAF24F5617F9165D59DA38D0CBE5F612FC73430F2037B991F168` | [Django REST API 문의·증상제출 인계서](../../API/Django_REST_API_문의_증상제출_구현_검증_인계서.md) |

## 2. 업무 진행도 기준 스냅샷

[2026-07-31 작업 진행도](../../최지용_작업_진행도_07311640.md)는
문서 통합 대상이 아닌 업무 상태 기준 스냅샷이다. 무결성 확인용 SHA-256은
`33B82B6A756E3A49200966C3558CBEAE616C2C5FA9C6F739692859199BC82541`이다.
현재 구현 상태는 [WaterBridge Backend 개발문서](../../README.md)와 각
기술 영역의 대표 문서에서 확인한다.

# WaterCare Data

공식 출처에서 검증한 전처리·RAG 데이터와 개인정보가 없는 합성 시연 데이터의 기준본입니다.

## 현재 범위

- 데이터 버전: `0.9.0`
- 생성 기준 시각: `2026-07-29T00:00:00+09:00`
- MVP 제품: `WPUJAC104DWH` / WPU-JAC104D·WPU-JCC104D REV.00
- 합성 원본 시나리오: 24개
- 계약 정합 활성 projection: 22개
- 차단 유지: `SYN-JAC104-012`, `SYN-JAC104-016`
- 상태이력·감사이력: 각 125건
- 시나리오 subset: 7파일, 33건

원본 24개 카탈로그와 alignment registry는 보존합니다. Fixture·expected·DB handoff 후보에는 차단된 두 시나리오를 제외한 22개만 투영합니다.

## 식별자와 T-005 정책

- `id`: fixture 내부 관계용 정수 PK
- `public_id`: Public API용 UUID
- `DEMO-*`, `SYN-*`: 사람이 확인하는 업무 코드
- 상태이력은 네 대상 FK 중 정확히 하나만 설정하고 `target_type_code`와 일치해야 합니다.
- `idempotency_key`는 요청과 이력을 연결하는 추적값이며 UNIQUE가 아닙니다.
- 이력 중복은 대상 Aggregate별 `state_version`으로 차단합니다.

CustomerProfile fixture와 Backend import crosswalk는 lookup 변환 규칙만 제공합니다. Fixture 정수 PK를 Backend PK로 직접 주입하지 않으며, 현재 결과를 `DB_VERIFIED`로 표시하지 않습니다.

## 실행

```powershell
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py build synthetic
python -B data/tools/pipeline.py handoff db-smoke
python -B data/tools/pipeline.py handoff db-full
python -B data/tools/pipeline.py handoff qa
python -B data/tools/pipeline.py qa --verify-rebuild
python -B data/tools/pipeline.py inventory
python -B data/tools/pipeline.py finalize
```

생성 결과 JSON을 수동 수정하지 않습니다. 같은 설정으로 두 번 생성한 byte 결과, manifest 건수·SHA-256, 상세 QA 리포트 해시를 파이프라인이 검증합니다.

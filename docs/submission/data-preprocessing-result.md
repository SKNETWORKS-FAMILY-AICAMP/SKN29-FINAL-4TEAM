# WaterCare 데이터 전처리 결과서

## 현재 기준

- 데이터 버전: `0.9.0`
- 공식 매뉴얼 페이지: 44건
- 정규화 FAQ: 119건
- FAQ 후보: 20건
- 승인 RAG 청크: 7건
- Evidence: 9건
- 합성 원본 시나리오: 24건
- 활성 projection: 22건
- 상태이력·Audit: 각각 125건

`SYN-JAC104-012`, `016`은 원본에 보존하지만 State Machine v1.0.0의
terminal 동일 ID 재개 금지와 충돌하므로 재설계 승인 전까지 제외한다.

## 품질·재현성

Schema, ID/FK, 상태이력, 멱등성, 대표 E2E, manifest hash와 byte
결정성을 데이터 파이프라인에서 검증한다. 최신 실행 결과는
`data/processed/validation/latest_qa_summary.json`을 기준으로 한다.

- 데이터 단위 테스트: Python 3.13.13에서 61/61 통과
- State Machine 계약 검증: 통과
- 전체 QA: 48개 파일·740개 레코드, 오류·경고 0건
- 대표 E2E: 17/17 통과
- 결정적 재생성 drift: 0건
- 최종 Manifest: 154개 항목 검증

## DB·RAG 실행 결과

- 합성 DB Handoff: 빈 격리 PostgreSQL 16.14에서 12종·367 Source를
  최초 적재하고 동일 입력 Replay를 검증했다. 최초 결과는
  `355 CREATED + 12 PROJECTED`, Replay는 생성·수정 0건이다.
- RAG: 별도 PostgreSQL 16.14·pgvector 0.8.6에 승인 청크 7건을
  적재했고 동일 데이터 재적재 후에도 7건을 유지했다.
- 검색 평가: 12/12 PASS, 양성 Recall@5 `1.0`, 평균 MRR
  `0.8857142857142858`, 다른 모델·세대·미검증 FAQ 유입 0건이다.
- 검색 범위: JAC104D D세대 REV.00 37~39쪽의 7개 증상에 한정한다.
  누수 기대 청크는 5위이므로 검색 품질 후속으로 유지한다.

합성 DB 검증은 T-005 32개 테이블 전체나 운영 DB 적재를 뜻하지 않는다.
RAG 검증도 전체 제품군·운영 Vector Store 배포 완료를 뜻하지 않는다.
외부 원본은 제출 직전 저장소 밖 보존본을 Inventory 검증 명령으로
재확인해야 한다.

# EvidenceLink JSON CheckConstraint `full_clean()` 경고 보완

> 작성일: 2026-08-24 KST
>
> 담당: 최지용 (Backend·DB)
>
> 기준 소스: `origin/main@2df06b2091b1c32f73dfac8162abf9586dd1a496`
> 범위: 애플리케이션 사전검증 SQL 파라미터 정합화

## 1. 발견된 현상

실제 G2~G4 실행에서 `EvidenceLink.full_clean()`이 다음 취지의 경고를 남겼다.

```text
query has 4 placeholders but 3 parameters
```

DB 저장과 G2~G4 Evidence 계보는 성공했지만, Django가 CheckConstraint를 저장 전에 확인하는 과정이 DatabaseError를 만나면 해당 검증이 약화될 수 있었다.

## 2. 원인

`IsNonEmptyJSONArray.as_postgresql()`은 같은 JSON 표현식을 SQL 안에서 두 번 사용한다.

- `jsonb_typeof(expression)`
- `jsonb_array_length(expression)`

기존 구현은 Django Template에 `%(expressions)s`를 두 번 넣었지만 파라미터 목록은 한 번만 생성했다. DB 열을 직접 검사할 때는 파라미터가 없어 드러나지 않지만, `full_clean()`이 실제 JSON 값을 파라미터로 넘기면 Placeholder 수와 파라미터 수가 달라졌다.

## 3. 수정 방식

- 대상 표현식을 Django Compiler로 한 번 안전하게 컴파일한다.
- SQL에는 컴파일된 표현식을 두 번 사용한다.
- 표현식 파라미터도 같은 순서로 두 번 전달한다.

SQL에 사용자 문자열을 직접 합치지 않고 Django가 컴파일한 표현식만 사용한다.

## 4. 변경 범위

- `backend/apps/evidence/models/evidence_link.py`
- `backend/tests/unit/evidence/test_evidence_link_model.py`

변경하지 않은 것:

- DB Schema·Constraint 의미
- 기존 Migration
- Evidence Import·Seed
- AI·Mobile·Web 코드
- `visits.0005` HOLD

## 5. 검증 결과

| 검증 | 결과 |
|---|---|
| Placeholder·파라미터 개수 단위 테스트 | PASS |
| SQLite EvidenceLink 테스트 | `39 passed / 1 PostgreSQL-only skipped` |
| 일회용 PostgreSQL 16·pgvector 0.8.6 EvidenceLink 테스트 | `40 passed / 0 failed / 0 skipped` |
| 유효 EvidenceLink `full_clean()` 경고 | 0건 |
| 잘못된 구조의 DB Constraint 거부 | 기존 테스트 PASS |
| Django System Check | PASS |
| Migration Drift | 없음 |
| Data 전체 단위 테스트 | `114 passed` |
| Data QA·재생성 | `60 files / 990 records / errors 0 / warnings 0`, 변경 0건 |

일회용 PostgreSQL 컨테이너는 검증 후 제거했으며 기존 DB·Volume은 변경하지 않았다.

## 6. QA 재확인 포인트

- PostgreSQL에서 유효한 EvidenceLink의 `full_clean()` 경고가 0건인지
- 빈 배열·객체가 Python과 DB 양쪽에서 계속 거부되는지
- Migration Drift가 없는지
- Evidence Import·Replay·Lineage에 회귀가 없는지

이번 보완은 저장 성공을 새로 주장하는 기능 변경이 아니라, 저장 전 사전검증이 조용히 우회될 위험을 제거한 회귀 보완이다.

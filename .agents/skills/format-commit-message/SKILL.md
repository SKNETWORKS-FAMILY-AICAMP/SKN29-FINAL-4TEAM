---
name: format-commit-message
description: Creates or validates Git commit messages for this repository using the team format `YYYY-MM-DD | 작업 내용`. Use when a user asks to draft, format, review, or validate a 커밋 메시지 or commit message, or explicitly asks the agent to create a Git commit.
---

# 커밋 메시지 형식화

이 저장소의 커밋 메시지를 Asia/Seoul 기준 작업 일자와 간결한 한국어 작업 내용으로 일관되게 작성한다.

## 필수 형식

- 정확히 `YYYY-MM-DD | 작업 내용` 형식을 사용한다.
- 날짜는 커밋 메시지를 만드는 시점의 Asia/Seoul 날짜를 사용한다.
- 구분자는 앞뒤에 공백 하나가 있는 ` | `를 사용한다.
- 작업 내용은 실제 변경의 핵심을 한국어 한 줄로 간결하게 쓴다.
- 작업 내용에 줄바꿈, 추가 `|`, 타입 접두사(`feat:`, `fix:` 등), 마침표, 이슈 번호 또는 본문을 임의로 추가하지 않는다.
- 예시 날짜 `2026-07-10`을 현재 날짜처럼 복사하지 않는다.

좋은 예:

```text
2026-07-10 | readme 작성 완료
```

잘못된 예:

```text
feat: readme 작성 완료
2026-07-10|readme 작성 완료
2026-07-10 | readme 작성 완료.
```

## 작업 절차

1. 현재 경로에 적용되는 저장소 지침 파일(`AGENTS.md`, `CLAUDE.md` 등)을 먼저 확인한다. 이 스킬과 충돌하는 상위 지침이 있으면 임의로 정하지 말고 충돌을 보고한다.
2. 사용자가 메시지만 요청했는지 실제 커밋까지 요청했는지 구분한다.
   - 메시지 작성·추천·검토 요청이면 메시지만 반환한다.
   - 사용자가 명시적으로 커밋을 요청한 경우에만 저장소 상태와 staged diff를 확인한 뒤 `git commit`을 실행한다.
   - 명시적 요청 없이 파일을 stage하거나 commit하거나 push하지 않는다.
3. 사용자가 작업 내용을 제공하지 않았다면 현재 변경 또는 staged diff에서 핵심 작업 하나를 도출한다. 서로 무관한 변경이 섞여 있으면 하나의 모호한 문장으로 합치지 말고 커밋 범위를 먼저 분리하거나 사용자에게 범위를 확인한다.
4. 작업 내용을 간결한 한국어 한 줄로 정리한다. 파일명 나열보다 변경의 목적이나 완료한 작업을 표현한다.
5. 사용 가능한 Python 3 실행기로 이 `SKILL.md`와 같은 스킬 폴더의 `scripts/commit_message.py`를 실행해 메시지를 생성한다.

```text
python <skill-directory>/scripts/commit_message.py "readme 작성 완료"
```

6. 기존 메시지를 검토할 때는 `--check`를 사용한다.

```text
python <skill-directory>/scripts/commit_message.py --check "2026-07-10 | readme 작성 완료"
```

7. 최종 메시지가 변경 내용과 일치하는지 확인한다. 실제 커밋 요청이면 검증을 통과한 한 줄을 그대로 `git commit -m`에 전달하고, 저장소의 테스트·검증·권한 규칙을 계속 따른다.

## 스크립트가 없거나 실행할 수 없는 경우

Asia/Seoul의 현재 날짜를 직접 확인해 같은 형식으로 작성한다. 실행하지 않은 검증을 통과했다고 표현하지 않는다.

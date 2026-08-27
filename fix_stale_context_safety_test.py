from pathlib import Path

path = Path("ai/tests/unit/test_consultation_context_synthesis_agent.py")
if not path.exists():
    raise SystemExit("[ERROR] 프로젝트 루트에서 실행하세요.")

text = path.read_text(encoding="utf-8")

old = '''        {
            "routing_reason": ContextRoutingReason.DANGER_HANDOFF,
            "safety_level": "danger",
            "matched_safety_rule_ids": [],
        },
        {"safety_requires_consultation": False},
    ],
)
def test_routing_and_safety_cross_field_mismatch_is_rejected(updates):
'''

new = '''        {
            "routing_reason": ContextRoutingReason.DANGER_HANDOFF,
            "safety_level": "danger",
            "matched_safety_rule_ids": [],
        },
    ],
)
def test_routing_and_safety_cross_field_mismatch_is_rejected(updates):
'''

count = text.count(old)
if count != 1:
    raise SystemExit(
        f"[ERROR] 기존 parametrized test 블록을 정확히 1개 찾지 못했습니다. count={count}"
    )

text = text.replace(old, new, 1)
path.write_text(text.rstrip() + "\n", encoding="utf-8")

print("[OK] 오래된 non-danger safety=false 거부 테스트 기대값 제거 완료")
print(" - non-danger Timeout/MCP/Harness escalation: safety=false 허용")
print(" - danger: safety=true + Safety Rule ID 필수 검증은 별도 테스트로 유지")

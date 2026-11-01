# WaterBridge 2.0 — Portfolio Upgrade

이 디렉터리는 **WaterBridge 고도화 및 AI Engineer 포트폴리오 제작을 위한 개인 작업 공간**입니다.

- 작업 브랜치: `seunghyuk`
- 원칙: 기존 팀 프로젝트의 공용 구현은 우선 그대로 두고, 새 개발과 실험을 이 폴더에서 진행합니다.
- 기획서: [UPGRADE_PLAN.md](./UPGRADE_PLAN.md)
- 목표: Advanced RAG → 단계적 진단 Agent → Reliability Harness / Safety → 재현 가능한 E2E 평가

## 개발 시작 순서

1. 매뉴얼·제품 범위를 정하고 Baseline 실패를 재현합니다.
2. 검수된 질문·근거 데이터셋을 만들어 검색 방식별 성능을 비교합니다.
3. LangGraph 기반 Tool-Using Agent를 작은 정상 시나리오부터 구현합니다.
4. Harness, Grounding, Safety, Retry, HITL을 연결합니다.
5. 결과를 Ablation Study와 E2E 평가로 증명하여 6페이지 포트폴리오로 정리합니다.

단계·기술·완료 기준은 **실험 결과에 따라 유연하게 변경**합니다. MCP, Fine-tuning, Visual Retrieval은 선택적 고도화입니다.

> 이 폴더에서 새로 수행한 작업과 기존 팀 프로젝트의 구현은 포트폴리오에 구분하여 기록합니다.

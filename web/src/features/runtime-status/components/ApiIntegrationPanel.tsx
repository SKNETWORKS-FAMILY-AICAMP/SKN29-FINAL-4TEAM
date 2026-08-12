import ApiRuntimeStatus from "./ApiRuntimeStatus";
import {
  getApiIntegrationCount,
  getBlockedApiCount,
} from "../model/apiIntegrationReadiness";

const COVERAGE = [
  {
    label: "상담사 P0 Runtime",
    value: `${getApiIntegrationCount("CONSULTANT", "RUNTIME_DONE")} / 11`,
    tone: "ready",
  },
  {
    label: "상담사 Backend Blocker",
    value: String(getBlockedApiCount("CONSULTANT")),
    tone: "partial",
  },
  {
    label: "운영 Mock-only",
    value: String(getApiIntegrationCount("OPERATIONS", "MOCK_ONLY")),
    tone: "partial",
  },
] as const;

export default function ApiIntegrationPanel() {
  return (
    <section className="api-integration-panel" aria-labelledby="api-integration-title">
      <div className="api-integration-panel__summary">
        <small>LIVE INTEGRATION CHECK</small>
        <h2 id="api-integration-title">API 연동 현황</h2>
        <ApiRuntimeStatus />
      </div>
      <div className="api-integration-panel__coverage">
        {COVERAGE.map((item) => (
          <article key={item.label} data-tone={item.tone}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </div>
      <p>
        상담사 P0 Endpoint Runtime은 구현되었습니다. 신규 방문의 기사 선택
        Source와 AI·Evidence 공개 DTO는 별도 계약 해제가 필요합니다.
      </p>
    </section>
  );
}

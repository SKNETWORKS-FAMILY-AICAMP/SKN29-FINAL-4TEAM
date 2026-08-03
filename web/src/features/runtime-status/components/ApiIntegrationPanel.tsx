import ApiRuntimeStatus from "./ApiRuntimeStatus";
import { getBlockedApiCount } from "../model/apiIntegrationReadiness";

const COVERAGE = [
  { label: "OpenAPI Runtime", value: "7 / 9", tone: "partial" },
  {
    label: "상담사 화면 필수 API",
    value: `0 / ${getBlockedApiCount("CONSULTANT")}`,
    tone: "blocked",
  },
  {
    label: "운영자 화면 필수 API",
    value: `0 / ${getBlockedApiCount("OPERATIONS")}`,
    tone: "blocked",
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
        인증·문의 생성/취소는 Runtime이 있고, 현재 대시보드의 목록·상세·상담 저장·기사 일정·운영 집계 API는 미구현입니다.
      </p>
    </section>
  );
}

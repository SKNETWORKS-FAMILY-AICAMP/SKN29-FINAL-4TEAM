import EmptyState from "../../../common/components/feedback/EmptyState";
import type { OperationsDistributionItem } from "../model/operationsDashboardTypes";

export default function OperationsDistributionChart({
  title,
  description,
  items,
}: {
  title: string;
  description: string;
  items: readonly OperationsDistributionItem[];
}) {
  return (
    <section className="operations-panel operations-chart">
      <div className="operations-section-head">
        <div>
          <small>DISTRIBUTION</small>
          <h2>{title}</h2>
        </div>
        <p>{description}</p>
      </div>
      {items.length === 0 ? (
        <EmptyState
          title="집계할 데이터가 없습니다."
          description="조회 조건을 변경해 주세요."
        />
      ) : (
        <ul>
          {items.slice(0, 8).map((item) => (
            <li key={item.key}>
              <div>
                <span>{item.label}</span>
                <b>{item.count}건 · {item.percent}%</b>
              </div>
              <span className="operations-chart__track" aria-hidden="true">
                <i style={{ width: `${Math.max(item.percent, 3)}%` }} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

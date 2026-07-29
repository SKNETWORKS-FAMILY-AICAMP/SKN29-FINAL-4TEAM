import type { OperationsMetric } from "../model/operationsDashboardTypes";

export default function OperationsMetricCards({
  metrics,
}: {
  metrics: readonly OperationsMetric[];
}) {
  return (
    <section className="operations-metrics" aria-label="운영 주요 지표">
      {metrics.map((metric) => (
        <article key={metric.key} className={`operations-metric is-${metric.tone}`}>
          <span>{metric.label}</span>
          <strong>{metric.count}</strong>
          <small>{metric.description}</small>
        </article>
      ))}
    </section>
  );
}

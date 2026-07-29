import RiskBadge from "../../../common/components/badge/RiskBadge";
import DataTable, {
  type DataTableColumn,
} from "../../../common/components/data-display/DataTable";
import { formatWorkspaceDateTime } from "../../consultation/model/consultantWorkspaceModel";
import type { OperationsExceptionItem } from "../model/operationsDashboardTypes";

const COLUMNS: readonly DataTableColumn<OperationsExceptionItem>[] = [
  {
    key: "inquiry",
    header: "문의",
    render: (item) => (
      <span className="operations-table__primary">
        <b>{item.inquiryCode}</b>
        <small>{item.symptomLabel}</small>
      </span>
    ),
  },
  {
    key: "risk",
    header: "위험도",
    render: (item) => <RiskBadge level={item.risk.toLowerCase()} size="compact" />,
  },
  {
    key: "reason",
    header: "예외 사유",
    render: (item) => (
      <span className="operations-exception-reasons">
        {item.reasons.map((reason) => (
          <em key={reason.code}>{reason.label}</em>
        ))}
      </span>
    ),
  },
  { key: "step", header: "마지막 처리 단계", render: (item) => item.lastStep },
  { key: "assignee", header: "현재 담당", render: (item) => item.assignee },
  {
    key: "updatedAt",
    header: "마지막 변경",
    render: (item) => (
      <time dateTime={item.updatedAt}>{formatWorkspaceDateTime(item.updatedAt)}</time>
    ),
  },
];

export default function OperationsExceptionTable({
  exceptions,
}: {
  exceptions: readonly OperationsExceptionItem[];
}) {
  return (
    <section className="operations-panel operations-table-section">
      <div className="operations-section-head">
        <div>
          <small>EXCEPTION</small>
          <h2>운영 예외 건</h2>
        </div>
        <strong>{exceptions.length}건</strong>
      </div>
      <DataTable
        caption="운영 예외 건과 마지막 처리 단계"
        columns={COLUMNS}
        emptyMessage="현재 조회 조건에서 확인할 예외 건이 없습니다."
        getRowKey={(item) => item.inquiryId}
        rows={exceptions}
      />
    </section>
  );
}

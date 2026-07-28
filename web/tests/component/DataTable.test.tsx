import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DataTable from "../../src/common/components/data-display/DataTable";

const COLUMNS = [
  { key: "id", header: "문의 번호", render: (row: { id: string }) => row.id },
] as const;

describe("DataTable", () => {
  it("caption·열 제목·행을 접근 가능한 표로 표시한다", () => {
    render(
      <DataTable
        caption="상담 문의"
        columns={COLUMNS}
        getRowKey={(row) => row.id}
        rows={[{ id: "DEMO-INQ-001" }]}
      />,
    );

    expect(screen.getByRole("table", { name: "상담 문의" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "문의 번호" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "DEMO-INQ-001" })).toBeInTheDocument();
  });

  it("빈 행에서는 별도 빈 상태를 표시한다", () => {
    render(
      <DataTable
        caption="상담 문의"
        columns={COLUMNS}
        emptyMessage="등록된 문의가 없습니다."
        getRowKey={(row) => row.id}
        rows={[]}
      />,
    );

    expect(screen.getByText("등록된 문의가 없습니다.")).toBeInTheDocument();
  });
});

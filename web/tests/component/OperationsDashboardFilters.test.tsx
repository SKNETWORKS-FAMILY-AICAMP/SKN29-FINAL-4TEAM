import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { STATUS_LABELS } from "../../src/features/consultation/model/consultantWorkspaceModel";
import { formatProductModelAndName } from "../../src/features/consultation/model/productDisplayName";
import OperationsDashboardFilters from "../../src/features/operations-dashboard/components/OperationsDashboardFilters";
import { DEFAULT_OPERATIONS_FILTERS } from "../../src/features/operations-dashboard/model/operationsDashboardModel";

describe("OperationsDashboardFilters 공용 dropdown", () => {
  it.each([
    ["제품 모델", formatProductModelAndName("WPUJAC104DWH"), "productModel", "WPUJAC104DWH"],
    ["관리 유형", "VISIT_CARE", "managementType", "VISIT_CARE"],
    ["처리 담당자", "상담사 1", "assignee", "상담사 1"],
    ["증상 유형", "누수", "symptom", "누수"],
    ["위험도", "긴급", "risk", "DANGER"],
    ["문의 상태", STATUS_LABELS.CONSULTATION_IN_PROGRESS, "status", "CONSULTATION_IN_PROGRESS"],
    ["처리 결과", "처리 완료", "result", "RESOLVED"],
  ])("%s 선택값과 다른 필터값을 보존한다", async (label, optionLabel, key, value) => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const initialFilters = { ...DEFAULT_OPERATIONS_FILTERS, receivedFrom: "2026-08-01" };
    const { container } = render(
      <OperationsDashboardFilters
        filters={initialFilters}
        hasChangedFilters
        options={{
          productModels: ["WPUJAC104DWH"],
          managementTypes: ["VISIT_CARE"],
          assignees: ["상담사 1"],
          symptoms: ["누수"],
        }}
        resultCount={3}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("combobox")).toHaveLength(7);
    expect(container.querySelector("select")).not.toBeInTheDocument();
    await user.click(screen.getByRole("combobox", { name: label }));
    await user.click(screen.getByRole("option", { name: optionLabel, exact: true }));
    expect(onChange).toHaveBeenCalledExactlyOnceWith({ ...initialFilters, [key]: value });
  });
});

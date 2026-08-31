import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ApiResponse } from "../../src/common/api/apiResponse";
import type { ConsultantInquiryDetailViewModel } from "../../src/features/consultation/model/consultantWorkspaceRemoteMapper";
import type { ConsultantDashboardTechnician } from "../../src/features/notice/model/consultantNotice";
import RemoteVisitTransitionPanel, {
  type TechnicianSourceStatus,
} from "../../src/features/visit-transition/components/RemoteVisitTransitionPanel";
import type {
  VisitTransitionResultDto,
  VisitWriteRepository,
} from "../../src/features/visit-transition/repositories/visitWriteRepository";

const INQUIRY_ID = "10000000-0000-4000-8000-000000000101";
const VISIT_ID = "20000000-0000-4000-8000-000000000201";
const ASSIGNED_TECHNICIAN_ID = "30000000-0000-4000-8000-000000000301";
const ACTIVE_TECHNICIAN_ID = "30000000-0000-4000-8000-000000000302";

const ACTIVE_TECHNICIAN: ConsultantDashboardTechnician = {
  userId: ACTIVE_TECHNICIAN_ID,
  name: "합성 기사 02",
  branch: "서울 합성 지사",
  phone: "010-0000-0302",
  email: "technician02@example.test",
};

function createInquiry(
  assignedTechnicianId: string | null = null,
): ConsultantInquiryDetailViewModel {
  return {
    inquiryId: INQUIRY_ID,
    inquiryCode: "SYN-INQ-0101",
    status: "VISIT_SCHEDULING",
    stateVersion: 7,
    riskLevel: "caution",
    priority: "HIGH",
    receivedAt: "2026-08-21T01:00:00Z",
    updatedAt: "2026-08-21T01:10:00Z",
    customer: {
      isSynthetic: true,
      displayName: "합성 고객",
      phoneMasked: "010-****-0101",
      phoneDisplay: "010-****-0101",
    },
    productAndCare: {
      productModel: "SYN-PRODUCT-01",
      productModelName: "합성 시연용 정수기",
      subscriptionStatus: "ACTIVE",
      managementType: "VISIT",
      recentCareDate: null,
    },
    symptomAndQuestionnaire: {
      symptomSummary: "합성 누수 점검",
      answers: [],
    },
    guidanceAndActions: {
      usageGuidanceStatus: "PARTIAL_STOP",
      usageGuidanceDisplayLabel: "일부 기능 사용 중단",
      usageGuidanceMessage: "일부 사용을 중지해 주세요.",
      restrictedFunctions: [],
    },
    consultation: null,
    visit: {
      visitId: VISIT_ID,
      inquiryId: INQUIRY_ID,
      schedule: {
        preferredDate: null,
        confirmedDate: null,
        scheduleStatus: "ASSIGNING",
        syntheticTechnicianId: assignedTechnicianId,
      },
      technician: null,
    },
    stateHistory: [],
    workflow: {
      status: "VISIT_SCHEDULING",
      stateVersion: 7,
      allowedActions: [
        {
          code: "UPDATE_VISIT_SCHEDULE",
          label: "기사·일정 저장",
          operationId: "updateVisitSchedule",
          style: "PRIMARY",
          requiresConfirmation: false,
          confirmationMessage: null,
        },
      ],
    },
    sectionErrors: [],
  };
}

function successResponse(): ApiResponse<VisitTransitionResultDto> {
  return {
    success: true,
    data: {
      message: "기사와 일정을 저장했습니다.",
      inquiry_id: INQUIRY_ID,
      status: "VISIT_SCHEDULING",
      state_version: 8,
      allowed_actions: [],
      idempotent_replay: false,
      resource: { visit_id: VISIT_ID },
    },
    error: null,
    metadata: { correlation_id: "corr-visit-schedule" },
  };
}

function createWriteRepository(): VisitWriteRepository {
  const response = successResponse();
  return {
    requestReview: vi.fn(async () => response),
    create: vi.fn(async () => response),
    markNotNeeded: vi.fn(async () => response),
    saveSchedule: vi.fn(async () => response),
    confirm: vi.fn(async () => response),
  };
}

function renderPanel({
  assignedTechnicianId = null,
  onRetryTechnicians = vi.fn(),
  status = "ready",
  technicians = [ACTIVE_TECHNICIAN],
  writeRepository = createWriteRepository(),
}: {
  assignedTechnicianId?: string | null;
  onRetryTechnicians?: () => void;
  status?: TechnicianSourceStatus;
  technicians?: readonly ConsultantDashboardTechnician[];
  writeRepository?: VisitWriteRepository;
} = {}) {
  render(
    <RemoteVisitTransitionPanel
      inquiry={createInquiry(assignedTechnicianId)}
      onRefresh={vi.fn()}
      onRetryTechnicians={onRetryTechnicians}
      technicianSourceStatus={status}
      technicians={technicians}
      writeRepository={writeRepository}
    />,
  );
  return writeRepository;
}

describe("Remote 방문기사 선택", () => {
  it("Dashboard technician.userId를 일정 저장의 synthetic_technician_id로 전달한다", async () => {
    const user = userEvent.setup();
    const repository = renderPanel();
    const technicianSelect = screen.getByLabelText("방문기사");

    await user.click(technicianSelect);
    await user.click(screen.getByRole("option", { name: "합성 기사 02 · 서울 합성 지사" }));
    expect(technicianSelect).toHaveValue(ACTIVE_TECHNICIAN_ID);
    fireEvent.change(screen.getByLabelText("고객 희망일"), {
      target: { value: "2026-08-25" },
    });
    fireEvent.change(screen.getByLabelText("확정일"), {
      target: { value: "2026-08-26" },
    });
    await user.click(screen.getByRole("button", { name: "기사·일정 저장" }));

    await waitFor(() =>
      expect(repository.saveSchedule).toHaveBeenCalledWith(
        VISIT_ID,
        {
          state_version: 7,
          synthetic_technician_id: ACTIVE_TECHNICIAN_ID,
          preferred_date: "2026-08-25",
          confirmed_date: "2026-08-26",
        },
        expect.objectContaining({
          correlationId: expect.any(String),
          idempotencyKey: expect.any(String),
        }),
      ),
    );
  });

  it("현재 배정 ID가 활성 목록 밖이면 값을 보존하되 새 저장은 차단한다", async () => {
    const user = userEvent.setup();
    renderPanel({ assignedTechnicianId: ASSIGNED_TECHNICIAN_ID });

    const technicianSelect = screen.getByLabelText("방문기사");
    const saveButton = screen.getByRole("button", { name: "기사·일정 저장" });

    expect(technicianSelect).toHaveValue(ASSIGNED_TECHNICIAN_ID);
    await user.click(technicianSelect);
    expect(
      screen.getByRole("option", { name: "현재 배정 기사 · 선택 목록 외" }),
    ).toHaveAttribute("aria-disabled", "true");
    expect(saveButton).toBeDisabled();

    await user.click(screen.getByRole("option", { name: "합성 기사 02 · 서울 합성 지사" }));
    expect(technicianSelect).toHaveValue(ACTIVE_TECHNICIAN_ID);
  });

  it.each([
    ["loading", "방문기사 목록을 불러오고 있습니다."],
    ["empty", "선택 가능한 합성 방문기사가 없습니다."],
    ["forbidden", "방문기사 목록을 조회할 권한이 없습니다."],
  ] as const)("%s 상태에서는 기사 선택과 저장을 차단한다", (status, message) => {
    renderPanel({ status, technicians: [] });

    expect(screen.getByLabelText("방문기사")).toBeDisabled();
    expect(screen.getByRole("button", { name: "기사·일정 저장" })).toBeDisabled();
    expect(screen.getByText(message)).toBeVisible();
  });

  it("기사 목록 오류에서 저장을 차단하고 목록 재시도를 제공한다", async () => {
    const user = userEvent.setup();
    const onRetryTechnicians = vi.fn();
    renderPanel({
      onRetryTechnicians,
      status: "error",
      technicians: [],
    });

    expect(screen.getByLabelText("방문기사")).toBeDisabled();
    expect(screen.getByRole("button", { name: "기사·일정 저장" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "방문기사 목록을 불러오지 못했습니다.",
    );

    await user.click(
      screen.getByRole("button", { name: "기사 목록 다시 불러오기" }),
    );
    expect(onRetryTechnicians).toHaveBeenCalledTimes(1);
  });
});

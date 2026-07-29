import { describe, expect, it } from "vitest";

import {
  mapWorkflowActionSuccess,
  mapWorkflowConflict,
  type WorkflowAllowedAction,
} from "../../src/features/workflow-action/model/workflowActionMapper";
import type {
  WorkflowActionSuccessDto,
  WorkflowConflictErrorDto,
} from "../../src/features/workflow-action/model/workflowActionDtos";

type TestActionCode = "SAVE" | "COMPLETE";
type TestStatus = "IN_PROGRESS" | "DONE";

const ACTION_CATALOG: readonly WorkflowAllowedAction<TestActionCode>[] = [
  {
    code: "SAVE",
    label: "저장",
    operationId: "save",
    style: "SECONDARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  {
    code: "COMPLETE",
    label: "완료",
    operationId: "complete",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "완료하시겠습니까?",
  },
];

describe("Workflow Action 응답 Mapper", () => {
  it("성공 allowed_actions 객체 배열을 화면 행동 객체로 변환한다", () => {
    const dto: WorkflowActionSuccessDto<TestActionCode> = {
      message: "저장 완료",
      state_version: 5,
      allowed_actions: [
        {
          code: "COMPLETE",
          label: "완료",
          operation_id: "complete",
          style: "PRIMARY",
          requires_confirmation: true,
          confirmation_message: "완료하시겠습니까?",
        },
      ],
    };

    expect(mapWorkflowActionSuccess(dto, "correlation-success")).toEqual({
      message: "저장 완료",
      stateVersion: 5,
      allowedActions: [ACTION_CATALOG[1]],
      correlationId: "correlation-success",
    });
  });

  it("STATE-CONFLICT-01의 행동 코드 배열로 최신 화면 행동을 복구한다", () => {
    const dto: WorkflowConflictErrorDto<TestActionCode> = {
      code: "STATE-CONFLICT-01",
      message: "최신 상태를 확인해 주세요.",
      details: {
        current_status: "IN_PROGRESS",
        current_state_version: 6,
        allowed_actions: ["SAVE"],
      },
    };

    expect(
      mapWorkflowConflict<TestActionCode, TestStatus>(
        dto,
        "correlation-conflict",
        ACTION_CATALOG,
      ),
    ).toMatchObject({
      conflictCode: "STATE-CONFLICT-01",
      currentStatus: "IN_PROGRESS",
      currentStateVersion: 6,
      allowedActionCodes: ["SAVE"],
      allowedActions: [ACTION_CATALOG[0]],
    });
  });

  it("DUPLICATE-EVENT-01의 빈 details를 상태 Snapshot으로 만들지 않는다", () => {
    const dto: WorkflowConflictErrorDto<TestActionCode> = {
      code: "DUPLICATE-EVENT-01",
      message: "같은 키에 다른 요청이 사용되었습니다.",
      details: {},
    };
    const result = mapWorkflowConflict<TestActionCode, TestStatus>(
      dto,
      "correlation-duplicate",
      ACTION_CATALOG,
    );

    expect(result).toEqual({
      kind: "CONFLICT",
      conflictCode: "DUPLICATE-EVENT-01",
      message: "같은 키에 다른 요청이 사용되었습니다.",
      correlationId: "correlation-duplicate",
    });
    expect(result).not.toHaveProperty("currentStateVersion");
    expect(result).not.toHaveProperty("allowedActions");
  });
});

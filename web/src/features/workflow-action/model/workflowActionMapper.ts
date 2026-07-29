import type {
  DuplicateEventErrorDto,
  StateConflictErrorDto,
  WorkflowActionSuccessDto,
  WorkflowAllowedActionDto,
  WorkflowConflictErrorDto,
} from "./workflowActionDtos";

export interface WorkflowAllowedAction<TCode extends string = string> {
  code: TCode;
  label: string;
  operationId: string;
  style: "PRIMARY" | "SECONDARY" | "DESTRUCTIVE";
  requiresConfirmation: boolean;
  confirmationMessage: string | null;
}

export interface WorkflowActionSuccess<TCode extends string = string> {
  message: string;
  stateVersion: number;
  allowedActions: readonly WorkflowAllowedAction<TCode>[];
  correlationId: string;
}

export interface StateConflict<TCode extends string, TStatus extends string> {
  kind: "CONFLICT";
  conflictCode: "STATE-CONFLICT-01";
  message: string;
  currentStatus: TStatus | null;
  currentStateVersion: number;
  allowedActionCodes: readonly TCode[];
  allowedActions: readonly WorkflowAllowedAction<TCode>[];
  correlationId: string;
}

export interface DuplicateEventConflict {
  kind: "CONFLICT";
  conflictCode: "DUPLICATE-EVENT-01";
  message: string;
  correlationId: string;
}

export type WorkflowConflict<TCode extends string, TStatus extends string> =
  | StateConflict<TCode, TStatus>
  | DuplicateEventConflict;

export function mapWorkflowAllowedAction<TCode extends string>(
  dto: WorkflowAllowedActionDto<TCode>,
): WorkflowAllowedAction<TCode> {
  return {
    code: dto.code,
    label: dto.label,
    operationId: dto.operation_id,
    style: dto.style,
    requiresConfirmation: dto.requires_confirmation,
    confirmationMessage: dto.confirmation_message,
  };
}

export function mapWorkflowActionSuccess<TCode extends string>(
  dto: WorkflowActionSuccessDto<TCode>,
  correlationId: string,
): WorkflowActionSuccess<TCode> {
  return {
    message: dto.message,
    stateVersion: dto.state_version,
    allowedActions: dto.allowed_actions.map(mapWorkflowAllowedAction),
    correlationId,
  };
}

function mapStateConflict<TCode extends string, TStatus extends string>(
  dto: StateConflictErrorDto<TCode>,
  correlationId: string,
  actionCatalog: readonly WorkflowAllowedAction<TCode>[],
): StateConflict<TCode, TStatus> {
  const allowedActionCodeSet = new Set(dto.details.allowed_actions);

  return {
    kind: "CONFLICT",
    conflictCode: dto.code,
    message: dto.message,
    currentStatus: dto.details.current_status as TStatus | null,
    currentStateVersion: dto.details.current_state_version,
    allowedActionCodes: dto.details.allowed_actions,
    allowedActions: actionCatalog.filter((action) =>
      allowedActionCodeSet.has(action.code),
    ),
    correlationId,
  };
}

function mapDuplicateEvent(
  dto: DuplicateEventErrorDto,
  correlationId: string,
): DuplicateEventConflict {
  return {
    kind: "CONFLICT",
    conflictCode: dto.code,
    message: dto.message,
    correlationId,
  };
}

export function mapWorkflowConflict<TCode extends string, TStatus extends string>(
  dto: WorkflowConflictErrorDto<TCode>,
  correlationId: string,
  actionCatalog: readonly WorkflowAllowedAction<TCode>[],
): WorkflowConflict<TCode, TStatus> {
  return dto.code === "STATE-CONFLICT-01"
    ? mapStateConflict<TCode, TStatus>(dto, correlationId, actionCatalog)
    : mapDuplicateEvent(dto, correlationId);
}

export interface WorkflowAllowedActionDto<TCode extends string = string> {
  code: TCode;
  label: string;
  operation_id: string;
  style: "PRIMARY" | "SECONDARY" | "DESTRUCTIVE";
  requires_confirmation: boolean;
  confirmation_message: string | null;
}

export interface WorkflowActionSuccessDto<TCode extends string = string> {
  message: string;
  state_version: number;
  allowed_actions: readonly WorkflowAllowedActionDto<TCode>[];
}

export interface StateConflictErrorDto<TCode extends string = string> {
  code: "STATE-CONFLICT-01";
  message: string;
  details: {
    current_status: string | null;
    current_state_version: number;
    allowed_actions: readonly TCode[];
  };
}

export interface DuplicateEventErrorDto {
  code: "DUPLICATE-EVENT-01";
  message: string;
  details: Record<string, never>;
}

export type WorkflowConflictErrorDto<TCode extends string = string> =
  | StateConflictErrorDto<TCode>
  | DuplicateEventErrorDto;

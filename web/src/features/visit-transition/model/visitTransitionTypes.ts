export type VisitMockAction =
  | "CREATE_VISIT_REQUEST"
  | "SAVE_SCHEDULE"
  | "CONFIRM_VISIT";

export interface VisitTransitionValues {
  visitReason: string;
  preferredDate: string;
  technicianId: string;
  inspectionPriority: string;
  notes: string;
  safetyNotes: string;
  confirmedDate: string;
}

export type VisitTransitionField = keyof VisitTransitionValues;
export type VisitTransitionErrors = Partial<
  Record<VisitTransitionField, string>
>;

export interface MockTechnician {
  id: string;
  name: string;
  team: string;
  area: string;
}

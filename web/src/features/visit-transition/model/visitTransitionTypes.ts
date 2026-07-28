export type VisitMockAction = "SAVE_SCHEDULE" | "CONFIRM_VISIT";

export interface VisitTransitionValues {
  visitReason: string;
  desiredAt: string;
  technicianId: string;
  inspectionPriority: string;
  notes: string;
  safetyNotes: string;
  confirmedAt: string;
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

import type {
  MockTechnician,
  VisitTransitionValues,
} from "./visitTransitionTypes";

export const MOCK_TECHNICIANS: readonly MockTechnician[] = [
  {
    id: "STAFF-TECH-01",
    name: "오세훈",
    team: "서울 서부 방문팀",
    area: "마포·은평·서대문",
  },
  {
    id: "STAFF-TECH-02",
    name: "이도윤",
    team: "서울 동부 방문팀",
    area: "광진·성동·동대문",
  },
];

export function createVisitTransitionMockValues(
  symptomSummary: string,
): VisitTransitionValues {
  return {
    visitReason: "상담 안내 후에도 증상이 지속되어 현장 점검이 필요합니다.",
    desiredAt: "",
    technicianId: "",
    inspectionPriority: symptomSummary,
    notes: "고객 원문과 상담 확인 내용을 참고해 제품 상태를 점검해 주세요.",
    safetyNotes: "현장 점검 전 사용 제한 상태와 전원·원수 밸브 조치를 재확인해 주세요.",
    confirmedAt: "",
  };
}

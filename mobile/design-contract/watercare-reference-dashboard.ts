export type WaterCareRole = "customer" | "technician";

export interface DashboardPalette {
  accent: string;
  accentSecondary: string;
  accentSoft: string;
  backgroundStart: string;
  backgroundEnd: string;
  textStrong: string;
  textMuted: string;
  success: string;
  warning: string;
  danger: string;
}

export interface DashboardLayout {
  horizontalPaddingDp: number;
  sectionGapDp: number;
  heroHeightDp: number;
  statusTileHeightDp: number;
  actionTileHeightDp: number;
  cardRadiusDp: number;
  bottomNavigationFixed: boolean;
  bottomNavigationHeightDp: number;
  titleWeight: "bold" | "semibold";
  bodyFontFamily: "system-sans";
  useTextGlyphIcons: boolean;
  backgroundAsset: string;
  statusLabelMaxLines: 2;
  actionLabelMaxLines: 2;
  heroTextMaxLines: 3;
  panelOpacityStrong: number;
  panelOpacityNormal: number;
  buttonOpacity: number;
  backgroundImageOpacity: number;
  glassBorderOpacity: number;
  fullTransparentSurface: boolean;
  primaryButtonAccentOnly: boolean;
  customerPrimaryButtonColor: string;
  technicianPrimaryButtonColor: string;
}

export interface DashboardAction {
  icon: string;
  label: string;
  subtitle: string;
  enabled: boolean;
}

export interface DashboardDefinition {
  role: WaterCareRole;
  roleLabel: string;
  statusSection: string;
  quickActions: readonly DashboardAction[];
  bottomNavigation: readonly string[];
  palette: DashboardPalette;
  layout: DashboardLayout;
}

const sharedLayout: DashboardLayout = {
  horizontalPaddingDp: 16,
  sectionGapDp: 14,
  heroHeightDp: 226,
  statusTileHeightDp: 106,
  actionTileHeightDp: 108,
  cardRadiusDp: 24,
  bottomNavigationFixed: true,
  bottomNavigationHeightDp: 68,
  titleWeight: "semibold",
  bodyFontFamily: "system-sans",
  useTextGlyphIcons: false,
  backgroundAsset: "water-image",
  statusLabelMaxLines: 2,
  actionLabelMaxLines: 2,
  heroTextMaxLines: 3,
  panelOpacityStrong: 0.24,
  panelOpacityNormal: 0.14,
  buttonOpacity: 0.18,
  backgroundImageOpacity: 1.0,
  glassBorderOpacity: 0.86,
  fullTransparentSurface: true,
  primaryButtonAccentOnly: true,
  customerPrimaryButtonColor: "#248CFF",
  technicianPrimaryButtonColor: "#0FB9AA",
};

export const customerDashboard: DashboardDefinition = {
  role: "customer",
  roleLabel: "고객용",
  statusSection: "홈 상태",
  quickActions: [
    { icon: "intake", label: "문진 시작", subtitle: "증상 입력", enabled: true },
    { icon: "care", label: "안심 케어", subtitle: "안전 안내", enabled: true },
    { icon: "schedule", label: "방문 일정", subtitle: "API 준비 중", enabled: false },
    { icon: "product", label: "제품 정보", subtitle: "제품 확인", enabled: true },
  ],
  bottomNavigation: ["홈", "제품", "관리", "알림", "마이"],
  palette: {
    accent: "#4E9BFF",
    accentSecondary: "#A678FF",
    accentSoft: "rgba(78, 155, 255, 0.20)",
    backgroundStart: "#F8FCFF",
    backgroundEnd: "#F7F4FF",
    textStrong: "#12262B",
    textMuted: "#61747C",
    success: "#32BE9B",
    warning: "#E2A141",
    danger: "#E95570",
  },
  layout: sharedLayout,
};

export const technicianDashboard: DashboardDefinition = {
  role: "technician",
  roleLabel: "방문기사용",
  statusSection: "방문 상태",
  quickActions: [
    { icon: "visits", label: "방문 목록", subtitle: "일정 확인", enabled: true },
    { icon: "precheck", label: "사전 점검", subtitle: "읽기 전용", enabled: true },
    { icon: "route", label: "경로 확인", subtitle: "개인 확장", enabled: false },
    { icon: "report", label: "작업 기록", subtitle: "API 준비 중", enabled: false },
  ],
  bottomNavigation: ["홈", "방문", "작업", "알림", "마이"],
  palette: {
    accent: "#18B8A8",
    accentSecondary: "#66D6C7",
    accentSoft: "rgba(24, 184, 168, 0.20)",
    backgroundStart: "#F7FFFD",
    backgroundEnd: "#F2FAFC",
    textStrong: "#123136",
    textMuted: "#5F777A",
    success: "#18B8A8",
    warning: "#E5A146",
    danger: "#EA5B70",
  },
  layout: sharedLayout,
};

export const dashboardByRole: Record<WaterCareRole, DashboardDefinition> = {
  customer: customerDashboard,
  technician: technicianDashboard,
};

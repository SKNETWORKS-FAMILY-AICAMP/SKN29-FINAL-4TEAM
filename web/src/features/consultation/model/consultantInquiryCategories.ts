export interface InquiryCategoryNode {
  label: string;
  children: readonly {
    label: string;
    children: readonly string[];
  }[];
}

export interface InquiryCategoryPath {
  major: string;
  middle: string;
  minor: string;
}

export const INQUIRY_CATEGORY_TREE: readonly InquiryCategoryNode[] = [
  {
    label: "제품 작동 이상",
    children: [
      {
        label: "출수 문제",
        children: ["물이 안 나옴", "출수량이 적음", "출수량이 다름", "연속 출수 문제"],
      },
      {
        label: "냉수 문제",
        children: ["냉수가 미지근함", "냉수 기능 이상", "냉수 준비 지연"],
      },
      {
        label: "온수 문제",
        children: ["온수가 안 나옴", "온도가 낮음", "온수 출수량이 적음", "온수 초기화 필요"],
      },
      {
        label: "소음·진동",
        children: ["출수 소음", "지속 소음", "팬·컴프레서 소음", "진동"],
      },
      {
        label: "버튼·표시",
        children: ["버튼 작동 이상", "화면·LED 이상", "알림음 이상", "점검 문구 표시"],
      },
      {
        label: "배수·물받이",
        children: ["배수량 이상", "물받이 넘침", "퇴수구 이상"],
      },
    ],
  },
  {
    label: "물·위생 문제",
    children: [
      {
        label: "물맛·냄새",
        children: ["물맛 이상", "소독약 냄새", "장기 미사용 후 냄새", "조리수 맛 이상"],
      },
      {
        label: "물의 상태",
        children: ["기포 발생", "뿌연 물", "하얀 물", "이물질·부유물"],
      },
      {
        label: "취수구·물받이",
        children: ["취수구 오염", "물받이 오염", "청소 방법"],
      },
      {
        label: "살균·위생 관리",
        children: ["직수관 안심케어", "UV 살균", "살균키트 청소"],
      },
    ],
  },
  {
    label: "안전·긴급 문제",
    children: [
      {
        label: "누수",
        children: ["제품 아래 누수", "연결부 누수", "필터 교체 후 누수", "재사용 시 누수"],
      },
      {
        label: "전기 위험",
        children: ["감전 위험", "차단기 작동", "전원 코드 이상"],
      },
      {
        label: "화재 위험",
        children: ["타는 냄새", "연기 발생", "제품 과열"],
      },
      {
        label: "온수 위험",
        children: ["순간온수 점검", "스팀 분사", "뜨거운 물 튐"],
      },
    ],
  },
  {
    label: "필터·정기 관리",
    children: [
      {
        label: "필터 교체",
        children: ["교체 시기", "교체 방법", "필터 수명", "교체 후 이상"],
      },
      {
        label: "필터 배송·구매",
        children: ["필터 배송일", "배송지 변경", "필터·소모품 구매"],
      },
      {
        label: "정기점검",
        children: ["점검 시기", "방문 일정", "관리 기사 미방문"],
      },
      {
        label: "장기 미사용",
        children: ["휴가 전 조치", "단기 미사용", "장기 미사용 후 재사용"],
      },
    ],
  },
  {
    label: "사용 방법·기능",
    children: [
      {
        label: "출수 설정",
        children: ["출수 온도 설정", "출수 용량 설정", "연속 출수 설정", "메모리 출수"],
      },
      {
        label: "잠금·조작",
        children: ["냉수·온수 잠금", "버튼 사용법", "초기화 방법"],
      },
      {
        label: "앱·IoT",
        children: ["앱 연결", "Wi-Fi 연결", "원격 조작", "앱 필터 확인"],
      },
      {
        label: "제품 기능 문의",
        children: ["정수 방식", "제거수·조리수", "지원 기능", "제품 사양"],
      },
    ],
  },
  {
    label: "설치·이전",
    children: [
      {
        label: "신규 설치",
        children: ["설치 후 사용 준비", "초기 물빼기", "설치 직후 냉·온수"],
      },
      {
        label: "설치 환경",
        children: ["수압", "지하수", "전압·콘센트", "설치 장소"],
      },
      {
        label: "호스·밸브",
        children: ["원수 밸브", "조리수 밸브", "호스 꺾임·연결"],
      },
      {
        label: "이전 설치",
        children: ["이사·이전 설치", "위치 변경", "제품 운반"],
      },
    ],
  },
  {
    label: "서비스 문의",
    children: [
      {
        label: "방문·A/S",
        children: ["기사 방문 요청", "수리 상태", "재방문 요청"],
      },
      {
        label: "부품·보증",
        children: ["부품 구매", "제품보증", "폐제품 처리"],
      },
    ],
  },
  {
    label: "기타",
    children: [
      {
        label: "복합·미분류",
        children: ["여러 증상", "제품 모델 미확인", "분류 필요"],
      },
    ],
  },
];

interface CategoryRule extends InquiryCategoryPath {
  keywords: readonly string[];
  requiredKeywords?: readonly string[];
}

const CATEGORY_RULES: readonly CategoryRule[] = [
  { major: "안전·긴급 문제", middle: "화재 위험", minor: "타는 냄새", keywords: ["타는 냄새"] },
  { major: "안전·긴급 문제", middle: "화재 위험", minor: "연기 발생", keywords: ["연기"] },
  { major: "안전·긴급 문제", middle: "전기 위험", minor: "감전 위험", keywords: ["전기가 느껴", "감전", "누전"] },
  { major: "안전·긴급 문제", middle: "전기 위험", minor: "차단기 작동", keywords: ["차단기"] },
  { major: "안전·긴급 문제", middle: "온수 위험", minor: "순간온수 점검", keywords: ["순간온수", "모듈 점검"] },
  { major: "안전·긴급 문제", middle: "온수 위험", minor: "스팀 분사", keywords: ["스팀"] },
  { major: "안전·긴급 문제", middle: "온수 위험", minor: "뜨거운 물 튐", keywords: ["뜨거운 물", "물이 튀"] },
  { major: "안전·긴급 문제", middle: "누수", minor: "필터 교체 후 누수", keywords: ["필터교체 후 누수", "필터 교체 후 누수"] },
  { major: "안전·긴급 문제", middle: "누수", minor: "연결부 누수", keywords: ["연결부", "호스에서", "한두 방울"] },
  { major: "안전·긴급 문제", middle: "누수", minor: "재사용 시 누수", keywords: ["누수가 재발", "다시 사용"] },
  { major: "안전·긴급 문제", middle: "누수", minor: "제품 아래 누수", keywords: ["누수", "물이 고", "물 새", "물샘", "아래에 물"] },
  { major: "물·위생 문제", middle: "물맛·냄새", minor: "장기 미사용 후 냄새", keywords: ["집을 비운", "오랜기간", "오랫동안", "장기 미사용"] },
  { major: "물·위생 문제", middle: "물맛·냄새", minor: "소독약 냄새", keywords: ["소독약"] },
  { major: "물·위생 문제", middle: "물맛·냄새", minor: "조리수 맛 이상", keywords: ["물맛", "맛이"], requiredKeywords: ["조리수"] },
  { major: "물·위생 문제", middle: "물맛·냄새", minor: "물맛 이상", keywords: ["냄새", "물맛", "맛이"] },
  { major: "물·위생 문제", middle: "물의 상태", minor: "기포 발생", keywords: ["기포", "공기방울"] },
  { major: "물·위생 문제", middle: "물의 상태", minor: "이물질·부유물", keywords: ["이물질", "부유물", "까만"] },
  { major: "물·위생 문제", middle: "물의 상태", minor: "뿌연 물", keywords: ["뿌옇", "하얗"] },
  { major: "사용 방법·기능", middle: "앱·IoT", minor: "Wi-Fi 연결", keywords: ["와이파이", "Wi-Fi", "WiFi"] },
  { major: "사용 방법·기능", middle: "앱·IoT", minor: "원격 조작", keywords: ["원격", "IOT", "IoT"] },
  { major: "사용 방법·기능", middle: "앱·IoT", minor: "앱 필터 확인", keywords: ["앱으로 필터", "앱에서 필터"] },
  { major: "사용 방법·기능", middle: "앱·IoT", minor: "앱 연결", keywords: ["앱", "휴대폰"] },
  { major: "필터·정기 관리", middle: "장기 미사용", minor: "휴가 전 조치", keywords: ["휴가", "집을 비"] },
  { major: "필터·정기 관리", middle: "정기점검", minor: "관리 기사 미방문", keywords: ["왜 안오", "미방문"] },
  { major: "필터·정기 관리", middle: "필터 배송·구매", minor: "필터 배송일", keywords: ["배송", "배송지"], requiredKeywords: ["필터"] },
  { major: "필터·정기 관리", middle: "필터 교체", minor: "교체 시기", keywords: ["주기", "수명", "유효 기간"], requiredKeywords: ["필터"] },
  { major: "필터·정기 관리", middle: "필터 교체", minor: "교체 방법", keywords: ["교체", "바꾸"], requiredKeywords: ["필터"] },
  { major: "제품 작동 이상", middle: "버튼·표시", minor: "점검 문구 표시", keywords: ["LCD", "점검 문구", "화면에"] },
  { major: "제품 작동 이상", middle: "소음·진동", minor: "진동", keywords: ["진동"] },
  { major: "제품 작동 이상", middle: "소음·진동", minor: "팬·컴프레서 소음", keywords: ["팬", "컴프레서", "윙"] },
  { major: "제품 작동 이상", middle: "소음·진동", minor: "출수 소음", keywords: ["출수할 때", "툭 소리"] },
  { major: "제품 작동 이상", middle: "소음·진동", minor: "지속 소음", keywords: ["소음", "소리"] },
  { major: "제품 작동 이상", middle: "냉수 문제", minor: "냉수가 미지근함", keywords: ["미지근", "덜 차가", "차갑지"], requiredKeywords: ["냉수"] },
  { major: "제품 작동 이상", middle: "온수 문제", minor: "온수가 안 나옴", keywords: ["안 나오", "나오지"], requiredKeywords: ["온수"] },
  { major: "제품 작동 이상", middle: "온수 문제", minor: "온도가 낮음", keywords: ["뜨겁지", "미지근"], requiredKeywords: ["온수"] },
  { major: "제품 작동 이상", middle: "출수 문제", minor: "물이 안 나옴", keywords: ["물이 안 나오", "물이 안 나와", "물 안 나오", "물 안 나와", "출수되지"] },
  { major: "제품 작동 이상", middle: "출수 문제", minor: "출수량이 다름", keywords: ["용량이 달", "출수 용량"] },
  { major: "제품 작동 이상", middle: "출수 문제", minor: "출수량이 적음", keywords: ["물줄기", "출수량", "약해", "한 컵 받는 시간"] },
  { major: "설치·이전", middle: "설치 환경", minor: "수압", keywords: ["수압"] },
  { major: "설치·이전", middle: "호스·밸브", minor: "호스 꺾임·연결", keywords: ["호스", "밸브"] },
  { major: "설치·이전", middle: "이전 설치", minor: "이사·이전 설치", keywords: ["이사", "이전 설치"] },
  { major: "서비스 문의", middle: "방문·A/S", minor: "기사 방문 요청", keywords: ["기사", "방문", "A/S", "AS"] },
];

const FALLBACK_CATEGORY: InquiryCategoryPath = {
  major: "기타",
  middle: "복합·미분류",
  minor: "분류 필요",
};

export function classifyInquiryCategory(summary: string): InquiryCategoryPath {
  return (
    CATEGORY_RULES.find((rule) =>
      rule.keywords.some((keyword) => summary.includes(keyword)) &&
      (rule.requiredKeywords?.every((keyword) => summary.includes(keyword)) ??
        true),
    ) ?? FALLBACK_CATEGORY
  );
}

const CONSULTANT_DASHBOARD_DATE_FORMATTER = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function getConsultantDashboardDate(date: Date) {
  const parts = CONSULTANT_DASHBOARD_DATE_FORMATTER.formatToParts(date);
  const values = Object.fromEntries(
    parts.map(({ type, value }) => [type, value]),
  );

  return {
    dateTime: `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}`,
    label: `${values.year}. ${values.month}. ${values.day}. (${values.weekday}) ${values.hour}:${values.minute}`,
  };
}

// Hand-rolled — no date-fns/dayjs (webapp-spec S11: no library beyond what a
// branch's spec names, and S4 only names react-markdown).
// 직접 구현 — date-fns/dayjs 미사용 (webapp-spec S11: 브랜치 명세가 지목한
// 라이브러리 외 추가 금지, S4가 명시한 건 react-markdown뿐).
export function formatRelativeTime(input: string | Date, now: Date = new Date()): string {
  const then = typeof input === "string" ? new Date(input) : input;
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return "방금";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}시간 전`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay}일 전`;

  const sameYear = then.getFullYear() === now.getFullYear();
  return sameYear
    ? `${then.getMonth() + 1}월 ${then.getDate()}일`
    : `${then.getFullYear()}.${String(then.getMonth() + 1).padStart(2, "0")}.${String(then.getDate()).padStart(2, "0")}`;
}

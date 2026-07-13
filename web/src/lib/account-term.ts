// FE mirror of api/app/core/account_term.py's add_months (month arithmetic
// with end-of-month clamping) — used only to prefill the "+7개월" quick
// button; the value the server stores is whatever the admin submits.
// api/app/core/account_term.py add_months의 FE 미러(말일 클램프 달력 월
// 연산) — "+7개월" 퀵버튼 프리필에만 쓰이고, 서버 저장값은 관리자가 제출한
// 값 그대로다.

export const ACCOUNT_TERM_MONTHS = 7;

export function addMonthsClamped(date: Date, months: number): Date {
  const monthIndex = date.getFullYear() * 12 + date.getMonth() + months;
  const year = Math.floor(monthIndex / 12);
  const month = monthIndex % 12;
  const lastDay = new Date(year, month + 1, 0).getDate();
  return new Date(year, month, Math.min(date.getDate(), lastDay));
}

export function toDateInputValue(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

// Admin picks a calendar date; the account should stay valid through that
// whole day in Korea, so submit end-of-day KST.
// 관리자는 달력 날짜를 고른다 — 그 날 하루가 한국 시간으로 끝날 때까지
// 유효해야 하므로 KST 자정 직전으로 제출한다.
export function dateInputToExpiresAt(value: string): string {
  return `${value}T23:59:59+09:00`;
}

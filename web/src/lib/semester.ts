// Semester arithmetic in KST (webapp-spec S19/S21): term 1 starts 3/1, term
// 2 starts 9/1, so Jan–Feb still belong to the previous year's term 2.
// KST 기준 학기 연산 (webapp-spec S19/S21): 1학기 시작 3/1, 2학기 시작 9/1 —
// 1~2월은 전년도 2학기에 속한다.

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

export function currentSemester(now: Date = new Date()): string {
  const kst = new Date(now.getTime() + KST_OFFSET_MS);
  const year = kst.getUTCFullYear();
  const month = kst.getUTCMonth() + 1;
  if (month < 3) return `${year - 1}-2`;
  return month < 9 ? `${year}-1` : `${year}-2`;
}

// Fixed "YYYY-N" format makes plain string comparison chronological.
// "YYYY-N" 고정 포맷이라 단순 문자열 비교가 시간순이 된다.
export function isPastSemester(semester: string, now: Date = new Date()): boolean {
  return semester < currentSemester(now);
}

export function nextSemester(semester: string): string {
  const [year, term] = semester.split("-");
  return term === "1" ? `${year}-2` : `${Number(year) + 1}-1`;
}

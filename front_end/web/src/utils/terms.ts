export interface TermOption {
  label: string;
  value: string;
}

function getAcademicStartYear(date = new Date()) {
  const month = date.getMonth() + 1;
  return month >= 9 ? date.getFullYear() : date.getFullYear() - 1;
}

export function getCurrentTerm(date = new Date()) {
  const month = date.getMonth() + 1;
  const startYear = getAcademicStartYear(date);
  const semester = month >= 9 ? 1 : 2;
  return `${startYear}-${startYear + 1}-${semester}`;
}

export function getEnrollmentYear(username: string | null) {
  const match = username?.match(/^(\d{2})/);
  if (!match) {
    return getAcademicStartYear() - 4;
  }
  return 2000 + Number(match[1]);
}

export function getTermOptions(username: string | null): TermOption[] {
  const startYear = getEnrollmentYear(username);
  const currentStartYear = getAcademicStartYear();
  const options: TermOption[] = [];

  for (let year = startYear; year <= currentStartYear; year += 1) {
    for (const semester of [1, 2]) {
      const value = `${year}-${year + 1}-${semester}`;
      if (value <= getCurrentTerm()) {
        options.push({ label: value, value });
      }
    }
  }

  return options.reverse();
}

export function getDefaultTerm(username: string | null) {
  const options = getTermOptions(username);
  return options[0]?.value ?? getCurrentTerm();
}

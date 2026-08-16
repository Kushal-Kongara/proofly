/**
 * Shared formatting for date-only values (`YYYY-MM-DD`, e.g. Pydantic
 * `date` fields like `as_of_date`, `event_date`, EAD/visa/O-1 evidence
 * dates). These values carry no time-of-day or timezone — they mean the
 * same calendar date everywhere.
 *
 * `new Date("2027-06-30")` (or `"2027-06-30T00:00:00Z"`) parses as UTC
 * midnight; formatting that with `toLocaleDateString()` in a timezone
 * behind UTC (e.g. America/Los_Angeles) rolls it back to June 29. Every
 * date-only display in the app must go through `formatDateOnly` (or
 * `parseDateOnly`) instead of calling `new Date()`/`toLocaleDateString()`
 * directly, so the calendar date shown never depends on the viewer's
 * timezone.
 *
 * Real timestamps (e.g. `VaultDocument.created_at`) are a different kind
 * of value — an actual instant that legitimately should render in the
 * viewer's local time — and must keep using `new Date()`/
 * `toLocaleString()` as-is; this module is only for date-only fields.
 */

const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * Parses a `YYYY-MM-DD` string into a `Date` anchored at UTC midnight for
 * that exact calendar date, with no local-timezone conversion applied at
 * parse time. Returns `null` if `value` isn't in `YYYY-MM-DD` form.
 */
export function parseDateOnly(value: string): Date | null {
  const match = DATE_ONLY_PATTERN.exec(value);
  if (!match) return null;

  const [, year, month, day] = match;
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
}

const DEFAULT_FORMAT_OPTIONS: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "long",
  day: "numeric",
};

/**
 * Formats a date-only (`YYYY-MM-DD`) value for display. Always formats in
 * the UTC calendar date the string names — never the viewer's local
 * timezone — so `"2027-06-30"` always reads "June 30, 2027" regardless of
 * where the browser is running.
 *
 * Returns `"—"` for `null`/`undefined`/empty, and the raw value unchanged
 * if it isn't valid `YYYY-MM-DD`.
 */
export function formatDateOnly(
  value: string | null | undefined,
  options: Intl.DateTimeFormatOptions = DEFAULT_FORMAT_OPTIONS,
): string {
  if (!value) return "—";

  const parsed = parseDateOnly(value);
  if (!parsed) return value;

  return parsed.toLocaleDateString(undefined, { ...options, timeZone: "UTC" });
}

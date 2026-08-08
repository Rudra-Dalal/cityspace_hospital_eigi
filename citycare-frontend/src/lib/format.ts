import type { Appointment } from "./api";

export function toDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseDateKey(value?: string | null): Date | null {
  if (!value) return null;
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDate(value?: string | null): string {
  const date = parseDateKey(value);
  if (!date) return value ?? "—";
  return date.toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatShortDate(value?: string | null): string {
  const date = parseDateKey(value);
  if (!date) return value ?? "—";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function isCancelled(appointment: Appointment): boolean {
  return (appointment.status ?? "").toString().toLowerCase().includes("cancel");
}

export function isUpcoming(appointment: Appointment): boolean {
  const date = parseDateKey(appointment.date);
  if (!date) return true;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return date.getTime() >= today.getTime();
}

export function isToday(value?: string | null): boolean {
  const date = parseDateKey(value);
  if (!date) return false;
  return toDateKey(date) === toDateKey(new Date());
}

export function nextDays(count: number): Date[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Array.from({ length: count }, (_, index) => {
    const day = new Date(today);
    day.setDate(today.getDate() + index);
    return day;
  });
}

export function personName(
  value: { first_name?: string | null; last_name?: string | null } | null | undefined,
  fallback = "—",
): string {
  if (!value) return fallback;
  const name = `${value.first_name ?? ""} ${value.last_name ?? ""}`.trim();
  return name || fallback;
}

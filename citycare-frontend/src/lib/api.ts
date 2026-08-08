export const API_BASE_URL =
  (import.meta.env['VITE_API_BASE_URL'] as string | undefined) ?? "http://localhost:8000";

export type Role = "customer" | "doctor" | "hospital_manager" | "super_admin";

export type User = {
  id: number | string;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  role: Role;
  hospital_id?: number | string | null;
  is_active?: boolean;
};

export type Appointment = {
  id: number | string;
  date: string;
  slot: string;
  reason?: string | null;
  status?: string | null;
  temperature?: number | string | null;
  symptoms?: string[] | null;
  patient_name?: string | null;
  doctor_name?: string | null;
  customer?: Partial<User> | null;
  doctor?: Partial<User> | null;
};

export type Hospital = {
  id: number | string;
  name: string;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  status?: string | null;
  is_active?: boolean;
};

export type LoginResponse = { access_token: string; user: User };

export const TOKEN_KEY = "citycare.token";
export const USER_KEY = "citycare.user";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "string" && payload.trim()) return payload;
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown; message?: unknown }).detail ?? (payload as { message?: unknown }).message;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    }
  }
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getStoredToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    const init: RequestInit = { method, headers };
    if (body !== undefined) init.body = JSON.stringify(body);
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError("Can't reach the CityCare server. Please try again.", 0);
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(extractMessage(payload, `Request failed (${response.status})`), response.status);
  }
  return payload as T;
}

/* ---------- Endpoints ---------- */

export const authApi = {
  signup: (body: {
    first_name: string;
    last_name: string;
    email: string;
    mobile: string;
    password: string;
  }) => apiFetch<User>("/auth/signup", { method: "POST", body, auth: false }),
  login: (body: { email: string; password: string }) =>
    apiFetch<LoginResponse>("/auth/login", { method: "POST", body, auth: false }),
};

export const appointmentsApi = {
  freeSlots: (date: string) =>
    apiFetch<{ free_slots: string[] }>(`/appointments/free-slots?date=${encodeURIComponent(date)}`),
  create: (body: {
    date: string;
    slot: string;
    reason: string;
    temperature: number;
    symptoms: string[];
  }) => apiFetch<Appointment>("/appointments", { method: "POST", body }),
  mine: () => apiFetch<Appointment[]>("/appointments/my"),
  cancel: (id: number | string) =>
    apiFetch<Appointment>(`/appointments/${id}/cancel`, { method: "PATCH" }),
};

export const doctorApi = {
  info: () => apiFetch<Record<string, unknown>>("/doctor/info"),
  schedule: () => apiFetch<Appointment[]>("/doctor/schedule"),
  stats: () => apiFetch<Record<string, unknown>>("/doctor/stats"),
};

export const managerApi = {
  hospital: () => apiFetch<Hospital>("/manager/hospital"),
  updateHospital: (body: Partial<Hospital>) =>
    apiFetch<Hospital>("/manager/hospital", { method: "PATCH", body }),
  doctors: () => apiFetch<User[]>("/manager/doctors"),
  appointments: () => apiFetch<Appointment[]>("/manager/appointments"),
};

export const adminApi = {
  hospitals: () => apiFetch<Hospital[]>("/admin/hospitals"),
  createHospital: (body: Partial<Hospital>) =>
    apiFetch<Hospital>("/admin/hospitals", { method: "POST", body }),
  updateHospital: (id: number | string, body: Partial<Hospital>) =>
    apiFetch<Hospital>(`/admin/hospitals/${id}`, { method: "PATCH", body }),
  users: () => apiFetch<User[]>("/admin/users"),
  createManager: (body: Record<string, unknown>) =>
    apiFetch<User>("/admin/users/manager", { method: "POST", body }),
  createDoctor: (body: Record<string, unknown>) =>
    apiFetch<User>("/admin/users/doctor", { method: "POST", body }),
  deactivateUser: (id: number | string) =>
    apiFetch<User>(`/admin/users/${id}/deactivate`, { method: "PATCH" }),
};

/* ---------- helpers ---------- */

export function asList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === "object") {
    for (const key of ["items", "data", "results", "appointments", "doctors", "users", "hospitals"]) {
      const value = (payload as Record<string, unknown>)[key];
      if (Array.isArray(value)) return value as T[];
    }
  }
  return [];
}

export const ROLE_HOME: Record<Role, string> = {
  customer: "/patient/dashboard",
  doctor: "/doctor/dashboard",
  hospital_manager: "/manager/dashboard",
  super_admin: "/admin/dashboard",
};

export const ROLE_LABEL: Record<Role, string> = {
  customer: "Patient",
  doctor: "Doctor",
  hospital_manager: "Hospital manager",
  super_admin: "Super admin",
};

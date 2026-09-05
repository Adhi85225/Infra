/**
 * API client.
 *
 * Session model (mirrors the backend):
 *  - the access token lives in memory only -- never in localStorage, so an XSS
 *    bug cannot exfiltrate a token that survives a reload;
 *  - the refresh token is an httpOnly cookie the JS never sees;
 *  - cookie-authenticated calls (`/auth/refresh`, `/auth/logout`) echo the
 *    readable CSRF cookie in a header (double-submit).
 *
 * A 401 triggers exactly one refresh attempt, and concurrent 401s share it.
 */

import type { SessionResponse } from './types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');
const API_PREFIX = '/api/v1';
const CSRF_COOKIE = 'ght_csrf';
const CSRF_HEADER = 'X-CSRF-Token';

/** Shape of every error the API returns. */
export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? {};
  }

  /** Per-field messages, for rendering inline validation errors. */
  fieldErrors(): Record<string, string> {
    const result: Record<string, string> = {};
    const fields = this.details.fields;
    if (fields && typeof fields === 'object') {
      for (const [key, value] of Object.entries(fields as Record<string, unknown>)) {
        result[key] = String(value);
      }
    }
    for (const [key, value] of Object.entries(this.details)) {
      if (key === 'fields') continue;
      if (Array.isArray(value)) result[key] = value.join(' ');
    }
    return result;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

// --- in-memory token -------------------------------------------------------

let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** Called when the session cannot be recovered, so the app can sign out. */
export function setSessionLostHandler(handler: (() => void) | null): void {
  onSessionLost = handler;
}

// --- refresh coordination --------------------------------------------------

let refreshInFlight: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  const csrf = readCookie(CSRF_COOKIE);
  if (!csrf) return false;

  try {
    const response = await fetch(`${BASE_URL}${API_PREFIX}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { [CSRF_HEADER]: csrf },
    });
    if (!response.ok) return false;
    const body = (await response.json()) as SessionResponse;
    accessToken = body.access_token;
    return true;
  } catch {
    return false;
  }
}

/** Refresh the session, coalescing concurrent callers onto one request. */
export function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

// --- request ---------------------------------------------------------------

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  /** Skip the automatic refresh-and-retry (used by auth calls themselves). */
  skipRetry?: boolean;
  /** Send the CSRF header (needed by cookie-authenticated endpoints). */
  withCsrf?: boolean;
  signal?: AbortSignal;
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = { code: 'unknown_error', message: response.statusText };
  try {
    const json = await response.json();
    if (json?.error) body = json.error as ApiErrorBody;
  } catch {
    /* non-JSON error body; keep the fallback */
  }
  return new ApiError(response.status, body);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, skipRetry = false, withCsrf = false, signal } = options;

  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    if (withCsrf) {
      const csrf = readCookie(CSRF_COOKIE);
      if (csrf) headers[CSRF_HEADER] = csrf;
    }
    return fetch(`${BASE_URL}${API_PREFIX}${path}`, {
      method,
      credentials: 'include',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  };

  let response = await send();

  if (response.status === 401 && !skipRetry) {
    const recovered = await refreshSession();
    if (recovered) {
      response = await send();
    } else {
      accessToken = null;
      onSessionLost?.();
      throw await parseError(response);
    }
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

export type QueryValue = string | number | boolean | null | undefined | readonly (string | number)[];
export type QueryParams = Record<string, QueryValue>;

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const API_ROOT = (import.meta.env.VITE_API_ROOT ?? "/api").replace(/\/$/, "");
export const RV_API_BASE = `${API_ROOT}/rv`;
export const STAFFING_API_BASE = `${API_ROOT}/staffing`;

export function buildQuery(params: QueryParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item));
    } else {
      search.append(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `The request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail && typeof body.detail === "object") {
        const d = body.detail as { reason?: unknown; warning?: unknown };
        detail = typeof d.reason === "string" ? d.reason : JSON.stringify(body.detail);
      } else if (Array.isArray(body.detail)) {
        detail = "The request was not valid. Check the values and try again.";
      }
    } catch {
      /* generic */
    }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export async function getJson<T>(path: string, params: QueryParams = {}, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${RV_API_BASE}${path}${buildQuery(params)}`, {
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("The server could not be reached. Check that the API is running.", 0);
  }
  return readResponse<T>(response);
}

export async function staffingJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${STAFFING_API_BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("The server could not be reached. Check that the API is running.", 0);
  }
  return readResponse<T>(response);
}
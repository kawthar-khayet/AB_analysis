const API_BASE = "/api/v1";

export class ApiError extends Error {
  code: string;
  category?: string;
  details?: Record<string, any>;
  status: number;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = data?.code || (typeof data?.detail === "object" ? data.detail.code : "API_ERROR");
    this.category = data?.category || data?.detail?.category;
    this.details = data?.details || data?.detail?.details;
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: any;
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: await response.text() };
    }
    const message =
      errorData?.message ||
      (typeof errorData?.detail === "string"
        ? errorData.detail
        : errorData?.detail?.message) ||
      `Erreur HTTP ${response.status}`;
    throw new ApiError(message, response.status, errorData);
  }

  if (response.headers.get("content-type")?.includes("application/pdf")) {
    return (await response.blob()) as unknown as T;
  }

  return response.json();
}

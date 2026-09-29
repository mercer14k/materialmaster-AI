export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public trace?: string,
  ) {
    super(message);
  }
}
let token = "";
export function setToken(value: string) {
  token = value;
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      body.error?.message || `Request failed (${response.status})`,
      response.status,
      body.error?.trace_id,
    );
  }
  return response.json();
}
export function command<T>(path: string, body?: unknown) {
  return api<{ result: T }>("/commands" + path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}
export async function downloadFindings(dataset: string) {
  const response = await fetch(
    "/api/v1/export/findings.csv?dataset_id=" + encodeURIComponent(dataset),
    { headers: token ? { Authorization: `Bearer ${token}` } : {} },
  );
  if (!response.ok) throw new Error("Could not export findings");
  const url = URL.createObjectURL(await response.blob()),
    anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "materialmaster-findings.csv";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const number = (value: number | undefined) =>
  new Intl.NumberFormat("en-US").format(value ?? 0);
export const label = (value: string) =>
  ({
    uom: "Unit of measure",
    price: "Pricing anomaly",
    duplicate: "Potential duplicate",
    purchasing: "Purchasing gaps",
    lifecycle: "Lifecycle conflict",
    lead_time: "Lead time",
  })[value] || value.replaceAll("_", " ");
export const date = (value: string) =>
  new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

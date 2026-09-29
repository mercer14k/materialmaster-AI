import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, command, label, number, setToken } from "./api";
afterEach(() => {
  vi.unstubAllGlobals();
  setToken("");
});
describe("API client contracts", () => {
  it("formats measured values and domain terms", () => {
    expect(number(100000)).toBe("100,000");
    expect(label("uom")).toBe("Unit of measure");
  });
  it("preserves server error and trace ID", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({
              error: { message: "Conflict", trace_id: "trace123" },
            }),
            { status: 409 },
          ),
        ),
    );
    await expect(api("/findings")).rejects.toMatchObject({
      status: 409,
      trace: "trace123",
      message: "Conflict",
    });
    expect(new ApiError("x", 400)).toBeInstanceOf(Error);
  });
  it("sends token and idempotency key for a command", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ result: { ok: true } })),
      );
    vi.stubGlobal("fetch", fetcher);
    setToken("test-token");
    await command("/test", { decision: "accepted" });
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("/api/v1/commands/test");
    expect(init.headers.Authorization).toBe("Bearer test-token");
    expect(init.headers["Idempotency-Key"]).toMatch(/^[\w-]{36}$/);
    expect(init.method).toBe("POST");
  });
});

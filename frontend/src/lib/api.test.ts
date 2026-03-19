import { ApiClient } from "@/lib/api";

describe("ApiClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("treats 204 delete response as success without JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 204,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new ApiClient({ baseUrl: "http://localhost:8000" });

    await expect(client.deleteProduct("workspace-1", "product-1")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns JSON payload for successful non-empty responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ready" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = new ApiClient({ baseUrl: "http://localhost:8000" });
    const payload = await client.getHealthReady();

    expect(payload.status).toBe("ready");
  });
});

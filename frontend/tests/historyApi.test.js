import test from "node:test";
import assert from "node:assert/strict";
import { request } from "../src/services/api.js";

test("history view reads records from the existing backend route", async () => {
  let requestedUrl = "";
  globalThis.fetch = async (url) => {
    requestedUrl = url;
    return new Response(JSON.stringify([{ analysis_id: "id-1", query: "count buildings", status: "success" }]), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  const records = await request("/api/analysis/history");
  assert.match(requestedUrl, /\/api\/analysis\/history$/);
  assert.deepEqual(records, [{ analysis_id: "id-1", query: "count buildings", status: "success" }]);
});

test("history result expansion uses the existing analysis result route", async () => {
  let requestedUrl = "";
  globalThis.fetch = async (url) => {
    requestedUrl = url;
    return new Response(JSON.stringify({ analysis_id: "id/with space", execution: { results: [] } }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  await request(`/api/analysis/${encodeURIComponent("id/with space")}`);
  assert.match(requestedUrl, /\/api\/analysis\/id%2Fwith%20space$/);
});

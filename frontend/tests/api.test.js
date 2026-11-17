import test from "node:test";
import assert from "node:assert/strict";
import { request } from "../src/services/api.js";

test("request exposes FastAPI detail strings", async () => {
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "Invalid image ID." }),
    { status: 400, headers: { "content-type": "application/json" } },
  );
  await assert.rejects(request("/test"), /Invalid image ID\./);
});

test("request formats FastAPI validation arrays", async () => {
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: [{ msg: "Field required" }, { msg: "Invalid value" }] }),
    { status: 422, headers: { "content-type": "application/json" } },
  );
  await assert.rejects(request("/test"), /Field required; Invalid value/);
});

test("request preserves legacy messages and status fallback", async () => {
  globalThis.fetch = async () => new Response(
    JSON.stringify({ message: "Legacy error" }),
    { status: 400, headers: { "content-type": "application/json" } },
  );
  await assert.rejects(request("/test"), /Legacy error/);
  globalThis.fetch = async () => new Response("", { status: 503 });
  await assert.rejects(request("/test"), /status 503/);
});

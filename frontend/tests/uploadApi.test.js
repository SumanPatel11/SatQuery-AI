import test from "node:test";
import assert from "node:assert/strict";
import { uploadImage } from "../src/services/api.js";

test("image upload sends the selected file to the existing upload endpoint", async () => {
  let requestUrl = "";
  let uploadedFileName = "";
  globalThis.fetch = async (url, options) => {
    requestUrl = url;
    assert.equal(options.method, "POST");
    assert.ok(options.body instanceof FormData);
    uploadedFileName = options.body.get("image")?.name;
    return new Response(JSON.stringify({ status: "success", image_id: "server-issued-id" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  const file = new File([new Uint8Array([137, 80, 78, 71])], "scene.png", { type: "image/png" });
  const result = await uploadImage(file);
  assert.match(requestUrl, /\/api\/images\/upload$/);
  assert.equal(uploadedFileName, "scene.png");
  assert.equal(result.image_id, "server-issued-id");
});

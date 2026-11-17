# API Documentation

The local backend defaults to `http://localhost:8000`. Routes are defined in `backend/main.py`. The inspected API is local-development oriented and has no authentication layer.

## Health

`GET /api/health` returns a service-status object.

## Upload an image

`POST /api/images/upload` accepts multipart form data with a field named `image`. The backend checks extension, file signature, non-empty content, and a 20 MB size limit. Accepted extensions are JPEG, PNG, WebP, and TIFF variants. The response includes an `image_id` for later requests. Generic upload validation does not establish that an image meets a CV task?s modality requirements.

## Conversational query

`POST /api/query` accepts JSON:

```json
{
  "query": "How many buildings are visible?",
  "imageId": "<image_id returned by upload>",
  "secondImageId": null,
  "sessionId": "<optional client session id>",
  "context": {}
}
```

`imageId` is required. `secondImageId` supplies the after image for paired building-change requests. The backend resolves conversation context from its own bounded in-memory session store; the request model has a `context` field, but the current endpoint does not use it to construct session memory. If no session ID is supplied, the endpoint creates one.

A successful response contains status and IDs, the query, NLP/routing information, execution rows, and `assistant_response`. A blocked response includes validation details. Result fields depend on the capability; see [CV Models](CV_MODELS.md).

## Direct analysis

`POST /api/analysis` accepts `image` (uploaded ID), `query`, optional `second_image` (uploaded ID), and optional `session_id`. The request model also defines `analysisType` and `options`; the route currently does not use these to select a different model path. The same analysis pipeline serves the query endpoint.

## History and result retrieval

- `GET /api/analysis/history` returns analysis IDs, run IDs, queries, and statuses held by the current process.
- `GET /api/analysis/{analysis_id}` returns a recorded result while it remains in process memory.

Records and history do not survive a backend restart.

## Overlay routes

- `GET /api/analysis/{analysis_id}/change-overlay` returns a saved PNG change overlay if present under `cv/outputs/predictions/`.
- `GET /api/analysis/{analysis_id}/flood-overlay` returns a saved PNG flood overlay if present under that predictions directory.

These routes return image bytes rather than JSON. Missing records or overlays produce HTTP errors.

## Error behavior

FastAPI HTTP errors cover invalid IDs, missing uploads, unsupported formats, oversized uploads, missing inputs, and unavailable overlays. Unexpected analysis failures are logged server-side and return a sanitized message.

## Typical request sequence

1. Upload the single/before image to `/api/images/upload`; retain its `image_id`.
2. For change analysis, upload the after image separately and retain its ID.
3. Submit the query and image ID(s) to `/api/query`.
4. Read `assistant_response` and `execution.results`; use the returned analysis ID to retrieve details or a saved overlay.

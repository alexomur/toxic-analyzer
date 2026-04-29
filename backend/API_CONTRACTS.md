# Toxic Analyzer Backend API Obligations

This document defines the MVP-level obligations of the public ASP.NET backend service for Toxic Analyzer.

## Purpose and Boundaries

### Backend role

`backend` is the public product API. It is responsible for HTTP contracts, request validation, orchestration of internal calls, persistence of product data, and returning stable backend-level responses to clients.

### Model service role

`model` is an internal Python inference service. It is responsible for ML inference and related internal model operations.

### Boundary rule

`backend` calls `model`, but does not implement ML logic itself.

## MVP Scope

MVP defines two public toxicity-analysis endpoints, excluding authorization endpoints:

- `POST /api/v1/toxicity/analyze`
- `POST /api/v1/toxicity/analyze-batch`

The backend must expose stable public contracts even if the internal `model` contract evolves.

## Public Endpoint: `POST /api/v1/toxicity/analyze`

### Purpose

Check a single text for toxicity.

### Request

```json
{
  "text": "some text",
  "reportLevel": "summary"
}
```

### Response

```json
{
  "analysisId": "string",
  "label": 0,
  "toxicProbability": 0.12,
  "model": {
    "modelKey": "string",
    "modelVersion": "string"
  },
  "reportLevel": "summary",
  "explanation": null,
  "createdAt": "2026-04-29T12:00:00Z"
}
```

### Backend obligations

- Validate `text` before calling the internal `model` service.
- Validate `reportLevel` when it is supplied and default it to `summary` when it is omitted.
- Reject invalid requests with the common backend error format.
- Call the internal `model` service for either summary or explain inference depending on `reportLevel`.
- Persist the analysis result in backend storage.
- Add or update the corresponding text record in the temporary candidate-text store.
- Return a normalized backend response rather than the raw `model` service payload.
- Generate and return `analysisId` as the backend-side identifier of the stored analysis result.
- Return `createdAt` in UTC ISO 8601 format.

### Validation rules

- `text` is required.
- `text` must be a string.
- `text` must not be empty after normalization/trim.
- `reportLevel`, if provided, must be either `summary` or `full`.
- Maximum text length: `TBD`.

### Contract notes

- `label` is the backend-exposed binary toxicity label returned from model inference.
- `toxicProbability` is the backend-exposed normalized probability in the `[0, 1]` range.
- `model.modelKey` and `model.modelVersion` identify the model that produced the result.
- `reportLevel` echoes the resolved report mode used by the backend.
- `explanation` is always present in the JSON contract and is `null` for `summary`.
- In `full` mode, `explanation` contains backend-level explainability fields and does not mirror the raw internal `model` schema.

## Public Endpoint: `POST /api/v1/toxicity/analyze-batch`

### Purpose

Check a collection of texts for downstream analytics on the client side.

### Request

```json
{
  "items": [
    {
      "clientItemId": "optional-client-id",
      "text": "some text"
    }
  ]
}
```

### Response

```json
{
  "batchId": "string",
  "items": [
    {
      "clientItemId": "optional-client-id",
      "analysisId": "string",
      "label": 0,
      "toxicProbability": 0.12,
      "model": {
        "modelKey": "string",
        "modelVersion": "string"
      }
    }
  ],
  "summary": {
    "total": 1,
    "toxicCount": 0,
    "nonToxicCount": 1,
    "averageToxicProbability": 0.12
  },
  "createdAt": "2026-04-29T12:00:00Z"
}
```

### Backend obligations

- Validate the batch envelope and every item before calling the internal `model` service.
- Reject invalid requests with the common backend error format.
- Call the internal `model` service for batch inference.
- Persist the batch entity and all per-item analysis results in backend storage.
- Add or update corresponding text records in the temporary candidate-text store.
- Preserve the request item order in the response.
- Return `clientItemId` unchanged and without interpretation if it was supplied by the client.
- Return normalized backend-level batch results rather than the raw `model` service payload.
- Generate and return `batchId` as the backend-side identifier of the stored batch.
- Return `createdAt` in UTC ISO 8601 format.

### Validation rules

- `items` is required.
- `items` must be an array.
- `items` must contain at least one element.
- Maximum batch size: `TBD`.
- Every item must contain `text`.
- Every item `text` must satisfy the same validation rules as `POST /api/v1/toxicity/analyze`.
- `clientItemId`, if provided, must be treated as an opaque client value.
- Maximum `clientItemId` length: `TBD`.

### Ordering rule

For MVP, the backend must preserve the input order in the response `items` array. If internal processing is parallelized, response ordering must still match request ordering.

### Summary rules

- `summary.total` equals the number of accepted input items in the request.
- `summary.toxicCount` equals the number of items with `label = 1`.
- `summary.nonToxicCount` equals the number of items with `label = 0`.
- `summary.averageToxicProbability` is the arithmetic mean of all item-level `toxicProbability` values in the batch.

## Common Backend Rules

### Error format

All non-success responses must use a single backend error envelope.

Proposed MVP format:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": [
      {
        "field": "text",
        "message": "Text must not be empty."
      }
    ],
    "traceId": "string"
  }
}
```

### Error format obligations

- `code` is a stable machine-readable error identifier.
- `message` is a short human-readable description.
- `details` is optional and used for field-level validation or business-rule violations.
- `traceId` is included for diagnostics and request correlation.
- Backend must not leak raw internal exception payloads from ASP.NET, infrastructure, or the `model` service.

### Minimum error categories for MVP

- `validation_error`
- `unauthorized`
- `forbidden`
- `model_unavailable`
- `upstream_timeout`
- `conflict`
- `internal_error`

### HTTP status guidance for MVP

- `400 Bad Request` for malformed payloads and validation failures.
- `401 Unauthorized` for unauthenticated access.
- `403 Forbidden` for authenticated but unauthorized access.
- `409 Conflict` for request conflicts if such scenarios are introduced.
- `502 Bad Gateway` when the internal `model` service returns an invalid upstream response.
- `503 Service Unavailable` when the internal `model` service is unavailable.
- `504 Gateway Timeout` when the internal `model` service does not respond in time.
- `500 Internal Server Error` for unexpected backend failures.

### Input limits

- Maximum single-text length: `TBD`.
- Maximum batch size: `TBD`.
- Maximum `clientItemId` length: `TBD`.

These limits must be enforced by the backend before invoking the internal `model` service.

## Persistence Obligations

### What the backend must persist

For single analysis:

- backend `analysisId`
- original input text or a normalized backend-approved representation of it
- inference result: `label` and `toxicProbability`
- model metadata: `modelKey`, `modelVersion`
- timestamps such as `createdAt`
- audit and tracing metadata required by the product

For batch analysis:

- backend `batchId`
- batch-level timestamps and audit metadata
- item-to-batch linkage
- per-item `analysisId`
- per-item input text or normalized representation
- per-item inference result and model metadata
- optional raw `clientItemId` exactly as provided by the client

For temporary candidate-text storage:

- text identity or deduplication key
- source text content or normalized canonical form
- last analysis metadata relevant for future review
- timestamps for create/update lifecycle

### Persistence rule for candidate texts

When a text that is eligible for candidate storage is analyzed, the backend must add a new candidate record or update the existing temporary candidate record according to backend deduplication rules. The exact deduplication strategy is `TBD`, but the public API contract must remain stable regardless of that internal choice.

## Integration Obligations Toward `model`

The backend must treat the Python `model` service as an internal dependency with a separate contract.

### Backend responsibilities during integration

- Translate backend request DTOs into internal `model` service requests.
- Translate internal `model` service responses into backend public responses.
- Handle upstream availability, timeout, and invalid-response scenarios.
- Avoid exposing internal `model` field names directly in the public contract unless intentionally mapped.

### Backend must not do

- implement ML inference logic
- implement model training or retraining logic
- read model artifacts directly from `model/`
- load or store binary model weights
- bypass the internal `model` service for inference
- expose internal admin or retraining endpoints as part of this MVP public API

## Non-Goals for This MVP

- Separate public explainability endpoints
- Public dataset-management endpoints
- Public retraining endpoints
- Frontend-specific analytics endpoints beyond the batch response summary
- Tight coupling of the public API to raw `model` service schemas

## MVP+ Roadmap

This section describes expected future functionality without locking strict endpoint contracts yet.

### Candidate review flow

Future backend functionality may include:

- retrieving a random text from the temporary candidate-text store for human evaluation
- submitting a user label `0` or `1` for an existing candidate text
- adding a new text together with a user-provided label into the temporary candidate-text store

### Promotion to permanent training storage

Candidate texts may later be promoted from the temporary candidate-text store into the permanent training database when both conditions are met:

- the text has more than `100` collected evaluations
- at least `80%` agreement exists for label `0` or label `1`

### Model retraining trigger

Future backend functionality may include triggering model retraining through the internal `model` service after backend-side eligibility checks and workflow orchestration.

The retraining implementation and ML workflow remain internal responsibilities of the `model` service.

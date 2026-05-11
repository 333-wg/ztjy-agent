# Safety Model Runbook

## Agent Boundaries

`device_ad_agent` can bind existing ads to a device. It cannot create ads, upload files, delete data, modify device profile fields, or remove baseline ads.

`ad_upload_agent` can create image/video ads in advertisement management. It cannot bind ads to devices, create companies, delete ads, overwrite existing ads, or save multiple items with one approval.

## Permission Enforcement

Allowed actions live in versioned permission sets and are mirrored in `backend/app/safety/permissions.py`. Workflow code calls `PermissionSet.require()` before guarded operations.

## Approval Gates

Save approval uses a canonical JSON SHA-256 hash:

1. The workflow creates a pre-save report.
2. The approval stores the report hash.
3. Before save, the workflow recomputes the current report hash.
4. Save is blocked unless the approval is approved and hashes match.

## Device Baseline Protection

The device workflow reads existing device ads before adding anything. Corrections can only remove ads added by the current task and cannot remove baseline ads.

## Upload Sequential Execution

Upload commands may contain multiple image/video items, but the browser workflow processes one item at a time:

- search local asset
- validate media type
- open create form
- upload file
- read preview
- request item save approval
- save approved item
- move to next item

Missing tags require a separate owner approval before creation.

## Mixed Workflow Handoff

Mixed upload-then-bind commands complete the upload phase first. The system then creates a new task-level confirmation for device binding handoff. It does not automatically start the Device Advertisement Agent.

## LLM Boundary

LLM command parsing is optional and controlled by `LLM_PARSER_MODE`.
The LLM can only return structured routing fields such as workflow kind, device number, company, tag, and local asset names.
It cannot call browser methods, bypass permission checks, save forms, create tags, bind devices, or approve actions.

Recommended production mode is `hybrid`: deterministic parsing runs first, and the model is used only for unclear natural-language commands.

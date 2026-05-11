# Device Advertisement Agent Design

## Summary

Build a local, controlled agent system for operating the company's management backend through a browser. The first milestone implements one workflow: bind existing advertisements from the backend's advertisement library to a specified device.

The system will use a local Web console, Python FastAPI backend, LangGraph workflow orchestration, and Playwright for browser automation. The first implementation will support a mock backend adapter while preserving the same interface expected for the real management system.

The agent must not freely operate the backend. It can only call explicitly whitelisted tools. Before any final save, it must verify that the selected device and advertisements match the owner's command, report the pending action, and wait for owner approval.

## Goals

- Accept natural language commands from the owner.
- Parse commands into a target device number, advertisement names, and an intended action.
- Confirm the parsed command before browser operation begins.
- Use the browser's existing management-system login state.
- If not logged in, stop and ask the owner to log in manually.
- Search the device list by device number.
- Bind advertisements that already exist in advertisement management.
- Stop and report when a device or advertisement cannot be uniquely identified.
- Require owner approval before saving.
- Record key audit events for traceability.
- Structure the project so future business agents can be added without rewriting the first workflow.

## Non-Goals

- The first version will not create or upload new advertisements.
- The first version will not store or read backend usernames or passwords.
- The first version will not modify device information.
- The first version will not delete devices, delete advertisements, or change system configuration.
- The first version will not automatically hand off to another agent when an advertisement is missing.
- The first version will not rely on the LLM to perform arbitrary browser clicks.

## First Workflow

The first workflow is "bind existing advertisements to a specified device."

Example command:

```text
帮我给设备 10086 添加五一促销广告和新品视频
```

The system should parse this as:

- Target device number: `10086`
- Advertisement names: `五一促销广告`, `新品视频`
- Action: bind existing advertisements to the device

Before operating the backend, the agent must show the parsed result and state the allowed scope:

```text
我理解为：目标设备号是 10086；要绑定的广告是：五一促销广告、新品视频。
本次只会进入设备管理进行广告绑定，不会创建广告、删除广告或修改设备信息。
请确认是否开始。
```

## Architecture

The system has five main parts.

1. Local Web console
   - Accepts natural language commands.
   - Shows parsed command confirmation.
   - Shows workflow progress and paused states.
   - Shows the pre-save verification report.
   - Provides the final approval button before save.

2. FastAPI backend
   - Exposes task APIs for the console.
   - Runs LangGraph workflows.
   - Stores audit records.
   - Coordinates browser sessions.

3. LangGraph workflow layer
   - Owns state transitions.
   - Routes the command to the correct business workflow.
   - Enforces pauses for owner confirmation.
   - Handles failure branches such as missing login, multiple matches, and permission violations.

4. Browser adapter layer
   - Provides narrow business methods such as `search_device`, `search_ad`, and `save_after_approval`.
   - Hides raw Playwright access from the agent workflow.
   - Starts with a `MockAdminAdapter`.
   - Later adds a `PlaywrightAdminAdapter` for the real management backend.

5. Safety and audit layer
   - Defines each agent's allowed actions.
   - Blocks non-whitelisted operations.
   - Records key steps and decisions.
   - Requires approval before final save.

## Agent Model

The first version includes these roles:

- Task Router Agent
  - Parses the user's command.
  - Determines the target business workflow.
  - Checks whether the requested action is in scope.

- Device Advertisement Agent
  - Handles only device advertisement binding.
  - Uses only device-advertisement tools.
  - Cannot upload advertisements, delete data, or modify device profile fields.

Future agents can be added later:

- Advertisement Upload Agent
  - Uploads image or video advertisements.
  - Fills advertisement metadata.
  - Requires its own permission whitelist and confirmation gates.

- Device Management Agent
  - Handles device status queries first.
  - Any modification workflow must be separately designed and guarded.

Cross-agent handoff must be explicit. For example, if an advertisement does not exist, the Device Advertisement Agent stops and reports the missing advertisement. It must not automatically start the Advertisement Upload Agent.

## Device Advertisement Workflow

The workflow proceeds through these states:

1. Receive natural language command.
2. Parse command into device number, advertisement names, and action.
3. Ask owner to confirm the parsed command.
4. Check backend login state.
5. If not logged in, ask owner to log in manually and pause.
6. Open device management.
7. Search for the device number.
8. Require exactly one matching device.
9. Open the device's advertisement configuration entry.
10. Search for each requested advertisement.
11. If an advertisement has multiple candidates, list candidates and ask the owner to choose.
12. If an advertisement is missing, stop and report.
13. Add selected advertisements to the pending save list.
14. Read the pending save list from the page.
15. Compare pending device and advertisements with the original confirmed command.
16. Show a pre-save report to the owner.
17. Save only after owner approval.
18. Read the save result and report success or failure.
19. Write final audit entries.

## Allowed Actions

The first version allows only these actions:

- Check login status.
- Open the management backend URL.
- Open device management.
- Search by device number.
- Open the advertisement configuration entry for the uniquely matched device.
- Search existing advertisements by advertisement name.
- Select owner-approved advertisement candidates.
- Add selected advertisements to the pending list.
- Read the pending list for verification.
- Save after owner approval.
- Read and report the save result.

## Blocked Actions

The first version must block these actions:

- Create advertisements.
- Upload advertisement images or videos.
- Delete advertisements.
- Delete devices.
- Modify device profile information.
- Change system configuration.
- Perform batch operations outside the confirmed device.
- Save before owner approval.
- Continue when the page structure, button meaning, or target object is uncertain.
- Use backend credentials stored in configuration.

## Matching Rules

Device matching:

- The device number should produce exactly one backend result.
- If no device is found, stop and report.
- If multiple devices are found, stop and ask for a more precise identifier.

Advertisement matching:

- If an advertisement name produces exactly one clear result, continue.
- If multiple candidates are found, list candidates and ask the owner to choose.
- If no advertisement is found, stop and report that this must be handled by a future Advertisement Upload Agent.
- Candidate reports should include available identifying fields, such as name, type, ID, status, and effective time, when the backend exposes them.

## Login Handling

The agent will not store or read backend usernames or passwords.

The browser should use a persistent browser profile so login cookies can survive across runs. On task start, the agent opens the management backend and checks whether it is already logged in.

If the browser is not logged in:

- The workflow pauses.
- The Web console asks the owner to log in manually.
- After the owner confirms login is complete, the workflow checks login state again.

## Approval Gate

Before final save, the agent must produce a pre-save verification report containing:

- Original owner command.
- Parsed device number.
- Matched device details.
- Requested advertisement names.
- Matched advertisement details.
- Pending page state read from the browser.
- A statement that the agent did not create advertisements, delete data, or modify device profile information.

The save button in the workflow is enabled only after the owner approves this report.

## Audit Logging

The first version records key step-level audit events:

- Task created.
- Command parsed.
- Owner confirmed parsed command.
- Login state checked.
- Device search completed.
- Advertisement search completed.
- Candidate selection requested or completed.
- Pre-save verification generated.
- Owner approved or rejected save.
- Save attempted.
- Final result reported.

Each audit event should include:

- Task ID.
- Timestamp.
- Agent name.
- Step name.
- Status.
- Structured details relevant to that step.

Screenshots are not required by default in the first version. The design should leave room to add screenshots later for failure cases, with sensitive information masking considered separately.

## Suggested Project Structure

```text
ztjy-agent/
  backend/
    app/
      main.py
      agents/
        router.py
        device_ad_agent.py
      workflows/
        device_ad_graph.py
      browser/
        adapters.py
        mock_admin.py
        playwright_admin.py
      safety/
        permissions.py
        approvals.py
      audit/
        models.py
        store.py
    tests/
  frontend/
    src/
      pages/
      components/
      api/
  docs/
    superpowers/
      specs/
```

## Implementation Strategy

The first build should use a mock adapter to validate the workflow, permissions, approval gates, and audit logging before connecting to the real backend.

The browser adapter interface should be designed to match real backend operations:

- `check_login()`
- `open_device_management()`
- `search_device(device_no)`
- `open_device_ad_config(device_id)`
- `search_ad(ad_name)`
- `select_ad(ad_id)`
- `read_pending_ads()`
- `save_after_approval()`
- `read_save_result()`

The mock adapter and real Playwright adapter should implement the same interface so the workflow does not need to change when real backend access is added.

## Testing Requirements

The first implementation should include tests for:

- Natural language command parsing.
- Permission whitelist enforcement.
- Device not found.
- Multiple devices found.
- Advertisement not found.
- Multiple advertisement candidates.
- Pre-save verification mismatch.
- Save blocked before owner approval.
- Successful happy path with mock adapter.
- Audit events written for key steps.

## Open Implementation Inputs

These details are intentionally deferred until real backend integration:

- Management backend URL.
- Test device numbers.
- Test advertisement names.
- Actual menu paths and page selectors.
- Whether the backend has a staging environment.
- Fields available in device and advertisement search results.

These are not blockers for building the first workflow skeleton with a mock adapter.

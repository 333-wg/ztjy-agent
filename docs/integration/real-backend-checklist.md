# Real Backend Integration Checklist

Collect these inputs before enabling Playwright against a real management backend.

## Environment

- backend URL for the management system
- environment type: staging or production
- persistent browser profile path or profile alias
- confirmation that backend credentials, cookies, and passwords are not stored in Supabase

## Test Data

- test company name and backend ID
- test tags for existing-tag and missing-tag scenarios
- test device number and backend ID
- test image advertisement already present in advertisement management
- test video advertisement already present in advertisement management
- local image and video files safe to upload in staging

## Selectors

- login success selector
- device management menu path and search field selector
- device advertisement config entry selector
- advertisement management menu path
- company dropdown/search selectors
- tag dropdown/search/create selectors
- image/video type selectors
- local file input selector
- preview/result selectors
- save buttons and success/failure result selectors

## Safety Rules

- Use staging first and record screenshots for each selector.
- Production runs require explicit owner confirmation before save.
- Do not expose arbitrary click, type, or evaluate helpers through the adapter.
- Stop if a selector label, page target, or save semantics are uncertain.

1. **Fix `status_property` in `notion_brain/store.py` to redact secrets.**
   - In `notion_brain/store.py`, `select_property`, `multi_select_property`, `rich_text_property`, and `title_property` all call `redact_secrets` before putting the data in the payload. However, `status_property` does not.
   - This causes `provider.py` methods (like `_tool_task`) that use `status_property` (via `_validated_status` fallback) to leak un-redacted secrets to the Notion API in the `status` field.
   - We will modify `status_property` in `notion_brain/store.py` to call `redact_secrets(name)`.

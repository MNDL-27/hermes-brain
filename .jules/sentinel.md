## 2024-05-18 - Exposing exception details in tool responses
**Vulnerability:** The error messages passed to the API caller inside tool responses (e.g. `f"Tool error: {exc}"` or `f"Error: {exc}"`) include the unredacted exception detail, which might leak sensitive data such as API keys.
**Learning:** Exception details must be sanitized before passing them back in API responses, not just in logs.
**Prevention:** Use `S.redact_secrets` when catching exceptions and rendering error messages to the user.

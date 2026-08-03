## 2026-08-01 - Bypassing Sanitization via Direct Tool Calls
**Vulnerability:** The `notion_brain` application has a central `redact_secrets` mechanism applied in background data processing, but the explicit `notion_brain_task`, `notion_brain_content`, and `notion_brain_research` tools handled direct user input directly and bypassed this central sanitization. The `clean_title` and `dedupe_strings` (for tags) did not sanitize content. Consequently, API keys, tokens, and secrets could leak to the Notion database if a user explicitly passed them in.
**Learning:** Security controls applied only to the "primary" or "passive" path (like automated scraping/sync) are insufficient. Every boundary/entry point (like specific explicit CLI tools or command handlers) needs to defensively ensure inputs are sanitized.
**Prevention:** Apply input sanitization directly at the system boundary for all entry paths. Modify shared primitives (`clean_title`, `dedupe_strings`) to include standard sanitization (`redact_secrets`) where possible to prevent gaps.

## 2025-02-13 - [Fix Quoted Secret Redaction Regex]
**Vulnerability:** The secret redaction regex `(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s`'\"]+` failed to redact secrets enclosed in quotes (e.g., `api_key="my_secret"`).
**Learning:** Regex for token extraction needs to explicitly capture optionally quoted values to prevent evasion. Simply excluding quotes from the trailing part causes it to fail to match entirely when quotes are present.
**Prevention:** Use a regex pattern that explicitly handles quoted strings (e.g., `(?:[\"\'`][^\"\'`\r\n]+[\"\'`]|[^\s\"\'`])`) for generic secret matching.

## 2024-05-27 - Security Fix: Secret Redaction Coverage Leak
**Vulnerability:** API keys and sensitive tokens could be leaked to external services via the Notion integration. The redaction function `redact_secrets()` was originally only applied to the content body of the `BrainEntry` in `notion_brain/schema.py`. It missed properties like `title`, `tags`, and `entities`. Also, explicit tool calls bypassed `BrainEntry.normalized()` and generated Notion API JSON dictionaries directly, which didn't redact anything natively.
**Learning:** Redaction must be applied defensively and as close to the external API boundary (serialization step) as possible. If multiple layers can construct output payloads, each layer or the lowest common layer must apply the redaction. Relying on an intermediate normalization function (`BrainEntry.normalized()`) is unsafe when other code paths bypass it.
**Prevention:** Integrate secret redaction directly into output helper/formatting functions (e.g., `_rich_text`, `select_property`, `multi_select_property` in `notion_brain/store.py`). Always ensure all fields holding arbitrary string input, including metadata fields like titles and tags, are verified or redacted.

## 2026-07-31 - [CRITICAL] Fix API Path Traversal (SSRF risk) and Exception Leakage
**Vulnerability:**
The Notion API client (`notion_brain/store.py`) allowed API Path Traversal (SSRF risk) by embedding unescaped resource IDs directly into request URLs (e.g., `/databases/{database_id}`). A malicious payload like `../../users` could have been crafted to traverse to unintended backend endpoints.
Additionally, in `notion_brain/provider.py`, when a tool failed, the raw `Exception` string was directly logged and returned in the JSON payload, potentially leaking unredacted API secrets or internal paths.
**Learning:**
String concatenation with unsanitized identifiers in URL paths is a critical security vulnerability even if those identifiers are presumed to be safe internal UUIDs. Furthermore, `str(exc)` cannot be trusted as safe to log or return because Python exceptions capture their arguments directly, meaning secret tokens passed to failed operations could leak.
**Prevention:**
Always URL-encode dynamic path segments using `urllib.parse.quote(id, safe="")` before embedding them into a URL. All logged or returned exception messages must be wrapped in `redact_secrets()` (or similar scrubbing mechanisms) to ensure no sensitive credentials escape via stack traces or error responses.

## 2026-08-01 - Prevent Exception Leakage via Logs
**Vulnerability:** The logging statements sometimes logged exceptions (`logger.error("... %s", exc)`) which implicitly triggered `str(exc)`. This is a problem because if the exception contains sensitive information like API tokens or inputs, these will be leaked in log outputs directly. This bypasses the redaction logic applied in `notion_brain/provider.py` which was only manually applied in a few specific locations (like tool return bodies).
**Learning:** Log messages directly formatting exceptions without using `redact_secrets(str(exc))` are vulnerable to leaking sensitive data if the exception object encapsulates sensitive arguments.
**Prevention:** Systematically apply `redact_secrets(str(exc))` in all logging statements that capture and log exceptions.

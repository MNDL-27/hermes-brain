## 2026-08-01 - Bypassing Sanitization via Direct Tool Calls
**Vulnerability:** The `notion_brain` application has a central `redact_secrets` mechanism applied in background data processing, but the explicit `notion_brain_task`, `notion_brain_content`, and `notion_brain_research` tools handled direct user input directly and bypassed this central sanitization. The `clean_title` and `dedupe_strings` (for tags) did not sanitize content. Consequently, API keys, tokens, and secrets could leak to the Notion database if a user explicitly passed them in.
**Learning:** Security controls applied only to the "primary" or "passive" path (like automated scraping/sync) are insufficient. Every boundary/entry point (like specific explicit CLI tools or command handlers) needs to defensively ensure inputs are sanitized.
**Prevention:** Apply input sanitization directly at the system boundary for all entry paths. Modify shared primitives (`clean_title`, `dedupe_strings`) to include standard sanitization (`redact_secrets`) where possible to prevent gaps.

## 2026-07-27 - [Path Traversal in API Requests]
**Vulnerability:** User-provided IDs (like page_id, database_id, block_id) were being directly interpolated into URL paths without encoding.
**Learning:** Even internal API clients can be vulnerable to path traversal if they blindly trust IDs provided by upper layers or external input. Standard `urllib.parse.quote` keeps `/` unencoded by default (`safe='/'`), which still allows directory traversal payloads like `../`.
**Prevention:** Always use URL encoding with `safe=""` (e.g., `urllib.parse.quote(var, safe="")`) when building URL paths dynamically with variables.

## 2025-02-13 - [Fix Quoted Secret Redaction Regex]
**Vulnerability:** The secret redaction regex `(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s`'\"]+` failed to redact secrets enclosed in quotes (e.g., `api_key="my_secret"`).
**Learning:** Regex for token extraction needs to explicitly capture optionally quoted values to prevent evasion. Simply excluding quotes from the trailing part causes it to fail to match entirely when quotes are present.
**Prevention:** Use a regex pattern that explicitly handles quoted strings (e.g., `(?:[\"\'`][^\"\'`\r\n]+[\"\'`]|[^\s\"\'`]+)`) for generic secret matching.

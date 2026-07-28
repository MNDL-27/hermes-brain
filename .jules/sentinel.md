## 2025-02-13 - [Fix Quoted Secret Redaction Regex]
**Vulnerability:** The secret redaction regex `(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s`'\"]+` failed to redact secrets enclosed in quotes (e.g., `api_key="my_secret"`).
**Learning:** Regex for token extraction needs to explicitly capture optionally quoted values to prevent evasion. Simply excluding quotes from the trailing part causes it to fail to match entirely when quotes are present.
**Prevention:** Use a regex pattern that explicitly handles quoted strings (e.g., `(?:[\"\'`][^\"\'`\r\n]+[\"\'`]|[^\s\"\'`]+)`) for generic secret matching.

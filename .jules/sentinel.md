## 2025-03-01 - [CRITICAL] Fix Stripe Secret Redaction Regex
**Vulnerability:** The secret redaction regex only matched OpenAI format (`sk-`) and failed to match Stripe keys (`sk_live_` and `sk_test_`), allowing critical secrets to be stored in plaintext.
**Learning:** README documentation for security features (e.g. secret redaction) should be explicitly tested in the test suite to ensure the implemented regex patterns actually match the intended vulnerability signatures.
**Prevention:** Always write unit tests for each type of secret explicitly claimed to be protected by redaction patterns.

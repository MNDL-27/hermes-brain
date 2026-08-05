# Troubleshooting

Common setup failures and how to recover. Most issues fall into one of five buckets.

## 1. "I get `unauthorized` from Notion"

**Cause:** the integration token is missing, wrong, or the integration has not been shared with the target page.

**Fix:**

1. Confirm `NOTION_API_KEY` is set and starts with `ntn_`.
2. Open the Notion page you want as the brain parent.
3. Click `•••` → `Connections` → add your integration.
4. Re-run `python -m notion_brain health`.

If you skip step 3, the token is valid but cannot see any page — Notion returns `unauthorized` for an empty workspace.

## 2. "Bootstrap created the page but no databases"

**Cause:** a previous bootstrap partially completed and left an inconsistent cache.

**Fix:**

```bash
rm "$HERMES_HOME/notion_brain.json"
python -m notion_brain health    # auto-repairs schema mismatches
```

The cache is safe to delete — bootstrap recreates it from whatever exists in Notion.

## 3. "Heuristics missed something I said"

**Cause:** the classifier is regex-based and intentionally conservative. It catches roughly 70% of actionable items.

**Fix:** for anything critical, call `notion_brain_remember` explicitly instead of relying on auto-capture. Auto-capture is for the long tail; explicit calls are for the things you cannot afford to lose.

See [Automatic Capture](../README.md#automatic-capture) in the README for the full trigger list.

## 4. "Secret redaction stripped something legitimate"

**Cause:** the generic fallback regex matches `api_key=`, `token=`, `password=`, `secret=` anywhere in the text, including in code snippets and config examples.

**Fix:** none today — the redactor runs blindly to avoid leaks. If you need to store a non-secret string that matches the pattern, rename the variable (e.g. `api_key` → `apiKey` in your example).

## 5. "Background sync is silent on errors"

**Cause:** by design. The daemon thread logs failures to stderr but does not surface them to the agent loop — surfacing them would block the agent on transient Notion outages.

**Fix:** check stderr or run `python -m notion_brain health` to see the current sync state. If failures persist for more than a few minutes, the Notion token has likely been revoked — re-issue and re-share.

## 6. "`pip install hermes-brain` fails"

**Cause:** the package may not be on PyPI yet for your version.

**Fix:** install from source:

```bash
git clone https://github.com/MNDL-27/hermes-brain.git
cd hermes-brain
pip install -e .
```

If you need a stable release, check the [Releases page](https://github.com/MNDL-27/hermes-brain/releases) for the latest tag.

## Health check cheat sheet

```bash
python -m notion_brain health    # prints health report, auto-repairs schema mismatches
python -m notion_brain url       # prints the Notion URL of the Hermes Brain page
python -m notion_brain reset     # archive and recreate mismatched databases
```

Run `health` first whenever something looks off. It is the only command that auto-repairs.

## Still stuck?

Open an issue with:

1. The exact command you ran.
2. The exact output (redact any tokens).
3. Output of `python -m notion_brain health`.

Without these three, debugging is guesswork.

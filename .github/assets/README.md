# Social preview image

GitHub's social preview card (the image shown when this repo is linked on Twitter, LinkedIn, Discord, etc.) is configured in **Settings → General → Social preview**. GitHub does not read it from a file in the repo — it must be uploaded through the web UI.

**Required image:** `.github/assets/social-preview.png` (1200×630, 766 KB).

## How to update

1. Generate a new image matching the brand palette (Hermes amber `#FFB300` / `#FFC107` on dark navy `#0d1117`).
2. Resize to exactly **1200×630** PNG.
3. Save it over `.github/assets/social-preview.png` (this keeps the repo in sync with what's uploaded).
4. Upload it via Settings → General → Social preview → Upload an image.

Both the README hero (`.github/assets/hero.png`, any size) and the social card (`.github/assets/social-preview.png`, 1200×630) should be regenerated together to stay visually consistent.

## Why this is documented

Every maintainer eventually asks "where is the social image set?" and wastes time hunting through the repo. The answer is: GitHub UI only, plus this file in the repo for source-of-truth.

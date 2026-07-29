# Barrett Steel UK Steel Quota Tracker — Setup Guide (no dev team required)

This package gives you a fully automated, self-updating quota tracker. Follow these
steps once; after that it runs itself daily for free.

## What's in this folder
- `scripts/fetch_quotas.py` — pulls live data from the UK Government's Trade Tariff API
- `.github/workflows/update-quotas.yml` — runs that script automatically once a day
- `index.html` — the Barrett-branded page itself, ready to paste into Kentico
- `quota-data.json` — will be created automatically after the first run

## Step 1: Create a free GitHub account and repository
1. Go to github.com and sign up (free) if you don't already have an account —
   use a Barrett Steel email if possible.
2. Click "New repository". Name it something like `steel-quota-data`. Set it
   to **Public** (this is required for the free JSON hosting to work, and the
   data itself is already public government information, so there's no
   confidentiality concern).
3. Upload all the files in this folder to that new repository (drag-and-drop
   works fine on github.com, or ask IT for five minutes of help with `git push`
   if you'd rather not use the web uploader).

## Step 2: Turn on the daily automation
1. In your new repository, click the **Actions** tab.
2. GitHub should detect the workflow file automatically. Click "I understand
   my workflows, go ahead and enable them."
3. Click into "Daily Steel Quota Update" and press **Run workflow** to test it
   manually the first time (don't wait for the 6am scheduled run).
4. Check the run log. If it finishes green and a `quota-data.json` file
   appears in your repo with real numbers in it, you're done — it will now
   run automatically every day.

**If the test run fails with an authentication/403 error:** the government
API's public access rules may have changed since this was built. Go to
https://hub.trade-tariff.service.gov.uk/, register for a free API key (takes
a couple of minutes, no cost), and add it as an `Authorization` header in
`scripts/fetch_quotas.py` where indicated. This is the one step that might
need a short favour from IT if you're not comfortable editing the Python
file yourself — but it's a two-line change, not a build.

## Step 3: Get the live data URL
Once `quota-data.json` exists in your repo, its permanent public address is:

```
https://raw.githubusercontent.com/YOUR-GITHUB-USERNAME/steel-quota-data/main/quota-data.json
```

Open `index.html`, find the line near the bottom that says:

```js
const DATA_URL = "https://raw.githubusercontent.com/REPLACE_ORG/REPLACE_REPO/main/quota-data.json";
```

and replace `REPLACE_ORG/REPLACE_REPO` with your actual username/repo name.

## Step 4: Set up the alerts sign-up form (no code)
1. Go to forms.google.com and create a new form with fields: Name, Email,
   Company, and "Categories you want alerts for" (checkboxes — list the 20
   category names from the tracker).
2. Click the three-dot menu → "Get pre-filled link", fill in dummy answers,
   and generate the link — this reveals the real field names (`entry.xxxxx`)
   Google uses.
3. In `index.html`, replace `REPLACE_WITH_FORM_ID`, `REPLACE_NAME`,
   `REPLACE_EMAIL`, `REPLACE_COMPANY`, and `REPLACE_CATEGORIES` with the real
   values from that pre-filled link.
4. Every sign-up now lands automatically in a Google Sheet linked to your form
   (Responses tab → the green sheet icon).

## Step 5: Turn on real alert emails (optional, no-code)
Each day's run also writes `quota-changes.json`, listing any category that
newly crossed into WATCH or CRITICAL that day. To turn this into an actual
email:
1. Create a free account at make.com (or Zapier).
2. Build a simple scenario: **Watch a webhook → look up matching subscribers
   in your Google Sheet → send an email via Gmail/Outlook connector.**
3. Add one step to `update-quotas.yml` (a `curl` command posting
   `quota-changes.json` to your Make.com webhook URL) — a one-line addition,
   commented in the workflow file where it should go.

This step needs a little patience the first time but is entirely drag-and-drop
in Make.com's interface — no coding, and no dev team ticket required.

## Step 6: Add the page to barrettsteel.com
1. In Kentico, create a new page at the URL `/uk-steel-quota-tracker/`.
2. Paste the contents of `index.html` into the page's HTML/source editor.
3. Replace the placeholder logo path near the top (`/images/barrett-steel-logo.svg`)
   with the real logo asset path used elsewhere on the site.
4. Preview it, check the live table renders correctly, then publish.

## Notes
- The government API is free and needs no ongoing payment or account beyond
  the optional key in Step 2.
- Everything here is standard, low-risk web technology — nothing here touches
  or modifies any other page on barrettsteel.com.
- This whole pipeline can be ported as-is to the new platform at the Christmas
  migration — only the "paste HTML into the CMS" step (Step 6) needs redoing.

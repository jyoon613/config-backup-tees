# Setup Guide — Balboa Tee Time Watcher on GitHub Actions

This runs entirely on GitHub's servers, roughly every 10 minutes, 24/7.
Your computer does not need to be on.

## Step 1 — Create a GitHub account (skip if you have one)
Go to https://github.com/signup and follow the prompts. Free.

## Step 2 — Create a new repository
1. Click the **+** icon top-right → **New repository**.
2. Name it something like `tee-time-watcher`.
3. Set it to **Private** (recommended, so no one else sees your setup).
4. Click **Create repository**.

## Step 3 — Upload the files
On your new repo's page:
1. Click **Add file → Upload files**.
2. Drag in `balboa_tee_watcher.py` and `SETUP.md`.
3. Scroll down, click **Commit changes**.

Then create the workflow file (GitHub needs it in a specific folder):
1. Click **Add file → Create new file**.
2. In the filename box, type exactly: `.github/workflows/watch.yml`
   (typing the slashes creates the folders automatically).
3. Paste in the contents of the `watch.yml` file provided to you.
4. Click **Commit changes**.

## Step 4 — Add your secrets
These keep your Gmail app password out of the code itself.
1. In your repo, click **Settings** (top nav of the repo, not your account).
2. In the left sidebar: **Secrets and variables → Actions**.
3. Click **New repository secret**.
   - Name: `SMTP_EMAIL` → Value: your Gmail address
   - Click **Add secret**
4. Click **New repository secret** again.
   - Name: `SMTP_APP_PASSWORD` → Value: the 16-character app password from
     myaccount.google.com/apppasswords
   - Click **Add secret**
5. Click **New repository secret** again.
   - Name: `FOREUP_EMAIL` → Value: the email you use to log into the
     Balboa Park booking site
   - Click **Add secret**
6. Click **New repository secret** again.
   - Name: `FOREUP_PASSWORD` → Value: your foreUP account password
   - Click **Add secret**

This account login is used only to view tee-sheet availability — the
script never submits a reservation or enters any payment info.

## Step 5 — Fill in the two course ID numbers
Open `balboa_tee_watcher.py` in the repo (click on it, then the pencil/edit
icon), and replace:
```
SCHEDULE_ID = "REPLACE_ME"
BOOKING_CLASS_ID = "REPLACE_ME"
```
with the numbers you found via Chrome DevTools (see the walkthrough from
earlier). Commit the change.

## Step 6 — Test it manually
1. Click the **Actions** tab at the top of your repo.
2. Click **Balboa Tee Time Watcher** in the left sidebar.
3. Click **Run workflow** (top right) → **Run workflow**.
4. After ~30 seconds, click into the run to see the log output — it should
   say "Checking Balboa Park for Thursday tee times..." and either find
   something or say nothing available yet.

If that works, you're done — it'll now run automatically every ~10 minutes
without you touching anything. You'll get a text the moment a matching slot
opens.

## Troubleshooting
- **No text arrives when testing:** double check the secret names match
  exactly (`SMTP_EMAIL`, `SMTP_APP_PASSWORD`) and that 2-Step Verification
  is on for the Gmail account (required for app passwords to work).
- **Workflow shows a red X:** click into the run, expand the failed step,
  and the error message will usually point at what's wrong (commonly a
  typo in the secret name or the ID numbers).

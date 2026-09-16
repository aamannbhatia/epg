# teleora-epg

Builds the TV guide (EPG) for every Teleora channel that has one, using the
[iptv-org/epg](https://github.com/iptv-org/epg) grabber, and publishes it on the
`data` branch. The Teleora website downloads it from there.

**No schedule, no cron.** The website starts this workflow by itself whenever the
guide is older than about 20 hours, and picks up the new guide when it is ready.

## Set up (once, about 10 minutes)

1. **Create the repository.** On GitHub: New repository → name `teleora-epg` →
   **Public** (public repositories get free, unlimited Actions minutes) → Create.
2. **Add these files.** Upload everything from this folder, including the hidden
   `.github` folder. If your computer hides it, create the file on GitHub instead:
   Add file → Create new file → name `.github/workflows/epg.yml` → paste its contents.
3. **Allow the workflow to publish.** Settings → Actions → General →
   Workflow permissions → **Read and write permissions** → Save.
4. **Create a token for the website.** Your profile → Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token:
   - Repository access: **Only select repositories → teleora-epg**
   - Permissions → Repository permissions → **Contents: Read and write**
   - Expiration: the longest allowed (renew it before it runs out; the Teleora admin page shows an error if it does)
5. **Tell the website.** In Teleora's `config.php`:
   ```php
   define('EPG_GITHUB_REPO',  'your-github-name/teleora-epg');
   define('EPG_GITHUB_TOKEN', 'github_pat_...');
   ```
6. **First build.** Open any page on teleora.cc. The site sees there is no guide yet
   and starts the build. (Or: Actions → Build Teleora EPG → Run workflow.)
   The first build takes roughly 1–3 hours. After that, Admin → TV guide shows the counts.

## How it works

| Step | Where | What |
|---|---|---|
| plan | GitHub | Reads Teleora's channel ids from `https://teleora.cc/api/epg-ids.php`, picks the best guide source for each channel plus up to two fallbacks, splits the work into 20 parallel jobs |
| grab | GitHub | Runs the iptv-org grabber for 2 days of programmes. Channels that come back empty are retried on their fallback sources |
| build | GitHub | Converts everything into `teleora-epg.zip` (one small JSON file per channel) and `manifest.json`, and force-pushes them to the `data` branch |
| refresh | teleora.cc | A page view every 30 minutes pings `api/epg-refresh.php` in the background. It downloads a newer package if there is one, and starts a new build here if the guide is older than 20 hours |

## Coverage

About 3,900 of Teleora's 11,300 channels have a guide source in iptv-org/epg
(India about two thirds, United States about half). Channels without a source
simply show no schedule. Coverage grows as iptv-org adds sources.

## Troubleshooting

- **Admin says "No guide found on GitHub yet"**: the first build has not finished, or step 3 was skipped.
- **Admin says "HTTP 401" or "HTTP 404"**: the token is wrong, expired, or not given access to this repository.
- **A build job failed**: open Actions → the run → the red job. One failing site does not stop the others; the build step still publishes what was collected.

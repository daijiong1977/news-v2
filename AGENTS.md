# Kids News project working agreements

## Production changes

- `news-v2` is a live content pipeline. Make changes on a feature branch, run relevant checks, and create a pull request before merging into `main`. Do not push directly to `main` or merge without the user's approval or explicit exception.
- `kidsnews-v2` is the separate website deployment repository. A successful pipeline or report API call does not by itself prove that the public site has updated.

## Project Atlas report after every project change

1. With every completed project change, update `.project-atlas/project-status.json` **in the same code commit or PR** and push it. Use the existing Brain/Atlas `project_id` (`kids-news-website`); never infer an ID from a display name. Keep purpose, relevant branch roles, deployments and audiences, exact key-file paths, and dated lessons current. Preserve useful older lessons. Do not record credentials, tokens, personal data, or unverified deployments as live.
2. Confirm the commit containing that JSON is pushed to the named remote branch. From this repository root on the Mac running Atlas, send the JSON to the local API with the pushed `HEAD` SHA in `X-Source-Commit`. Read the bearer token only from `~/.config/project-list-api/token`; do not print, commit, or message it. Record the response's `changed` and `project_revision`.
3. A successful API response updates **local Brain only**. Check and report Brain GitHub `main` and the Atlas website **separately**; leave them pending unless their matching `source_commit` is verified. FeedStudy's local index refreshes on its separate 12-hour schedule.
4. On HTTP `400`, `404`, or `412`, inspect the JSON, true ID, pushed SHA, and any version conflict, then correct and retry. On connection failure, timeout, or server failure, follow the Brain MD fallback instructions only if the existing project page can be safely edited without interfering with another session; preserve its frontmatter, body, and lessons and use Brain's branch/PR process. Otherwise leave the pushed JSON intact, report "等待 Brain 同步", and send the repository, branch, commit, ID, and JSON path (no token) to the **Project List** Codex chat, thread `01a0dffa-4d44-7462-acde-1b3d9b430c68`.
5. If authorized to sync Brain GitHub, use an independent Brain worktree/branch and PR. Never commit onto another session's Brain branch. Atlas's regular check may otherwise complete Brain GitHub and website publication. This repository must not copy or run Atlas code.

Reference instructions on this Mac:

- `/Users/jiong/myprojects/creator/PM/project-atlas-report-worktree/docs/project-handoff.md`
- `/Users/jiong/myprojects/creator/PM/project-atlas-report-worktree/docs/project-status-template.json`
- `/Users/jiong/myprojects/creator/PM/project-atlas-report-worktree/docs/brain-project-report-fallback.md`
- `/Users/jiong/myprojects/creator/PM/project-atlas-report-worktree/docs/project-report-sync-operations.md`
- `/Users/jiong/brain/projects/kids-news-website.md`

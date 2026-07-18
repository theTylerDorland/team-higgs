# Changelog

What's new, improved, and fixed, newest first. Entries are grouped under
**New**, **Improved**, and **Fixed**.

## 2026-07-18

### New

- You can now keep a project risk register from the command line. `emctl
  risk` adds, updates, lists, and shows risks, each with a category and a
  severity, and a status you move from acknowledged through mitigated,
  accepted, realized, or closed. Decisions gain a history too:
  `emctl decision supersede` records that one decision replaces an earlier
  one, and `--significance` marks a decision as major or minor so routine
  choices stay separate from the headline ones. You can link a pull request
  to the task it implements with `--task` on `emctl pr open` and
  `emctl pr update`, and review a task's full status timeline with
  `emctl task history`. Add `--by` to `emctl task create` and
  `emctl task update` to record which role made each change.
<!-- PR #11 · docs/prd/observability.md -->

- You can now read and write all platform state from the command line with
  `emctl`. It covers projects, tasks, runs, PRs, reviews, artifacts,
  questions, decisions, metrics, learnings, debt, and retros, plus a
  `status` overview and a `migrate` command that sets up the database. Add
  `--json` to any command for machine-readable output.
<!-- PR #5 · BOOTSTRAP task 1 · docs/prd/emctl.md -->

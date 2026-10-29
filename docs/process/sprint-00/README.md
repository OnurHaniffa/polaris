# Sprint 0 process evidence

For CSE 311 report Section 5 (CI/CD).

| File | What it shows |
|---|---|
| `ci-red-run.png` | [Run 40931885751](https://github.com/OnurHaniffa/polaris/actions/runs/40931885751): a deliberate failure on PR #11. `test_healthz` was changed to expect 201, so `test` failed while `lint` and `deploy-check` passed, and the PR could not merge. Reverted in the next commit. |
| `ci-green-run.png` | [Run 40932428369](https://github.com/OnurHaniffa/polaris/actions/runs/40932428369): the same PR after the revert, all three checks green. |

Since 29 Oct 2026, `lint`, `test` and `deploy-check` are required checks on `develop` and `main` (`scripts/protect_branches.sh`).

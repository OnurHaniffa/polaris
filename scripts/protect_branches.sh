#!/usr/bin/env bash
# scripts/protect_branches.sh: apply branch protection to main and develop (spec §9.6).
# S0-01 runs it with no required checks (CI doesn't exist yet, and a required check that
# never runs would block every PR). S0-05 re-runs it with CHECKS="lint test deploy-check".
set -euo pipefail
REPO="OnurHaniffa/polaris"
CHECKS="${CHECKS:-}"

if [ -n "$CHECKS" ]; then
  contexts=$(printf '"%s",' $CHECKS)
  status_checks="{\"strict\": true, \"contexts\": [${contexts%,}]}"
else
  status_checks="null"
fi

for branch in main develop; do
  gh api -X PUT "repos/$REPO/branches/$branch/protection" --input - <<JSON
{
  "required_status_checks": $status_checks,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
  echo "protected $branch (required checks: ${CHECKS:-none yet})"
done

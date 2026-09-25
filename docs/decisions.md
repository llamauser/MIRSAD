# Decisions log

- **Dataset source**: `raw.githubusercontent.com/.../main/...` returned 404; the default branch is `master` (commit 0314b92d). Config now uses `master`; clone fallback kept.
- **Week index**: week = floor((date − 2013-01-02)/7) + 1 → weeks 1..52.

# Frozen: pilot test-set labels, v1 (2026-09-30)

The labels on the 30 frozen test photos (`data/splits/test_labeling.txt`) are
the evaluation ground truth. Every reported number is measured against this
exact file, so it never changes. A correction or a re-labeling (e.g. the face
audit, `docs/ISSUE_FACES_NOT_OBJECTS.md` §7) goes into a **new project and a
new version**, `pilot-test-v2-<date>.json`; v1 stays as it is, so old and new
numbers can always be compared.

| What | Value |
| --- | --- |
| Label Studio project | `pilot-test-cans-glass`, id 3, on `atpg` |
| Export (full JSON) | `data/label_studio/exports/pilot-test-v1-2026-09-30.json` |
| sha256 | `cc83fee4d04bf2c3a9b1834b1dbf421934228f808b2d8d77fbea5e2b05f93b4a` |
| Label config at freeze | `data/label_studio/exports/pilot-test-v1-2026-09-30.config.xml` (sha256 `aea43de62d2ff4eb7c3f72032f96fb94f2beead670793f9feb7cf35d2312032f`) |
| Database dump at freeze | `backups/label-studio/ls-backup-2026-09-30-freeze-pilot-test.sql` |
| Contents | 30 photos, 1 submitted annotation each, 2,851 boxes |
| Meaning of a box | every visible product ("all objects"), not faces only |

Known and accepted at freeze:

- Photo #18 (task 19) has an unsaved draft that would remove 4 grey
  `product` boxes. It was left out on purpose; the submission is what counts.
- A few near-duplicate grey boxes remain: 1 pair on #2, #18, #19; the same box
  4 times on #15 (x≈85%, y≈64%). They affect detector numbers slightly, never
  the share (grey boxes are in no share).
- 4 `COMPETITOR_canned` and 42 `COMPETITOR_glass` boxes are untracked brands.

## What protects it

- The export files are read-only on disk (`chmod 444`), and their sha256 is
  above. `shelf-eval` prints the sha256 of the labels it read in its summary
  and `run_args.json`, so every number can be traced to this file.
- `shelf-ls-setup` refuses the project by title (`FROZEN_TITLES` in
  `src/face_counter/label_studio/setup_project.py`) before copying or sending
  anything, and it no longer has a default project.
- In Label Studio, the project's description and instructions say FROZEN
  (English and Persian); the instructions pop up when a task opens.

Label Studio Community has no read-only mode, so a person with an account can
still edit in the browser. Check it has not happened by exporting and
comparing annotation signatures with this file (as done at freeze time), not
by eye.

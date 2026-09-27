# Labeling the test set for the pilot: step by step

For the person labeling the 30 frozen test photos: from nothing to a saved
export file. What to label is in `docs/labeling_guide.md`, section "Pilot";
this page is only about the tool.

Decided 2026-09-27: one labeler, **one pass** (fix boxes and name drinks on the
same visit), brand-level names (`Kix-Max_canned`, not the flavour).

## Words used here

- **Project:** one labeling job in Label Studio: a set of photos plus a list of
  labels.
- **Task:** one photo inside a project.
- **Prediction:** a box the detector drew. It shows up drawn on the photo, but
  it counts for nothing until you submit.
- **Annotation:** what you submit: the boxes and labels as you left them. This
  is the ground truth every accuracy number is computed against.
- **Export:** a file of all your annotations, downloaded from Label Studio.
  This file is the deliverable.

## 0. Build the files (on this machine)

    uv run shelf-label-prep --list data/splits/test_labeling.txt --level scope \
        --predictions runs/bakeoff/20260927-114232/ls_predictions_yolo26l-sku110k.json \
        --stage-images data/label_studio/images

It writes three things into `data/label_studio/`:

| File | What it is |
| --- | --- |
| `images/` | The 30 photos, ready for any browser (4 HEIF/MPO converted to JPEG, upright) |
| `labeling_config_scope.xml` | The label list: 7 labels with number keys |
| `tasks_test_labeling.json` | The 30 tasks, each with YOLO26l's boxes pre-drawn |

## 1. Upload the photos to the server

Copies only; nothing on the server is deleted. Never add `--delete`.

    ssh atpg 'df -h / && mkdir -p /home/data/label-studio-photos/raw/images'
    rsync -av data/label_studio/images/ atpg:/home/data/label-studio-photos/raw/images/

Check that the container sees them (expect 30 or more files):

    ssh atpg 'cd /home/data/label-studio && docker compose exec label-studio ls /label-studio/files/raw/images | wc -l'

## 2. Create the project (in the browser, once)

Open `http://<server>:7071` and log in.

1. **Organization > Members:** remove any account you don't recognize (the
   instance is public).
2. **Create Project**, named `pilot-test-cans-glass`. Skip the Data Import tab.
3. **Labeling Setup** tab: choose **Custom template**, open the **Code** view,
   delete what is there, and paste the whole of
   `data/label_studio/labeling_config_scope.xml`. The preview should show 7
   labels, `product` in grey. **Save**.

## 3. Project settings

Open the project, then **Settings** (top right).

1. **Cloud Storage > Add Source Storage > Local files.**
   - Absolute local path: `/label-studio/files/raw/images`
   - Leave the file filter empty, and **don't** tick "Treat every bucket
     object as a source file".
   - **Check Connection**, then **Add Storage**. **Do not press Sync**: the
     tasks come from the import in step 4. This entry only gives Label Studio
     permission to show the files.
2. **Annotation:** turn on **Use predictions to prelabel tasks** and choose
   `yolo26l-sku110k` in the drop-down. **Save**. Without this the photos open
   empty.

## 4. Import the tasks

**Import** (top of the task list) > upload
`data/label_studio/tasks_test_labeling.json` > **Import**. You should get 30
tasks, and the Predictions column shows one prediction each.

Open one task. If the photo shows as broken ("There was an issue loading URL"),
either step 1 didn't copy it or step 3.1 is missing; see
`deploy/label-studio/README.md`, "Loading photos".

## 5. Label

1. Once per browser: in the labeling screen, open the **gear icon** and turn on
   **Show labels inside the regions**.
2. Follow `docs/labeling_guide.md`, "Pilot". In short: fix the boxes, then click
   each can or glass bottle and press its number (1-6). Leave the rest as
   `product` (7).
3. Useful controls:
   - Click a box to select it; `Backspace` or `Delete` deletes it.
   - Draw a new box: press the label's number first, then drag on the photo.
   - Zoom with the mouse wheel; hold `Space` and drag to move around.
   - `Ctrl+Z` undoes.
4. Press **Submit** when a photo is done. After submitting, the button reads
   **Update**: use it after later corrections.
5. Take the three guide screenshots on the way, when those photos are finished
   (next section).

About 10 to 20 minutes per photo, so plan on a day.

## 6. The three labeling-guide screenshots

When each of these is finished, take a screenshot of the Label Studio screen
(labels inside the regions on) and save it under the given name:

| Photo | Save as |
| --- | --- |
| `6a9eb3a923de307d656e13a7` (supermarket aisle) | `docs/labeling_guide/1_aisle.png` |
| `6a817d5c3d53df2b4e45e836` (fridge with glare) | `docs/labeling_guide/2_fridge_glare.png` |
| `6a708b39ddee25bd587e2e06` (crowded small shop) | `docs/labeling_guide/3_small_shop.png` |

Find a photo by typing its id in the task list's search or filter. They are
committed to git with the guide (private repo).

## 7. Export the annotations, after every session

1. In the project's task list: **Export** > **JSON** (not "JSON-MIN", and not
   COCO: both drop information) > **Export**.
2. Save the downloaded file as
   `data/label_studio/exports/pilot-test-<date>.json`, e.g.
   `pilot-test-2026-09-28.json`. Keep every export and never overwrite one.
   The folder is outside git on purpose (company photos).
3. Then tell Hermes the file is there; the evaluation script reads it.

Also take a database dump now and then (all projects, all users):

    ssh atpg 'cd /home/data/label-studio && docker compose exec -T db sh -c '\''pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"'\''' > ls-backup-$(date +%F).sql

**Never run `docker compose down -v`** or any volume or prune command on the
server: the volumes hold every annotation, and deleting them can't be undone.
`docker compose stop` is safe.

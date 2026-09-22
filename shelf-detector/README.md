# Shelf Detector: Phase 0

Counts product faces on store-shelf photos and computes share of shelf.
This folder is **Phase 0 (foundations)**:
- export the photos safely from MongoDB,
- fix a leakage-free test set,
- prepare labeling in a locked-down Label Studio.

```
configs/
  export.yaml            where photos + metadata live in MongoDB (EDIT FIRST)
  classes.csv            BRAND_CATEGORY_SKU class list (template; replace with the real one)
scripts/
  export_photos.py       GridFS -> data/raw/images + data/raw/manifest.csv (read-only, resumable)
  make_splits.py         train/val/test BY STORE + photo lists to label first
  prepare_label_studio.py  labeling config XML + task JSON for a photo list
deploy/label-studio/     hardened docker-compose for Label Studio
docs/
  labeling_guide.md      rules every labeler follows
  requests.md            messages to send for the class list and packshots
tests/                   end-to-end test on a fake MongoDB (no server needed)
```

## Day 1: lock down Label Studio

Your current instance lets anyone sign up. Do these steps before putting company photos in it:

1. Recreate it with `deploy/label-studio/docker-compose.yml`. Copy `.env.example` to `.env`
   first and fill it in. The compose file:
   - disables open signup,
   - binds the port to one interface only,
   - mounts the photos read-only,
   - caps memory at 2 GB.
2. To keep your existing projects, first find the current container's data volume
   (`docker inspect <container> | grep -A3 Mounts`). Then point `ls-data` at it, as an
   external volume or a bind mount.
3. In **Organization > Members**, remove any account you don't recognize.
4. Add labelers with **invite links** only.

Note: ports published by Docker bypass `ufw`. Binding to a specific IP (`LS_BIND_IP`) is
what actually restricts access.

## Read-only Mongo user (run once, as admin)

The export only ever reads. Give it a user that *can* only read:

```js
use admin
db.createUser({ user: "shelf_reader", pwd: "<long random>",
                roles: [{ role: "read", db: "<your app db>" }] })
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # set MONGO_URI (read-only user)
# edit configs/export.yaml: database, collection, field paths

python -m pytest -q                       # sanity check on fake data (no DB touched)

python scripts/export_photos.py --limit 20   # small test export; open data/raw/manifest.csv
python scripts/export_photos.py              # full export (resumable; run after hours)

python scripts/make_splits.py                # -> data/splits/
python scripts/prepare_label_studio.py --list data/splits/test_labeling.txt --level sku
python scripts/prepare_label_studio.py --list data/splits/label_batch_01.txt --level brand
```

### Finding your field paths

Open one photo's metadata document in Compass or `mongosh`:

```js
db.<collection>.findOne({}, {_id: 0})
```

- Copy the paths for store, visit, date, rep, and city into `configs/export.yaml`. Use dot
  notation for nested fields, e.g. `store.id`.
- If the metadata sits inside `fs.files.metadata` instead of its own collection, set
  `source: gridfs` and use paths like `metadata.store_id`.

After the first `--limit 20` run, check `manifest.csv`. **Empty `store_id` values mean
the mapping is wrong.** The split script also warns about this, because without a store
the test set can leak.

## Load into Label Studio

1. Create a project. Paste `data/label_studio/labeling_config_<level>.xml` into
   **Settings > Labeling Interface > Code**.
2. **Settings > Cloud Storage > Add Source Storage > Local files**, with absolute path
   `/label-studio/files/raw/images`. Label Studio only serves local files covered by a
   storage entry. Don't click "Sync": tasks come from the JSON import.
3. **Import** `data/label_studio/tasks_<list>.json`.

Label the **test set first** (`test_labeling.txt`, 30 photos). It must stay fixed. The
split is a stable hash of `store_id`, so re-running after new exports never moves a store
between train and test.

## Disk and load

- A full export of ~20k phone photos is roughly **60 to 100 GB**. Check free space
  first (`df -h`). If it's tight, export to a separate disk: set `export.out_dir` to an
  absolute path.
- `throttle_seconds` and the batched cursor keep load on MongoDB low. Still, run the full
  export outside working hours.

## Next (Phase 1)

- SKU-110K detector
- pre-labeling the test set
- reference gallery from packshots
- embedding matcher and evaluation script

See the roadmap doc.

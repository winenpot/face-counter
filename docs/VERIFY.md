# Verify this yourself

Every claim I made, as a command you can run. Nothing here writes: the database
commands are `count`/`find`/`aggregate` only, and the shell commands read files
or run the test suite.

Run everything from the repo root:

    cd /home/winenpot/code/face-counter

---

## 1. One command that checks every database claim

    uv run python scripts/verify_atpg_claims.py

Prints two columns — what the database says **now**, and what I reported on
2026-09-22. `atpg` is live, so "now" should be equal or higher; a lower number
means documents were deleted.

The last two lines are the open blocker. They currently read `root` and `8`
mutating actions, and should read `read` and `0` once `shelf_reader` is in use.

The script never prints the connection string, and on error prints only the
exception type — pymongo builds its messages out of the URI, so a normal
traceback would leak the server address.

---

## 2. The two claims that most affect Phase 1

Connect with `mongosh` and `use atpg`, then:

### `shelf_thumb` duplicates `shelf` — the leakage trap

    // do full-size photos and thumbnails share a photo_id?
    db['photos.files'].aggregate([
      {$group: {_id:'$photo_id', types:{$addToSet:'$photo_type'}}},
      {$match: {types:{$all:['shelf','shelf_thumb']}}},
      {$count: 'photos_with_a_thumbnail_copy'}
    ])

A non-zero count means exporting both types puts a photo and its own downscaled
copy in the dataset. Land them in different splits and that is test-set leakage.

### The export config points at fields that do not exist

    db['photos.files'].findOne()

Compare the keys against `configs/export.yaml`. The config maps `visit_id`,
`rep_id`, `city` and `created_at`; the document has none of them.

---

## 3. Check it in the Mongo shell instead

If you would rather not trust my Python, the same facts in `mongosh`. Connect
with your own credentials, then:

    use atpg

    // the collections exist, and how big they are
    db.getCollectionNames().filter(c => c.startsWith('photos'))
    db['photos.files'].estimatedDocumentCount()      // ~24,175 and rising
    db['photos.chunks'].estimatedDocumentCount()     // ~190,045 and rising

    // only 'shelf' is trainable; the *_thumb types are derivatives
    db['photos.files'].aggregate([
      {$group:{_id:'$photo_type', n:{$sum:1}, gb:{$sum:'$length'}}},
      {$project:{n:1, gb:{$round:[{$divide:['$gb',1073741824]},1]}}},
      {$sort:{n:-1}}
    ])

    // store_code is stored as BOTH int and string
    db['photos.files'].aggregate([
      {$group:{_id:{$type:'$store_code'}, n:{$sum:1}}}
    ])

    // ...but no single store uses both, so normalising with str() is safe
    db['photos.files'].aggregate([
      {$match:{store_code:{$ne:null}}},
      {$group:{_id:{v:'$store_code',t:{$type:'$store_code'}}}},
      {$group:{_id:{$toString:'$_id.v'}, types:{$addToSet:'$_id.t'}}},
      {$match:{'types.1':{$exists:true}}},
      {$count:'stores_using_both_types'}          // expect: no results
    ])

    // one photo document, to compare against configs/export.yaml
    db['photos.files'].findOne()

    // the region source that the photos themselves lack
    db.location.findOne({}, {code:1, name:1, region:1})

    // what this credential can actually do
    db.runCommand({connectionStatus:1, showPrivileges:true}).authInfo.authenticatedUserRoles

The last one is the important one. If it returns `root`, the export is running
as a superuser over all 20 databases on that server.

---

## 4. Check the credential is the blocker I said it is

In `mongosh`:

    db.runCommand({connectionStatus:1}).authInfo.authenticatedUserRoles

`root` means the export runs as a superuser over all 20 databases on the server.
After you create `shelf_reader` and point `.env` at it, this should return a
single `read` role on `atpg`.

Then prove it cannot write. Start a **new** mongosh as that user — `use`
switches database, not user, so you cannot become `shelf_reader` from a session
you opened as someone else:

    mongosh -u shelf_reader -p --authenticationDatabase admin
    use atpg                              // the DATABASE, not the user
    db.perm_test.insertOne({x: 1})        // must fail: not authorized

Use a throwaway collection name, never `photos.files`. If you are still
connected as an admin user the insert succeeds, and a document with no
`length`/`chunkSize` sitting in the real GridFS collection can break clients
that read it.

If that insert succeeds, the new user did not get the role you meant.

---

## 5. Check the repo changes (no database needed)

    # tests pass
    uv run pytest

    # the export refuses to run on the unedited config, instead of
    # silently "succeeding" with an empty manifest
    uv run shelf-export --limit 1          # expect: SystemExit about placeholders

    # all four CLIs are installed
    uv run face-counter
    for c in shelf-export shelf-splits shelf-label-prep; do uv run $c --help >/dev/null && echo "$c OK"; done

    # shelf-detector/ is gone and nothing references it
    ls shelf-detector 2>&1                 # expect: No such file or directory
    grep -rn "shelf-detector/" --exclude-dir=.git --exclude-dir=.venv \
         --exclude=VERIFY.md .             # expect: no output

    # the git history, one concern per commit
    git log --oneline
    git show --stat 385d074                # the refactor
    git show 652ebbd                       # the export guard + its test

---

## 6. Check the Label Studio compose file

    cd deploy/label-studio

    # A. without a .env it must FAIL, naming each missing value
    #    (run in a temp dir so your real .env is not picked up)
    mkdir -p /tmp/lscheck && cp docker-compose.yml /tmp/lscheck/
    (cd /tmp/lscheck && docker compose config)
    # expect: "required variable POSTGRES_PASSWORD is missing a value" etc.

    # B. with the example values it must PARSE
    cp .env.example /tmp/lscheck/.env
    (cd /tmp/lscheck && docker compose config | grep -A5 'ports:')
    # expect: host_ip: 127.0.0.1   <- bound to one interface, not 0.0.0.0

    # C. the photo mount and local-files settings the task URLs depend on
    (cd /tmp/lscheck && docker compose config | grep -E 'LOCAL_FILES|/label-studio/files|read_only')

    rm -rf /tmp/lscheck

Do **not** `docker compose up` this against your existing Label Studio yet —
first boot applies irreversible schema migrations. Migration steps are in
`deploy/label-studio/README.md`.

---

## 7. What I could not verify, and you can

These are outside anything I can reach:

- **Is the running Label Studio actually hardened?** I only fixed the committed
  compose file. Check the live instance's Organization → Members list, and
  whether its port is reachable from outside the office:
  `ss -ltnp | grep 8081` on the server, and try the URL from another network.
- **Is `sardar` shelf photography?** 3,794 photos, 13.3 GB. If it is, the usable
  corpus roughly doubles; if it is storefront/banner photography it must stay
  out. Only the business knows.
- **Did anything write to the database during my survey?** Everything I ran was
  read-only, but you do not have to take that on faith — the server's profiler
  or the oplog will show it:

      use local
      db.oplog.rs.find({ns:/^atpg\./, op:{$in:['i','u','d']}}).sort({$natural:-1}).limit(20)

  Expect nothing from the `face-counter-*` appnames.

# Verify this yourself

Every claim I made, as a command you can run. Nothing here writes: the database
commands are `count`/`find`/`aggregate` only, and the shell commands read files
or run the test suite.

Run everything from the repo root:

    cd /home/winenpot/code/face-counter

---

## 1. One command that checks every database claim

    uv run python scripts/verify_atpg_claims.py

Prints `claimed` vs `actual` for each number, with PASS/FAIL and a tally. It
never prints the connection string, the credentials, or the server host — the
output (including any error) is scrubbed first.

**Expected today: `21/22 checks passed`.** The single FAIL is section 9, the
`root` credential — it stays failing until the read-only user exists, which is
the point of the check.

Counts are compared with tolerance, not exact equality: `atpg` is live and
photos keep arriving (it grew by 28 files between my survey and this write-up).
A count *below* the surveyed number fails, because that would mean deletion
rather than growth.

---

## 2. The two claims that most affect Phase 1

If you only check two things, check these.

### `shelf_thumb` duplicates `shelf` — the leakage trap

    uv run python -c "
    from face_counter.config import PROJECT_ROOT
    import os,sys
    sys.path.insert(0,str(PROJECT_ROOT/'scripts'))
    from pymongo import MongoClient
    uri=[l.split('=',1)[1].strip() for l in open(PROJECT_ROOT/'.env') if l.startswith('MONGO_URI')][0]
    f=MongoClient(uri,appname='verify')['atpg']['photos.files']
    a={d['photo_id'] for d in f.find({'photo_type':'shelf'},{'photo_id':1}).limit(3000)}
    b={d['photo_id'] for d in f.find({'photo_type':'shelf_thumb'},{'photo_id':1}).limit(3000)}
    print('shared photo_id:',len(a&b),'-> thumbs are the SAME photos, not extra data')
    "

A non-zero result means exporting both `shelf` and `shelf_thumb` would put a
photo and its own downscaled copy in the dataset. In different splits, that is
test-set leakage.

### The export config points at fields that do not exist

    uv run python -c "
    from face_counter.config import PROJECT_ROOT
    from pymongo import MongoClient
    uri=[l.split('=',1)[1].strip() for l in open(PROJECT_ROOT/'.env') if l.startswith('MONGO_URI')][0]
    f=MongoClient(uri,appname='verify')['atpg']['photos.files']
    d=f.find_one()
    print('actual fields:',sorted(d))
    for x in ('visit_id','rep_id','city','created_at','metadata'):
        print(f'  {x:<12}',f.count_documents({x:{'\$exists':True}},limit=1),'docs')
    "

Compare `actual fields` against `configs/export.yaml`. The config maps
`visit_id`, `rep_id`, `city` and `created_at`; none are present.

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

    uv run python -c "
    from face_counter.config import PROJECT_ROOT
    from pymongo import MongoClient
    uri=[l.split('=',1)[1].strip() for l in open(PROJECT_ROOT/'.env') if l.startswith('MONGO_URI')][0]
    c=MongoClient(uri,appname='verify')
    a=c.admin.command({'connectionStatus':1,'showPrivileges':True})['authInfo']
    acts=set()
    for p in a.get('authenticatedUserPrivileges',[]): acts|=set(p.get('actions',[]))
    bad=sorted(acts & {'insert','update','remove','dropDatabase','dropCollection','shutdown','createUser','grantRole'})
    print('roles      :',[r['role'] for r in a['authenticatedUserRoles']])
    print('can mutate :',bad or 'nothing (good)')
    print('total actions granted:',len(acts))
    "

After you create `shelf_reader` and switch `.env` over, `can mutate` should read
`nothing (good)` and the total should drop from 136 to a handful.

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

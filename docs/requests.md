# Requests to send (Phase 0, day 1)

## 1. Class list (to sales / business analysts)

> Hi, for the shelf-counting project I need the full list of products we want to count,
> ours and main competitors', by **Day 3**.
>
> Please fill in the attached `classes.csv`, one row per product:
>
> | class_name | brand | category | sku | is_ours |
> | --- | --- | --- | --- | --- |
> | Kix-Max_canned_blueberry | Kix-Max | canned | blueberry | 1 |
>
> - `category` is the pack type (canned, glass, PET, and so on).
> - Competitors: list the ones you track on the dashboard. The rest will be counted as
>   "other competitor" per category.
> - If two products look the same on a shelf (same pack, only size differs), please tell me.

## 2. Packshots (to marketing)

> Hi, could you send product photos (packshots) for each of our products, and for the
> competitors' products if you have them, by **Day 5**?
>
> - 2 to 5 images per product, front view. Any size is fine, the original files are best.
> - File or folder names should match the product names in the class list.
>
> They're used as reference images so the system can recognize each product on shelves.

**Status 2026-09-24:** partly answered from other sources, no longer blocking
Phase 0. 242 images were extracted from the sales invoice's own embedded image
column, named by `class_name`, and seed a first reference gallery. Studio
photography exists for 2 of 8 brands (`configs/Product/Kixmax/`, `Torsh-X/`)
but is named by flavor or mockup rather than `class_name`, so nothing maps it
to a class yet. The ask above still stands for full coverage: **all 8 brands,
2–5 front views per SKU, named by `class_name`.** Please skip multi-product
mockups (e.g. a 24-can bundle shot) — a reference image must show one product
face, or it teaches the matcher the wrong thing.

## 3. Original uploads before recompression (to the field app developer)

> Hi — question about how the app stores shelf photos.
>
> Looking at the exported photos, it's clear something recompresses them
> server-side after upload: 1,225 of 9,704 photos (12.6%) are within 2 KB of
> exactly 4 MiB, and 950 of those are the *identical* byte size (4,194,868).
> There's also a downscaled population — 221 photos at 810x1080, 214 at
> 960x1280, 200 at 1200x1600. I gather this was to work around upload problems,
> which makes sense.
>
> The question: **do the original, pre-compression files still exist anywhere**
> (object storage, a backup, a staging bucket), or does the app overwrite them?
>
> Why it matters: we're counting small products packed tightly on a shelf, and
> JPEG recompression destroys exactly that kind of fine detail. If the originals
> are still around, training on them would be a free accuracy improvement. If
> they're gone, no problem — we'll measure the compressed tiers separately and
> report honestly. Either answer is useful; I just need to know which.
>
> Also useful if easy: the resize/quality settings and when they changed, so we
> can tell which photos went through which pipeline.

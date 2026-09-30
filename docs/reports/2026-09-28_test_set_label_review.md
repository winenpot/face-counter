# Test-set label review, 2026-09-28

Review of all 30 frozen test photos in Label Studio project
`pilot-test-cans-glass` (id 3), from the export
`data/label_studio/exports/pilot-test-2026-09-28-review.json`. **To address
next session.** The 30 photos stay frozen; only the labels change.

## Verdict: labels not final yet

> **Superseded 2026-09-29 (§1 closed by decision).** Grey `product` boxes
> stay grey, and only **targeted** competitors are named (list in
> `docs/PILOT.md`, Scope). The pilot's number is our share against those
> competitors, so the untargeted cans and glass in §1 no longer need naming.
> A box with no label counts as `product`, so the #15 item in §2 is
> dropped too. What remains is the rest of §2, a rename pass for targeted
> competitors, and §3.

Boxes are in good shape on #1-#23. The problem is **naming**: many
competitor cans and glass bottles are still grey `product`, which makes our
share of shelf look larger than it is. Photos #24-#30 look unfinished: their
boxes are exactly the pre-drawn ones, and each took about a minute.

Grey `product` boxes on things that are not cans or glass bottles can stay
grey. **Every can and glass bottle, ours or a competitor's, must be named.**

## To do, in order

### 1. Name the unnamed cans and glass bottles

Select a box, press **5** (competitor can) or **6** (competitor glass), or
1-4 for ours. A brand you can't read counts as a competitor unless it's
clearly ours.

- [X] **#25** Fridge full of cans: 5 Kix-Max named; about 25 competitor cans
      (King, Life, Monster, Red Bull, Big Bear...) still grey.
- [X] **#30** Dozens of cans and glass bottles, only 7 named. Also check boxes
      (unchanged from the detector).
- [X] **#29** 3 named; the juice fridge (Sunich etc.) has many glass bottles.
      Also check boxes.
- [ ] **#16** 16 glass bottles named; the two top rows of cans (Monster, Life,
      Hype, One, Nescafe...) are grey.
- [ ] **#14** 10 Kix-Max cans named; the Tarsh/Rani cans and the glass
      bottles lower down (Istak, Aloe...) are grey.
- [ ] **#26** 2 Kix-Max glass named; Coca-Cola, Fanta, Sprite and Efes cans
      and about 10 glass bottles are grey.
- [ ] **#22** Cans named well; Vimto, Barbican, Qube and Zam Zam glass
      bottles are grey.
- [ ] **#7** Some named; many cans and glass bottles on the lower shelves
      still grey.
- [ ] **#9** Some glass named; the Edge/King/Life cans and lower-fridge glass
      bottles are grey.
- [ ] **#24, #27, #28** Unchanged from the detector: check the boxes (#27 and
      #28 are no-drinks, so boxes only).

### 2. Small fixes

- [ ] ~~**#15** 9 boxes with no label at all: label or delete them.~~ Not needed
      (2026-09-29): no label counts as `product`.
- [ ] **#6, #17** Unsaved drafts newer than the submission: open and press
      **Update**, or the changes stay unsaved.
- [ ] **#23** Two submitted versions: delete the older one.
- [ ] **#2, #15, #18, #19** 1-3 near-duplicate box pairs each: keep one.
- [ ] **#20** Tagged no-drinks, but there may be glass bottles at the corner:
      check.
- [ ] **#21** Tagged no-drinks, but there is a small glass-bottle shelf at the
      back: check.

### 3. Then

- [ ] Export JSON (`docs/PILOT_LABELING.md` §7) and ask for the same review
      again. When it comes back clean, the labels are marked final and the
      evaluation script (`PILOT.md` step 6) starts from that export.

## Already good

- Scene type and capture/photo tags on all 30.
- Naming on #10-#14 and #18-#19 looks right.
- Real box work on #1-#23: 349 boxes drawn by hand, 294 deleted.
- The 6 no-drinks photos #1, #5, #8, #23, #27, #28 were checked by eye and
  are correct. No-drinks photos stay in the frozen set: they count toward
  detector recall and are only left out of the share of shelf.

## Numbers from this export (for reference, not final)

- 30/30 submitted; 2,869 boxes (2,650 `product`, 99 `COMPETITOR_glass`,
  47 `Kix-Max_canned`, 33 `COMPETITOR_canned`, 13 `Kix-Max_glass`,
  12 `TorshX_glass`, 6 `TorshX_canned`, 9 with no label).
- Detector vs labels at IoU 0.5: recall 0.878, precision 0.896. Photos
  #24-#30 flatter both, because they were not corrected.
- Scene types: 12 open fridge, 8 shelf aisle, 5 mixed, 4 glass-door fridge,
  1 counter. 22 of 30 photos contain cans or glass bottles.
- Labeling time (Label Studio's own timer): median 8 min per photo, 6.3 h in
  total.

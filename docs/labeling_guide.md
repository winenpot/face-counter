# Labeling guide: shelf product faces

Version 0.1. Every labeler follows this page. If the page doesn't answer a case, write
it in the task's **Notes** box and ask. Don't guess differently from everyone else.

## What to box

- **One box per product face.** A face is one unit whose front (label side) is visible
  in the **front row** of the shelf or fridge.
- **Tight boxes.** Draw around the visible product, not its shadow or the price tag.
- **Label every product in the photo, ours and competitors'.** An unlabeled product
  teaches the model that it's background.

## Class names

- Format: `BRAND_PACKTYPE_SKU`, for example `Kix-Max_canned_blue-berry`. The pack
  type is what you see: `canned`, `glass` (glass bottle), `milk-straw`, and so on.
- Competitors: `COMPETITOR_<pack type>`, by what the product physically is, for
  example `COMPETITOR_canned`, `COMPETITOR_glass`, `COMPETITOR_oil`,
  `COMPETITOR_dressing`, `COMPETITOR_plastic-bottle`. If none fits, use
  `COMPETITOR_other` and write what it is in Notes. Use a named
  competitor class only if it is in the list. Always box competitors — a missing
  competitor box makes our share of shelf look bigger than it is.
- Glass bottle and plastic bottle are different: `glass` is glass only.
- Products that are nothing like anything we sell or report on (shampoo,
  detergent, …): box them as `out_of_scope`. Don't label them as competitors.
- Press **Shift+F** and type to search the class list.
- Once per browser: open the **gear icon** (Settings) in the labeling screen and turn on
  **Show labels inside the regions**, so every box shows its class on the photo.
  It's off by default, which makes a wrong or missing class easy to miss.

## Edge cases

| Situation | Rule |
| --- | --- |
| Product behind the front row (second row visible) | Don't box |
| Front face at least 50% visible | Box it, box only the visible part |
| Front face less than 50% visible, or only the side visible | Don't box |
| Stacked units (one on top of another, both front row) | Box each one |
| Behind fridge glass, label readable | Box it |
| Glare or blur makes the flavor unreadable, brand readable | Box with the brand's closest class, write `unsure-sku` in Notes |
| Can't tell the brand at all | Don't box; write `unknown product` in Notes |
| Multipack or shrink-wrapped tray | One box for the whole pack, write `multipack` in Notes (to be decided) |
| Product on a promo stand or floor display | Box it like a shelf product |
| Product image on a poster, price tag, or cardboard | Don't box: it's not a product |

## Before you submit

- Zoom in once across the whole photo and check for missed products.
- Aim for about 10 to 20 minutes per photo. If a photo takes longer than 30 minutes,
  skip it and tell the project lead.

## Pilot: cans and glass bottles (test set, from 2026-09-27)

The pilot measures our share of cans and of glass bottles. It labels in **one
pass**, and it names brands, not flavours.

Every photo opens with boxes already drawn by a detector, all labeled `product`
(grey).

1. **Fix the boxes, on every product, not only drinks.** Delete boxes on
   reflections, empty dark spots, price tags and posters. Delete the extra box
   when one product has two. Draw a box on every product the detector missed.
   Tighten boxes that are clearly off. The rules above ("What to box", "Edge
   cases") still decide what counts.
2. **Name every can and every glass bottle.** Click the box, then press its
   number or click the label:

   | Key | Label | Use for |
   | --- | --- | --- |
   | 1 | `Kix-Max_canned` | Any Kix-Max can, any flavour |
   | 2 | `Kix-Max_glass` | Any Kix-Max glass bottle, any flavour |
   | 3 | `TorshX_canned` | Any TorshX can, any flavour, energy drink included |
   | 4 | `TorshX_glass` | Any TorshX glass bottle, any flavour |
   | 5 | `COMPETITOR_canned` | Any other can |
   | 6 | `COMPETITOR_glass` | Any other glass bottle |
   | 7 | `product` | Everything else: plastic bottles, cartons, snacks, oil... |

3. **Leave everything else as `product`.** Don't use `out_of_scope` or
   `COMPETITOR_other` in the pilot. `product` means "not named yet", and a
   later round names those boxes without redrawing them.

Unsure whether a bottle is glass or plastic? Leave it `product` and write
`glass?` in Notes. A can or glass bottle whose brand you can't read is a
competitor unless it's clearly ours.

## Examples

Screenshots live in `docs/labeling_guide/` (company photos: private repo only).
Take them from the Label Studio screen after the photo is finished, with **Show
labels inside the regions** on.

1. A supermarket aisle: `docs/labeling_guide/1_aisle.png`, from photo
   `6a9eb3a923de307d656e13a7`

   ![Supermarket aisle](labeling_guide/1_aisle.png)

2. A fridge with glass and glare: `docs/labeling_guide/2_fridge_glare.png`, from
   photo `6a817d5c3d53df2b4e45e836`

   ![Fridge with glare](labeling_guide/2_fridge_glare.png)

3. A crowded small shop: `docs/labeling_guide/3_small_shop.png`, from photo
   `6a708b39ddee25bd587e2e06`

   ![Crowded small shop](labeling_guide/3_small_shop.png)

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

- Format: `BRAND_CATEGORY_SKU`, for example `Kix-Max_canned_blueberry`.
- Competitors: use their SKU class if it's in the list, otherwise `COMPETITOR_<category>`,
  for example `COMPETITOR_canned`.
- Press **Shift+F** and type to search the class list.

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

## Examples

Add three annotated screenshots here once the first photos are labeled:
1. A supermarket aisle
2. A fridge with glass and glare
3. A crowded small shop

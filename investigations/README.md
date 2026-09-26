# investigations/

Throwaway probes kept for the record — not part of the pipeline, not imported by
anything, not covered by tests. Each one answered a question once; they are here
so the answer is findable, not because they are meant to be re-run.

Nothing here is a dependency. Delete freely.

Rules for what may land in this folder:
- **No secrets and no customer data**, including in notebook *output* cells.
  Notebook outputs are committed as-is, so a cell that printed a Mongo URI, a
  price list or a buyer name is a leak in git history, not a scratch file.
  `configs/classes.csv` (product names only) is fine; anything derived from
  `configs/*.xlsm` is not.
- No shelf photos or crops — those belong to DVC, not git.

## Contents

- `classes_csv_shape.ipynb` — first look at `configs/classes.csv` with pandas:
  confirmed the column shape (`class_name`, `brand`, `category`, `sku`,
  `is_ours`) and that `class_name` is the `brand_category_sku` join. 2026-09-26.
- `classes_names.txt` — the flat `class_name` list dumped from that notebook, in
  the form the identifier's gallery folders will be named after. Regenerate with
  `pandas.read_csv("configs/classes.csv").class_name` rather than editing it.

"""Stage 2 of the two-stage design: name a detector's crop (PILOT.md step 4b).

A detector finds faces (``evaluation/detector.py``); this package names them
by nearest match against a reference gallery, so adding a SKU is adding
images here, never retraining.
"""

# JWST Cycle 4 Transmission Spectroscopy Targets

This file (`jwst_cycle4_targets.csv`) is reserved as an independent forward-test ground truth dataset.

## Instructions
Please populate `jwst_cycle4_targets.csv` directly from the official **STScI JWST Cycle 4 Approved Science Programs List** once available:
- https://www.stsci.edu/jwst/science-execution/approved-programs

### Format:
```csv
planet_name,program_id,source_url
```

### Notes:
- Only include confirmed exoplanets selected for **transmission or emission spectroscopy** programs.
- Keep the header intact: `planet_name,program_id,source_url`.
- Once populated, run `python scripts/forward_test.py` to evaluate how many Cycle 4 targets land in our model's top 25, 50, and 100 predictions.

#!/usr/bin/env sh
# Full reproduction: download Treasury data, build panels, train + validate, export the site data, build the deck.
set -e
python pipeline/00_download.py
python pipeline/01_ingest.py
python pipeline/02_features.py
python pipeline/03_model.py
python pipeline/04_export.py
python scripts/make_deck.py

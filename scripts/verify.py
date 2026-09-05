#!/usr/bin/env python3
"""Controles de coherence sur l'API generee (execute en CI apres build.py)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

API = Path(__file__).resolve().parent.parent / "docs" / "v1"


def load(name: str):
    return json.loads((API / name).read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    meta = load("meta.json")
    meds = load("medications.json")
    compact = load("medications.min.json")

    if len(meds) != meta["counts"]["medications"]:
        errors.append("meta.counts.medications ne correspond pas a medications.json")
    if not meds:
        errors.append("medications.json est vide")
    if len(compact) != len(meds):
        errors.append("l'index compact et la collection complete n'ont pas la meme taille")

    ids = [m["id"] for m in meds]
    if len(set(ids)) != len(ids):
        errors.append("identifiants dupliques dans medications.json")

    for m in meds:
        if not m["dci"] or not m["brandName"]:
            errors.append(f"fiche incomplete: {m['id']}")
            break

    # Echantillon de ressources unitaires + coherence des regroupements.
    sample = meds[:: max(1, len(meds) // 50)]
    for m in sample:
        path = API / "medications" / f"{m['id']}.json"
        if not path.exists():
            errors.append(f"fiche unitaire manquante: {path.name}")
        elif json.loads(path.read_text(encoding="utf-8"))["registrationNumber"] != m["registrationNumber"]:
            errors.append(f"fiche unitaire desynchronisee: {path.name}")

    for folder, index_total in (("dci", meta["counts"]["dci"]), ("laboratories", meta["counts"]["laboratories"])):
        index = load(f"{folder}/index.json")
        if index["count"] != index_total:
            errors.append(f"{folder}/index.json: compteur incoherent")
        if sum(e["count"] for e in index["items"]) != len(meds):
            errors.append(f"{folder}: la somme des regroupements ne couvre pas toutes les fiches")

    ndjson_lines = sum(1 for _ in (API / "medications.ndjson").open(encoding="utf-8"))
    if ndjson_lines != len(meds):
        errors.append("medications.ndjson: nombre de lignes incoherent")

    with (API / "medications.csv").open(encoding="utf-8", newline="") as fh:
        csv_rows = sum(1 for _ in csv.reader(fh)) - 1
    if csv_rows != len(meds):
        errors.append("medications.csv: nombre de lignes incoherent")

    if errors:
        for e in errors:
            print(f"ECHEC: {e}", file=sys.stderr)
        return 1

    print(f"OK: {len(meds)} medicaments, edition {meta['edition']}, "
          f"{meta['counts']['dci']} DCI, {meta['counts']['laboratories']} laboratoires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Genere l'API statique JSON a partir du CSV de la Nomenclature Nationale
des Produits Pharmaceutiques a usage de la medecine humaine (Algerie).

Source: Ministere de l'Industrie Pharmaceutique - Direction de la
Pharmaco-economie, des Activites Pharmaceutiques et de la Regulation.

Usage:
    python scripts/build.py
    python scripts/build.py --source data/nomenclature-2026-06.csv --out docs
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TYPE_LABELS = {
    "GE": {"fr": "Generique", "en": "Generic"},
    "RE": {"fr": "Reference (princeps)", "en": "Reference (originator)"},
    "BIO": {"fr": "Produit biologique / biosimilaire", "en": "Biological / biosimilar"},
}

ORIGIN_LABELS = {
    "F": {"fr": "Fabrique localement", "en": "Locally manufactured"},
    "I": {"fr": "Importe", "en": "Imported"},
}

LIST_LABELS = {
    "LISTE I": "Liste I - substance veneneuse, prescription medicale obligatoire",
    "LISTE II": "Liste II - substance veneneuse, prescription medicale obligatoire",
    "STUPEFIANT": "Stupefiant - prescription sur carnet a souches",
    "PSYCHOTROPE": "Psychotrope - prescription reglementee",
}

CSV_FIELDS = [
    "id", "numero", "registrationNumber", "code", "dci", "brandName", "form", "dosage",
    "packaging", "list", "hospitalUse", "retailUse", "observation", "laboratory", "country",
    "registrationDateInitial", "registrationDateFinal", "type", "origin", "stabilityMonths",
]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def norm_key(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", strip_accents(text or "").upper()).strip()


SLUG_MAX_LEN = 80


def slugify(text: str, fallback: str = "n-a") -> str:
    """Slug ASCII deterministe, borne en longueur (contrainte des noms de fichiers)."""
    s = re.sub(r"[^a-z0-9]+", "-", strip_accents(text or "").lower()).strip("-")
    if len(s) > SLUG_MAX_LEN:
        digest = hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]
        s = s[:SLUG_MAX_LEN].rsplit("-", 1)[0].strip("-") + "-" + digest
    return s or fallback


def clean(value):
    if value is None:
        return None
    s = re.sub(r"\s+", " ", str(value).replace(" ", " ")).strip()
    return s or None


def parse_date(value):
    """dd/mm/yyyy -> yyyy-mm-dd (ISO 8601)."""
    v = clean(value)
    if not v:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_months(value):
    v = clean(value)
    if not v:
        return None
    m = re.search(r"(\d+)", v)
    if not m:
        return None
    n = int(m.group(1))
    if re.search(r"\bAN(S|NEE|NEES)?\b", strip_accents(v).upper()):
        n *= 12
    return n


def coded(code, labels):
    if not code:
        return None
    entry = labels.get(code, {})
    return {"code": code, "label": entry.get("fr", code), "labelEn": entry.get("en")}


def write_json(path: Path, payload, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_rows(source: Path):
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    lines = text.replace("\r\n", "\n").split("\n")

    edition = None
    for line in lines[:40]:
        m = re.search(r"\bAU\s+(\d{1,2}\s+[A-ZEA]+\s+\d{4})", strip_accents(line).upper())
        if m:
            edition = clean(m.group(1))
            break

    reader = list(csv.reader(lines, delimiter=";"))
    header_idx = next(
        i for i, row in enumerate(reader)
        if any("DENOMINATION COMMUNE INTERNATIONALE" in norm_key(c) for c in row)
    )
    header = [clean(c) or "" for c in reader[header_idx]]

    rows = []
    for row in reader[header_idx + 1:]:
        if not any((c or "").strip() for c in row):
            continue
        rows.append({
            header[i]: row[i]
            for i in range(min(len(header), len(row)))
            if header[i]
        })
    return rows, edition


def col(row: dict, *candidates: str):
    """Recupere une colonne par nom normalise (accents / ponctuation ignores)."""
    keys = {norm_key(k): v for k, v in row.items()}
    for cand in candidates:
        if cand in keys:
            return keys[cand]
    for cand in candidates:
        for k, v in keys.items():
            if k.startswith(cand):
                return v
    return None


def build_records(rows):
    records = []
    used_ids = Counter()

    for row in rows:
        values = list(row.values())
        numero = clean(values[0]) if values else None
        registration = clean(col(row, "N ENREGISTREMENT", "NENREGISTREMENT"))
        dci = clean(col(row, "DENOMINATION COMMUNE INTERNATIONALE"))
        brand = clean(col(row, "NOM DE MARQUE"))
        laboratory = clean(col(row, "LABORATOIRES DETENTEUR"))
        country = clean(col(row, "PAYS DU LABORATOIRE"))
        med_list = clean(col(row, "LISTE"))
        dosage = clean(col(row, "DOSAGE"))
        form = clean(col(row, "FORME"))

        base = slugify(registration or f"{dci}-{brand}-{dosage}")
        used_ids[base] += 1
        rec_id = base if used_ids[base] == 1 else f"{base}-{used_ids[base]}"

        record = {
            "id": rec_id,
            "numero": int(numero) if numero and numero.isdigit() else None,
            "registrationNumber": registration,
            "code": clean(col(row, "CODE")),
            "dci": dci,
            "dciSlug": slugify(dci or ""),
            "brandName": brand,
            "brandSlug": slugify(brand or ""),
            "form": form,
            "dosage": dosage,
            "packaging": clean(col(row, "CONDITIONNEMENT")),
            "list": med_list,
            "listLabel": LIST_LABELS.get(med_list or ""),
            "hospitalUse": clean(col(row, "P1")) == "HOP",
            "retailUse": clean(col(row, "P2")) == "OFF",
            "observation": clean(col(row, "OBS")),
            "laboratory": laboratory,
            "laboratorySlug": slugify(laboratory or ""),
            "country": country,
            "registrationDateInitial": parse_date(col(row, "DATE D ENREGISTREMENT INITIAL")),
            "registrationDateFinal": parse_date(col(row, "DATE D ENREGISTREMENT FINAL")),
            "type": coded(clean(col(row, "TYPE")), TYPE_LABELS),
            "origin": coded(clean(col(row, "STATUT")), ORIGIN_LABELS),
            "stabilityMonths": parse_months(col(row, "DUREE DE STABILITE")),
        }
        record["label"] = " ".join(x for x in [brand, dosage, form] if x)
        # Cle de recherche normalisee: uniquement exposee dans l'index compact.
        record["_searchKey"] = strip_accents(
            " ".join(x for x in [brand, dci, dosage, form, laboratory] if x)
        ).lower()
        records.append(record)

    records.sort(key=lambda r: ((r["dci"] or ""), (r["brandName"] or ""), (r["dosage"] or "")))
    return records


def public(record: dict) -> dict:
    """Vue publique d'une fiche (sans les champs techniques prefixes par _)."""
    return {k: v for k, v in record.items() if not k.startswith("_")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/nomenclature-2026-06.csv")
    parser.add_argument("--out", default="docs")
    parser.add_argument("--base-url", default=None,
                        help="URL publique de l'API (ex: https://user.github.io/dz-pharma-nomenclature)")
    args = parser.parse_args()

    source = (ROOT / args.source).resolve()
    api = (ROOT / args.out).resolve() / "v1"

    if not source.exists():
        print(f"Source introuvable: {source}", file=sys.stderr)
        return 1

    base_url = args.base_url
    if base_url is None:
        cfg = ROOT / "config.json"
        if cfg.exists():
            base_url = json.loads(cfg.read_text(encoding="utf-8")).get("baseUrl")
    base_url = (base_url or "").rstrip("/")

    rows, edition = read_rows(source)
    records = build_records(rows)
    print(f"{len(records)} medicaments lus depuis {source.name} (edition: {edition})")

    for sub in ("medications", "dci", "laboratories"):
        shutil.rmtree(api / sub, ignore_errors=True)
    api.mkdir(parents=True, exist_ok=True)

    # --- collection complete ------------------------------------------------
    write_json(api / "medications.json", [public(r) for r in records])

    # --- index compact (autocomplete / recherche cote client) ---------------
    compact = [{
        "i": r["id"],
        "b": r["brandName"],
        "d": r["dci"],
        "g": r["dosage"],
        "f": r["form"],
        "c": r["packaging"],
        "l": r["list"],
        "t": (r["type"] or {}).get("code"),
        "o": (r["origin"] or {}).get("code"),
        "s": r["_searchKey"],
    } for r in records]
    write_json(api / "medications.min.json", compact)

    # --- NDJSON (import batch / streaming) ----------------------------------
    with (api / "medications.ndjson").open("w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- CSV normalise UTF-8 ------------------------------------------------
    with (api / "medications.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=",", lineterminator="\n")
        writer.writerow(CSV_FIELDS)
        for r in records:
            writer.writerow([
                (r["type"] or {}).get("code") if f == "type"
                else (r["origin"] or {}).get("code") if f == "origin"
                else r.get(f)
                for f in CSV_FIELDS
            ])

    # --- ressources unitaires ------------------------------------------------
    for r in records:
        write_json(api / "medications" / f"{r['id']}.json", public(r))

    # --- regroupements -------------------------------------------------------
    def build_group(slug_field: str, label_field: str, folder: str, kind: str):
        groups = defaultdict(list)
        labels = {}
        for r in records:
            key = r[slug_field]
            if not key or key == "n-a":
                continue
            groups[key].append(r)
            labels[key] = r[label_field]
        index = []
        for key, items in sorted(groups.items(), key=lambda kv: labels[kv[0]]):
            write_json(api / folder / f"{key}.json", {
                "kind": kind,
                "key": key,
                "label": labels[key],
                "count": len(items),
                "medications": [public(x) for x in items],
            })
            entry = {"key": key, "label": labels[key], "count": len(items)}
            if base_url:
                entry["url"] = f"{base_url}/v1/{folder}/{key}.json"
            index.append(entry)
        write_json(api / folder / "index.json", {"kind": kind, "count": len(index), "items": index})
        return index

    dci_index = build_group("dciSlug", "dci", "dci", "dci")
    lab_index = build_group("laboratorySlug", "laboratory", "laboratories", "laboratory")

    # --- referentiels --------------------------------------------------------
    def facet(field: str):
        counter = Counter(r[field] for r in records if r.get(field))
        return [{"label": k, "count": v} for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]

    forms, countries, lists = facet("form"), facet("country"), facet("list")
    write_json(api / "forms.json", {"count": len(forms), "items": forms}, pretty=True)
    write_json(api / "countries.json", {"count": len(countries), "items": countries}, pretty=True)
    write_json(api / "lists.json", {
        "count": len(lists),
        "items": [dict(x, description=LIST_LABELS.get(x["label"])) for x in lists],
    }, pretty=True)
    write_json(api / "types.json", {
        "types": [{"code": c, "label": v["fr"], "labelEn": v["en"],
                   "count": sum(1 for r in records if (r["type"] or {}).get("code") == c)}
                  for c, v in TYPE_LABELS.items()],
        "origins": [{"code": c, "label": v["fr"], "labelEn": v["en"],
                     "count": sum(1 for r in records if (r["origin"] or {}).get("code") == c)}
                    for c, v in ORIGIN_LABELS.items()],
    }, pretty=True)

    # --- metadonnees ---------------------------------------------------------
    meta = {
        "name": "Nomenclature Nationale des Produits Pharmaceutiques - Algerie",
        "apiVersion": "v1",
        "edition": edition,
        "sourceFile": source.name,
        "sourceChecksumSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "publisher": ("Ministere de l'Industrie Pharmaceutique - Direction de la Pharmaco-economie, "
                      "des Activites Pharmaceutiques et de la Regulation"),
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "license": "Donnees publiques officielles redistribuees a titre de reference - voir DISCLAIMER.md",
        "counts": {
            "medications": len(records),
            "dci": len(dci_index),
            "laboratories": len(lab_index),
            "forms": len(forms),
            "countries": len(countries),
        },
        "endpoints": {
            "meta": "/v1/meta.json",
            "all": "/v1/medications.json",
            "compactIndex": "/v1/medications.min.json",
            "ndjson": "/v1/medications.ndjson",
            "csv": "/v1/medications.csv",
            "byId": "/v1/medications/{id}.json",
            "dciIndex": "/v1/dci/index.json",
            "byDci": "/v1/dci/{slug}.json",
            "laboratoryIndex": "/v1/laboratories/index.json",
            "byLaboratory": "/v1/laboratories/{slug}.json",
            "forms": "/v1/forms.json",
            "countries": "/v1/countries.json",
            "lists": "/v1/lists.json",
            "types": "/v1/types.json",
        },
    }
    if base_url:
        meta["baseUrl"] = base_url
    write_json(api / "meta.json", meta, pretty=True)

    total = sum(1 for p in api.rglob("*") if p.is_file())
    print(f"OK -> {api} ({total} fichiers generes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

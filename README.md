# 🇩🇿 API Nomenclature Nationale des Médicaments — Algérie

API **JSON publique, gratuite et sans clé** de la *Nomenclature Nationale des Produits
Pharmaceutiques à usage de la médecine humaine* publiée par le Ministère de l'Industrie
Pharmaceutique (Direction de la Pharmaco-économie, des Activités Pharmaceutiques et de la
Régulation).

## 📅 Version juin 2026

Données issues de la nomenclature **arrêtée au 30 juin 2026**, dernière édition publiée par le
Ministère à ce jour. Elle contient **5 381 médicaments · 1 375 DCI · 518 laboratoires**.

La version publiée est toujours lisible par programme dans `/v1/meta.json` :

```json
{
  "edition": "juin 2026",
  "editionDate": "2026-06-30",
  "editionCode": "2026-06",
  "editionRaw": "30 JUIN 2026",
  "editionStatement": "Version juin 2026, données arrêtées au 30 juin 2026."
}
```

> 📍 **Base URL** : `https://allaouayoucef.github.io/dz-pharma-nomenclature`
> 🌐 **Documentation & recherche en ligne** : https://allaouayoucef.github.io/dz-pharma-nomenclature/

Il ne s'agit pas d'un serveur applicatif mais d'une **API statique** : des fichiers JSON
pré-générés servis par le CDN de GitHub Pages. Conséquences pratiques : aucune authentification,
aucun quota, aucun coût d'hébergement, CORS ouvert, cache HTTP (`ETag` / `Last-Modified`) et une
disponibilité alignée sur celle de GitHub.

---

## Points d'entrée

| Ressource | Chemin | Détail |
|---|---|---|
| Métadonnées | `/v1/meta.json` | Version publiée, date d'arrêt, empreinte de la source, compteurs, endpoints |
| Tous les médicaments | `/v1/medications.json` | Tableau complet (~5 Mo) |
| Index compact | `/v1/medications.min.json` | Champs abrégés + clé de recherche normalisée (~1,4 Mo) |
| NDJSON | `/v1/medications.ndjson` | Une fiche JSON par ligne (import en base) |
| CSV normalisé | `/v1/medications.csv` | UTF-8, séparateur virgule, dates ISO |
| Fiche unitaire | `/v1/medications/{id}.json` | Ex. `/v1/medications/352-01-a-003-06-22.json` |
| Index des DCI | `/v1/dci/index.json` | 1 375 dénominations communes internationales |
| Spécialités d'une DCI | `/v1/dci/{slug}.json` | Ex. `/v1/dci/paracetamol.json` |
| Index des laboratoires | `/v1/laboratories/index.json` | 518 détenteurs d'enregistrement |
| Produits d'un laboratoire | `/v1/laboratories/{slug}.json` | Ex. `/v1/laboratories/groupe-saidal.json` |
| Formes galéniques | `/v1/forms.json` | 671 formes avec effectifs |
| Pays | `/v1/countries.json` | 49 pays de laboratoires |
| Listes de substances | `/v1/lists.json` | Liste I, Liste II, Stupéfiant… |
| Types et origines | `/v1/types.json` | GE / RE / BIO et F / I |

## Schéma d'une fiche

```json
{
  "id": "352-01-a-003-06-22",
  "numero": 1,
  "registrationNumber": "352/01 A 003/06/22",
  "code": "01 A 003",
  "dci": "CETIRIZINE DICHLORHYDRATE",
  "dciSlug": "cetirizine-dichlorhydrate",
  "brandName": "ARTIZ",
  "brandSlug": "artiz",
  "form": "COMPRIME PELLICULE SECABLE",
  "dosage": "10MG",
  "packaging": "B/10",
  "list": "LISTE II",
  "listLabel": "Liste II - substance veneneuse, prescription medicale obligatoire",
  "hospitalUse": true,
  "retailUse": true,
  "observation": null,
  "laboratory": "EL KENDI INDUSTRIE DU MEDICAMENT",
  "laboratorySlug": "el-kendi-industrie-du-medicament",
  "country": "ALGERIE",
  "registrationDateInitial": "2006-07-31",
  "registrationDateFinal": "2025-08-10",
  "type":   { "code": "GE", "label": "Generique", "labelEn": "Generic" },
  "origin": { "code": "F",  "label": "Fabrique localement", "labelEn": "Locally manufactured" },
  "stabilityMonths": 60,
  "label": "ARTIZ 10MG COMPRIME PELLICULE SECABLE"
}
```

| Champ | Origine (colonne CSV) | Notes |
|---|---|---|
| `id` | `N° ENREGISTREMENT` | Numéro d'enregistrement normalisé en slug ; suffixe `-2`, `-3`… si un même numéro couvre plusieurs présentations |
| `numero` | `N°` | Rang dans l'édition — **change à chaque édition**, ne pas utiliser comme clé |
| `code` | `CODE` | Code de classification nationale (ex. `01 A 003`) |
| `hospitalUse` | `P1 = HOP` | Circuit hospitalier |
| `retailUse` | `P2 = OFF` | Circuit officine |
| `type` | `TYPE` | `GE` générique · `RE` référence (princeps) · `BIO` biologique/biosimilaire |
| `origin` | `STATUT` | `F` fabriqué localement · `I` importé |
| `stabilityMonths` | `DUREE DE STABILITE` | Converti en mois |
| dates | `DATE D'ENREGISTREMENT …` | Converties en ISO 8601 (`yyyy-mm-dd`) |

L'index compact `medications.min.json` utilise des clés abrégées pour rester léger :
`i` id · `b` marque · `d` DCI · `g` dosage · `f` forme · `c` conditionnement · `l` liste ·
`t` type · `o` origine · `s` clé de recherche (minuscules, sans accents).

---

## Utilisation

### curl

```bash
curl -s https://allaouayoucef.github.io/dz-pharma-nomenclature/v1/meta.json | jq .counts
curl -s https://allaouayoucef.github.io/dz-pharma-nomenclature/v1/dci/paracetamol.json | jq '.medications[].brandName'
```

### JavaScript / TypeScript

```js
const BASE = 'https://allaouayoucef.github.io/dz-pharma-nomenclature/v1';

// Autocomplétion : charger l'index compact une seule fois
const index = await fetch(`${BASE}/medications.min.json`).then(r => r.json());

const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
function search(q, limit = 20) {
  const terms = norm(q).split(/\s+/).filter(Boolean);
  return index.filter(m => terms.every(t => m.s.includes(t))).slice(0, limit);
}

// Fiche complète à la sélection
const fiche = await fetch(`${BASE}/medications/${search('doliprane')[0].i}.json`).then(r => r.json());
```

### C# / .NET

```csharp
public sealed record CodedValue(string Code, string Label, string? LabelEn);

public sealed record Medication(
    string Id,
    int? Numero,
    string RegistrationNumber,
    string Code,
    string Dci,
    string DciSlug,
    string BrandName,
    string BrandSlug,
    string Form,
    string Dosage,
    string Packaging,
    string? List,
    string? ListLabel,
    bool HospitalUse,
    bool RetailUse,
    string? Observation,
    string Laboratory,
    string LaboratorySlug,
    string Country,
    DateOnly? RegistrationDateInitial,
    DateOnly? RegistrationDateFinal,
    CodedValue? Type,
    CodedValue? Origin,
    int? StabilityMonths,
    string Label);

public sealed class NomenclatureClient(HttpClient http)
{
    private static readonly JsonSerializerOptions Json =
        new(JsonSerializerDefaults.Web);   // camelCase, insensible à la casse

    public Task<List<Medication>?> GetAllAsync(CancellationToken ct = default) =>
        http.GetFromJsonAsync<List<Medication>>("v1/medications.json", Json, ct);

    public Task<Medication?> GetByIdAsync(string id, CancellationToken ct = default) =>
        http.GetFromJsonAsync<Medication>($"v1/medications/{id}.json", Json, ct);
}
```

Enregistrement du client :

```csharp
builder.Services.AddHttpClient<NomenclatureClient>(c =>
    c.BaseAddress = new Uri("https://allaouayoucef.github.io/dz-pharma-nomenclature/"));
```

**Recommandation d'intégration** : ne pas appeler l'API à chaque prescription. Synchroniser
`v1/medications.json` dans une table locale (job quotidien ou hebdomadaire), et n'utiliser le
réseau que pour détecter un changement d'édition. `v1/meta.json` expose
`editionCode` (`2026-06`), `sourceChecksumSha256` et `generatedAt` : si ces valeurs n'ont pas bougé,
aucune resynchronisation n'est nécessaire. Stocker `editionCode` avec les données importées permet
d'afficher la version de la nomenclature en vigueur dans l'application. GitHub Pages gère également `ETag` / `If-None-Match` (réponse `304`).

### Import en base (SQL Server / PostgreSQL)

```bash
# CSV prêt à charger (UTF-8, dates ISO)
curl -O https://allaouayoucef.github.io/dz-pharma-nomenclature/v1/medications.csv

# ou une ligne JSON par enregistrement
curl -s https://allaouayoucef.github.io/dz-pharma-nomenclature/v1/medications.ndjson | head -1
```

---

## Mettre à jour la nomenclature

La nomenclature est rééditée périodiquement par le Ministère (généralement en juin et en décembre).
La version, sa date d'arrêt et son code sont déduits automatiquement de l'en-tête du CSV officiel —
aucune saisie manuelle. Pour publier une nouvelle édition :

1. Déposer le nouveau CSV dans `data/` (ex. `data/nomenclature-2026-12.csv`).
2. Régénérer l'API :

```bash
python scripts/build.py --source data/nomenclature-2026-12.csv
```

3. Commiter et pousser sur `main` : GitHub Actions revalide la génération et publie GitHub Pages.

Le script accepte un CSV encodé en UTF-8 ou CP1252, détecte automatiquement la ligne d'en-tête et
l'édition, et fait abstraction des lignes de titre du document officiel.

## Structure du dépôt

```
data/                     CSV source (converti en UTF-8)
scripts/build.py          Générateur de l'API statique
docs/                     Racine publiée par GitHub Pages
  index.html              Documentation + recherche en direct
  v1/…                    Fichiers JSON de l'API
.github/workflows/        Build + déploiement Pages
```

## Avertissement

Données publiques officielles republiées à titre de **référence documentaire**. L'inscription à la
nomenclature n'implique ni commercialisation effective, ni disponibilité en officine. Ce jeu de
données ne contient ni posologie, ni contre-indication, ni interaction médicamenteuse, et ne
remplace pas le Résumé des Caractéristiques du Produit. **Il ne constitue pas un avis médical.**
Voir [DISCLAIMER.md](DISCLAIMER.md).

## Licence

- **Code** (scripts, page de documentation) : [MIT](LICENSE).
- **Données** : information publique émanant du Ministère de l'Industrie Pharmaceutique
  (République Algérienne Démocratique et Populaire), redistribuée sans modification de fond.
  La transformation appliquée est purement technique (encodage, normalisation des dates, mise en
  forme JSON).

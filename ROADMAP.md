# Astra — Roadmap Stratégique v0.5 → v1.0

> Document de travail — Avril 2026

---

## Vue d'ensemble

| Axe | Thème | Versions | Effort |
|-----|-------|----------|--------|
| **1** | Ingestion Multi-Format (PDF, upload manuel) | v0.5 | ~3 sem |
| **2** | Gestion des Révisions (versioning nœud, diff, alertes) | v0.6 – v0.7 | ~6 sem |
| **3** | Guidances & Documents Connexes (AMC 20, SC, TGL, Certif Memo, eSF) | v0.8 – v0.9 | ~5 sem |
| — | Stabilisation & Production | v1.0 | ~2 sem |

**Priorité recommandée :** Axe 2 en premier (colonne vertébrale), Axe 1 upload manuel en parallèle rapide, Axe 3 en dernier.

---

## Axe 1 — Ingestion Multi-Format

### Contexte

Seuls les Easy Access Rules EASA au format XML sont ingérés. Les IR publiées au Journal Officiel EU, les CS standalone, les AMC 20, TGL, Certif Memo et SC n'ont pas de XML structuré — ils existent uniquement en PDF.

### Architecture Pipeline v2

```
Source Type        Parser               Normalizer
─────────────────  ───────────────────  ─────────────────────
EASA XML (EAR)  →  easa_xml_parser   →  nodes + edges (existant)
EU OJ PDF       →  pdf_structured    →  nodes IR
EASA PDF CS     →  pdf_cs_parser     →  nodes CS + AMC/GM intégrés
AMC 20 / TGL    →  pdf_generic       →  nodes AMC / GM
Upload Manuel   →  admin_upload      →  nodes (tout type, validation humaine)
```

### Composants à créer

#### Backend

- **`pdf_extractor.py`** — PyMuPDF + heuristiques de structure (titres, numérotation hiérarchique) → `ParsedDocument` normalisé
- **`pdf_cs_parser.py`** — spécialisé CS : détection `CS-XX.YYY`, AMC/GM intégrés dans le même PDF
- **`pdf_generic_parser.py`** — parser générique pour AMC 20, TGL, Certif Memo
- **`POST /api/admin/upload`** — endpoint upload PDF → parsing → preview → validation → insertion

#### Admin Console UI

- Nouveau tab **Upload** dans l'Admin Console
- Preview du parsing avant validation (liste des nœuds détectés)
- Validation humaine obligatoire avant insertion en DB

#### Catalog

Nouveaux champs sur `CatalogEntry` :

| Champ | Type | Description |
|-------|------|-------------|
| `format` | `xml \| pdf \| manual` | Format source |
| `source_type` | `ear \| oj \| standalone \| tgl \| memo \| sc` | Type de source |
| `harvest_url` | `TEXT \| null` | URL de téléchargement automatique |

### Effort : ~3 semaines

---

## Axe 2 — Gestion des Révisions

### Vision

Un **"Git pour la réglementation"** : chaque nœud réglementaire a un historique complet. On peut voir ce qui a changé entre deux versions, s'abonner à des alertes, et remonter dans le temps nœud par nœud.

### Modèle de données

```sql
-- Historique des versions par nœud
CREATE TABLE regulatory_node_versions (
    version_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         TEXT NOT NULL REFERENCES regulatory_nodes(node_id),
    version_label   TEXT NOT NULL,          -- ex: "Amendment 27"
    content_text    TEXT,
    content_html    TEXT,
    content_hash    TEXT NOT NULL,          -- MD5
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    change_type     TEXT NOT NULL,          -- added | modified | deleted | unchanged
    diff_prev       JSONB                   -- diff mot-à-mot vs version précédente
);

-- Snapshot de version par document
CREATE TABLE document_versions (
    doc_version_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_title    TEXT NOT NULL,
    version_label   TEXT NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    nodes_added     INT DEFAULT 0,
    nodes_modified  INT DEFAULT 0,
    nodes_deleted   INT DEFAULT 0,
    nodes_unchanged INT DEFAULT 0
);

-- Subscriptions alertes
CREATE TABLE alert_subscriptions (
    sub_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type TEXT NOT NULL,   -- 'document' | 'node'
    target_id   TEXT NOT NULL,   -- source_title ou node_id
    frequency   TEXT NOT NULL,   -- 'immediate' | 'weekly'
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

### Flux de détection automatique

```
HARVEST run (nouveau document ou refresh)
    │
    ├─→ Pour chaque nœud parsé :
    │       hash(content) == hash(version actuelle) ?
    │       ├── OUI  → change_type = 'unchanged'  (pas d'insert)
    │       └── NON  → INSERT regulatory_node_versions
    │                   compute diff_prev (difflib word-level)
    │                   change_type = 'modified'
    │
    ├─→ Nœuds présents en DB mais absents du parse :
    │       change_type = 'deleted'  (soft delete, conservé)
    │
    └─→ Nouveaux nœuds :
            change_type = 'added'
```

### Résolution du bug `amended_by`

Le champ `amended_by` en DB stocke actuellement la même valeur que `version_label` (sans valeur sémantique). Avec ce système :

- `document_versions` contiendra l'historique réel
- Un job harvest comparera la version en ligne EASA avec la dernière version indexée
- Le warning "version obsolète" sera basé sur une comparaison réelle

### UI — Node History (style GitHub)

```
┌──────────────────────────────────────────────────────────────┐
│  21.A.91  Classification of changes          [⏱ History ▾]  │
├──────────────────────────────────────────────────────────────┤
│  ● Amendment 27   (current)    2024-03-15                    │
│  ○ Amendment 26               2023-01-10        [View diff]  │
│  ○ Amendment 25               2022-06-01        [View diff]  │
└──────────────────────────────────────────────────────────────┘

Diff view (Amendment 26 → 27) :
  [-] "the applicant shall submit"
  [+] "the applicant shall provide evidence and submit"
       ───────────────────────────
```

- Bouton **History** dans le header de l'`ArticlePanel`
- Panel latéral ou modal avec liste des versions + dates
- Diff word-level coloré (rouge suppression, vert ajout)
- Navigation entre versions sans quitter l'article

### Module WATCH — Alertes

- Page dédiée dans la topbar (remplacement du tab Map ou nouvel onglet)
- Subscription par document ou par nœud individuel
- Digest hebdomadaire (email ou in-app)
- Badge notification dans la topbar si changements non lus

### Effort : ~6 semaines (4 sem versioning + 2 sem WATCH UI)

---

## Axe 3 — Guidances & Documents Connexes

### Contexte

Pour les aéronefs de transport civil (Large Aircraft), la conformité CS-25 s'appuie sur un écosystème de documents connexes que l'outil doit couvrir pour être réellement utile à un expert TC.

### Taxonomie étendue

#### Nouveaux `node_type`

| Type | Description | Exemple |
|------|-------------|---------|
| `AMC20` | AMC 20 standalone — cross-domain | AMC 20-29 (EWIS) |
| `SC` | Special Condition | SC-ASTC-01 |
| `TGL` | Temporary Guidance Leaflet | TGL No. 44 |
| `CERTIF_MEMO` | Certification Memorandum | CM-AS-006 |
| `ESF` | Equivalent Safety Finding | eSF-XXXX |
| `ISSUE_PAPER` | FAA Issue Paper (harmonisation) | IP-25-XXX |

#### Nouveaux types de relations

| Relation | Sémantique |
|----------|------------|
| `ISSUED_UNDER` | SC émis sous 21.A.18 / 21.A.101 |
| `HARMONIZED_WITH` | CS-25 article ↔ FAA AC ou ICAO SARPs |
| `SUPERSEDED_BY` | TGL remplacé par amendement CS |
| `APPLIED_TO` | SC appliqué à un TC spécifique |
| `CLARIFIES` | Certif Memo clarifie un CS ou AMC |

### Sources

| Document | Source | Format |
|----------|--------|--------|
| AMC 20-xx | EASA website (liste PDF) | PDF |
| TGL | EASA website | PDF |
| Certification Memoranda | EASA website | PDF |
| Special Conditions | EASA Official Journal | PDF |
| eSF | EASA website | PDF |
| FAA Issue Papers | FAA DRS | PDF |

### Catalog — nouvelles sections

Le `DocPicker` dans la sidebar affichera deux nouvelles sections :

```
■ INITIAL AIRWORTHINESS
    Part 21 · CS-25 · CS-23 · ...  (existant)

■ GUIDANCE MATERIAL                           ← nouveau
    AMC 20       Cross-domain AMC         234
    TGL          Temporary Guidance         45

■ SPECIAL CONDITIONS & FINDINGS               ← nouveau
    SC           Special Conditions          12
    Certif Memo  Certification Memoranda      8
    eSF          Equivalent Safety Findings   3
```

### UI — intégration Consult

- **DocPicker** : nouvelles sections `Guidance Material` et `Special Conditions`
- **Badge types** : `AMC20`, `SC`, `TGL`, `CERTIF_MEMO`, `ESF` avec couleurs distinctes
- **NeighborsPanel** : nouvelles relations `ISSUED_UNDER`, `HARMONIZED_WITH`, `APPLIED_TO`
- **ArticlePanel** : contextual sidebar "Related Special Conditions" sur les articles CS-25

### Effort : ~5 semaines

---

## Roadmap par version

```
v0.5  ──────  Axe 1 : PDF parsing + Admin Upload manuel
              ├─ pdf_extractor.py (PyMuPDF)
              ├─ pdf_cs_parser.py
              ├─ POST /api/admin/upload + preview UI
              └─ Catalog : champs format / source_type

v0.6  ──────  Axe 2 : Versioning DB + détection automatique
              ├─ regulatory_node_versions table
              ├─ document_versions table
              ├─ Intégration dans le pipeline HARVEST
              └─ API : GET /api/nodes/{id}/history

v0.7  ──────  Axe 2 : Node History UI + WATCH alerts
              ├─ ArticlePanel : bouton History + diff view
              ├─ alert_subscriptions table
              ├─ WATCH tab dans topbar
              └─ Warning "version obsolète" basé sur comparaison réelle

v0.8  ──────  Axe 3 : AMC 20 / TGL / Certif Memo
              ├─ Catalog étendu (AMC20, TGL, CERTIF_MEMO)
              ├─ pdf_generic_parser.py
              └─ Harvest automatique EASA website

v0.9  ──────  Axe 3 : SC / eSF / relations cross-documents
              ├─ SC / ESF catalog + parsing
              ├─ Nouveaux types de relations
              └─ UI : DocPicker sections + NeighborsPanel étendu

v1.0  ──────  Stabilisation & Production
              ├─ Tests de régression complets
              ├─ Performance (index DB, pagination)
              ├─ Auth / RBAC
              └─ Déploiement production
```

---

## Décisions à prendre avant v0.5

| Décision | Options | Impact |
|----------|---------|--------|
| Parser PDF | PyMuPDF seul vs PyMuPDF + LLM extraction | Qualité vs coût |
| Validation upload | Manuelle systématique vs auto si confiance > seuil | Fiabilité |
| Stockage PDF originaux | File system local vs S3/Blob | Scalabilité |
| Format diff | difflib word-level vs LLM-generated summary | UX |
| Sources SC | Scraping OJ EU vs saisie manuelle | Effort |

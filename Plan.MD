# [cite_start]CERTIFEXPERT PLATFORM [cite: 1]
[cite_start]**Dossier de Conception Détaillé** [cite: 2]
[cite_start]*Outil d'Expertise en Type Certification* [cite: 3]
[cite_start]*Version 2.0 — Avril 2026* [cite: 4]
[cite_start]*Document de travail — Conception système (Inclut les réponses aux questions d'Architecture Review)* [cite: 5]

---

## [cite_start]Table des Matières [cite: 6]
* [cite_start]1. Résumé Exécutif [cite: 7]
* [cite_start]2. Architecture Globale [cite: 8]
* [cite_start]3. Module HARVEST — Collecte Réglementaire [cite: 9]
* [cite_start]4. Cartographie Part 21 — TC & Changes [cite: 10]
* [cite_start]5. Module EXPERT — Fonctionnalités Utilisateur [cite: 11]
* [cite_start]6. Knowledge Graph — Modèle de Données [cite: 12]
* [cite_start]7. Schéma de Base de Données [cite: 13]
* [cite_start]8. Spécification API [cite: 14]
* [cite_start]9. Référentiel de Compétences Expert TC [cite: 15]
* [cite_start]10. Architecture Technique et Sécurité [cite: 16]
* [cite_start]11. Logique Métier et Conformité [cite: 17]
* [cite_start]12. Stratégie et Déploiement [cite: 18]
* [cite_start]13. Prochaines Étapes [cite: 19]
* [cite_start]Annexe A — Glossaire [cite: 20]
* [cite_start]Annexe B — Références Documentaires [cite: 21]
* [cite_start]Annexe C — Trame d'Évaluation Architecture Review [cite: 22]

---

## [cite_start]1. Résumé Exécutif [cite: 23]

### [cite_start]1.1 Contexte et Objectif [cite: 24]
[cite_start]Ce document présente la conception détaillée de CertifExpert, une plateforme destinée à l'acquisition et au maintien de l'expertise en Type Certification (TC) et Changes to Type Certificate selon la réglementation EASA Part 21. [cite: 25] [cite_start]L'outil vise à transformer la manière dont les professionnels de la certification aéronautique acquièrent, maintiennent et appliquent leur expertise réglementaire, en combinant une base de connaissances structurée avec des outils pédagogiques interactifs. [cite: 26]

### [cite_start]1.2 Périmètre Fonctionnel [cite: 27]
* [cite_start]**Module HARVEST :** Collecte automatisée et structuration des sources réglementaires [cite: 28]
* [cite_start]**Module EXPERT :** Outils de formation, pratique et référence pour l'utilisateur [cite: 29]
* [cite_start]**Knowledge Layer :** Moteur de graphe et RAG pour l'intelligence réglementaire [cite: 30]
* [cite_start]**Data Layer :** Stockage structuré, vectoriel et fichiers [cite: 31]

### [cite_start]1.3 Valeur Ajoutée [cite: 32]
* [cite_start]Cartographie complète des exigences Part 21 (Subparts B et D) avec leurs interdépendances [cite: 33]
* [cite_start]Veille réglementaire automatisée avec détection des changements [cite: 34]
* [cite_start]Parcours de formation structurés avec cas pratiques réalistes [cite: 35]
* [cite_start]Assistant expert contextuel basé sur RAG avec garde-fous anti-hallucination [cite: 36]

### [cite_start]1.4 Évolutions v2.0 [cite: 37]
[cite_start]Cette version intègre les clarifications issues de la revue d'architecture : [cite: 38]
* [cite_start]Architecture sécurité détaillée (authentification, RBAC, multi-tenant) [cite: 39]
* [cite_start]Stratégie anti-hallucination pour les décisions critiques [cite: 40]
* [cite_start]Framework de responsabilité juridique [cite: 41]
* [cite_start]KPIs quantitatifs pour la Phase 1 [cite: 42]
* [cite_start]Gestion des standards paywalled [cite: 43]
* [cite_start]Trame d'évaluation pour revue d'architecture [cite: 44]

---

## [cite_start]2. Architecture Globale [cite: 45]

### [cite_start]2.1 Vue d'Ensemble [cite: 46]
[cite_start]L'architecture de CertifExpert repose sur une séparation claire entre la collecte de données (HARVEST), le stockage (DATA LAYER), le traitement intelligent (KNOWLEDGE LAYER) et l'interface utilisateur (EXPERT MODULE). [cite: 47]

| Couche | Description |
| :--- | :--- |
| **HARVEST** | [cite_start]Scrapers, parsers, schedulers pour la collecte automatisée des sources EASA, FAA, ICAO et standards industriels [cite: 48] |
| **DATA LAYER** | [cite_start]PostgreSQL (données structurées), ChromaDB (embeddings vectoriels), File Storage (PDFs archivés) [cite: 48] |
| **KNOWLEDGE LAYER** | [cite_start]Graph Engine (traversée des relations), RAG Engine (recherche sémantique + LLM), Content Engine (pédagogie) [cite: 48] |
| **EXPERT MODULE** | [cite_start]Interface utilisateur : LEARN, PRACTICE, EXPLORE, WATCH, ASK, ASSESS [cite: 48] |

### [cite_start]2.2 Flux de Données [cite: 49]
[cite_start]Le flux principal s'organise en deux directions complémentaires : [cite: 50]
1. [cite_start]**HARVEST → DATA LAYER :** Alimentation continue de la base de connaissances par scraping et parsing des sources externes [cite: 51]
2. [cite_start]**EXPERT MODULE → KNOWLEDGE LAYER → DATA LAYER :** Consommation des données par les fonctionnalités utilisateur [cite: 52]

### [cite_start]2.3 Principe de Découplage [cite: 53]
* [cite_start]HARVEST écrit dans la base, EXPERT lit depuis la base [cite: 54]
* [cite_start]HARVEST peut fonctionner même si EXPERT est indisponible [cite: 55]
* [cite_start]Le contenu pédagogique référence les données réglementaires sans duplication [cite: 56]
* [cite_start]Les changements détectés par HARVEST déclenchent des notifications push vers EXPERT [cite: 57]

---

## [cite_start]3. Module HARVEST — Collecte Réglementaire [cite: 58]

### [cite_start]3.1 Objectif [cite: 59]
[cite_start]Le module HARVEST est responsable de la collecte automatisée, du parsing structuré et de la mise à jour continue de l'ensemble des sources réglementaires pertinentes pour la certification aéronautique. [cite: 60]

### [cite_start]3.2 Registre des Sources [cite: 61]

[cite_start]**3.2.1 Tier 1 — Autorités (Sources Primaires)** [cite: 62]

[cite_start]**Sources EASA** [cite: 63]
| Source | Format | Fréquence |
| :--- | :--- | :--- |
| Easy Access Rules (Part 21, CS-25, CS-ACNS) | HTML + PDF | [cite_start]Daily check, weekly refresh [cite: 64] |
| NPAs / Opinions / ED Decisions | RSS + PDF | [cite_start]Hourly RSS check [cite: 64] |
| Airworthiness Directives | REST API | [cite_start]Daily [cite: 64] |
| Type Certificate Data Sheets | PDF | [cite_start]Weekly [cite: 64] |

[cite_start]**Sources FAA** [cite: 65]
| Source | Format | Fréquence |
| :--- | :--- | :--- |
| 14 CFR Part 21, Part 25 | HTML / XML API (eCFR) | [cite_start]Weekly [cite: 66] |
| Advisory Circulars | PDF | [cite_start]Monthly [cite: 66] |
| FAA Orders (8110.4) | PDF | [cite_start]Monthly [cite: 66] |

[cite_start]**3.2.2 Tier 2 — Standards Industriels (Paywalled)** [cite: 67]
* [cite_start]EUROCAE : ED-12C, ED-79A, ED-80, ED-120, ED-202A [cite: 68]
* [cite_start]RTCA : DO-178C, DO-254, DO-326A, DO-280B, DO-160 [cite: 69]
* [cite_start]SAE : ARP4754A, ARP4761/A, ARP5150 [cite: 70]
> [cite_start]**Note :** Ces standards sont sous copyright et nécessitent une gestion spécifique (voir Section 11.2). [cite: 71]

[cite_start]**3.2.3 Tier 3 — Sources Complémentaires** [cite: 72]
* [cite_start]EASA Board of Appeal Decisions (jurisprudence certification) [cite: 73]
* [cite_start]EU Official Journal (Basic Regulation, Implementing Rules) [cite: 74]
* [cite_start]ICAO Annexes et Documents (Annex 8, Doc 9760, Doc 9880) [cite: 75]

### [cite_start]3.3 Pipeline de Traitement [cite: 76]
[cite_start]Le pipeline HARVEST se décompose en quatre étapes principales : [cite: 77]
1. [cite_start]**FETCH :** Récupération des contenus via HTTP, API REST ou flux RSS selon la source [cite: 78]
2. [cite_start]**PARSE :** Extraction structurée du contenu (PDF via PyMuPDF, HTML via BeautifulSoup) [cite: 79]
3. [cite_start]**TRANSFORM :** Chunking sémantique, extraction des références croisées, génération des embeddings [cite: 80]
4. [cite_start]**STORE :** Insertion dans PostgreSQL (structure), ChromaDB (vecteurs), archivage des PDFs [cite: 81]

### [cite_start]3.4 Détection des Changements [cite: 82]
[cite_start]L'algorithme de diffing compare chaque nouvelle version avec la version stockée : [cite: 83]
1. [cite_start]Alignement des nœuds par reference_code (ex: 21.A.91 v1 ↔ 21.A.91 v2) [cite: 84]
2. [cite_start]Comparaison des hash MD5 du contenu [cite: 85]
3. [cite_start]Classification : ADDED (nouveau), MODIFIED (changé), DELETED (supprimé) [cite: 86]
4. [cite_start]Génération d'un diff textuel mot à mot via difflib [cite: 87]
5. [cite_start]Notification aux utilisateurs abonnés [cite: 88]

---

## [cite_start]4. Cartographie Part 21 — TC & Changes [cite: 89]

### [cite_start]4.1 Vue d'Ensemble Part 21 Section A [cite: 90]
[cite_start]La Part 21 Section A couvre la certification des aéronefs et de leurs composants. [cite: 91] [cite_start]Les Subparts clés pour la Type Certification sont : [cite: 92]

| Subpart | Titre | Articles |
| :--- | :--- | :--- |
| Subpart B | Type Certificates | [cite_start]21.A.11 → 21.A.55 [cite: 93] |
| Subpart D | Changes to Type Certificates | [cite_start]21.A.90 → 21.A.109 [cite: 93] |
| Subpart E | Supplemental Type Certificates | [cite_start]21.A.111 → 21.A.118B [cite: 93] |
| Subpart G | Production Organisation Approval | [cite_start]21.A.131 → 21.A.165 [cite: 93] |
| Subpart J | Design Organisation Approval | [cite_start]21.A.231 → 21.A.265 [cite: 93] |

### [cite_start]4.2 Subpart B — Type Certificates (Détail) [cite: 94]
| Article | Titre | Contenu Principal |
| :--- | :--- | :--- |
| 21.A.15 | Application | [cite_start]Contenu de la demande : description, caractéristiques inhabituelles, programme certification [cite: 95] |
| 21.A.17 | TC Basis | [cite_start]Établissement de la base de certification : CS applicable, Special Conditions, Exemptions [cite: 95] |
| 21.A.18 | Special Conditions | [cite_start]Quand les CS ne couvrent pas une novel feature ou un usage non conventionnel [cite: 95] |
| 21.A.20 | Compliance | [cite_start]Démonstration de conformité par tests, analyses, inspections [cite: 95] |
| 21.A.21 | Issuance | [cite_start]Délivrance du TC incluant Type Design, TCDS, ICA [cite: 95] |
| 21.A.44 | Obligations | [cite_start]Responsabilités continues : continued airworthiness, ICA, coopération Authority [cite: 95] |

### [cite_start]4.3 Subpart D — Changes to Type Certificates [cite: 96]

[cite_start]**4.3.1 Classification des Changements (21.A.91)** [cite: 97]
| Classification | Définition |
| :--- | :--- |
| MINOR | [cite_start]Changement sans effet appréciable sur : masse & centrage, résistance structurale, fiabilité, caractéristiques opérationnelles, autres caractéristiques de navigabilité [cite: 98] |
| MAJOR | [cite_start]Tout changement qui n'est pas Minor (définition par exclusion) [cite: 98] |

[cite_start]**4.3.2 Critères de Classification (GM 21.A.91 Appendix A)** [cite: 99]
[cite_start]Le GM 21.A.91 Appendix A fournit des critères détaillés : [cite: 100]
* [cite_start]**Flight Test Required :** Le changement nécessite-t-il un essai en vol ? [cite: 101]
* [cite_start]**AFM Change :** Le changement affecte-t-il l'AFM (limitations, procédures, performances) ? [cite: 102]
* [cite_start]**Crew Interface :** Le changement affecte-t-il l'interface équipage ou la workload ? [cite: 103]
* [cite_start]**Safety Assessment :** Le changement modifie-t-il les Safety Objectives (FHA/SSA) ? [cite: 104]
* [cite_start]**Structural Substantiation :** Nouvelle analyse structurale significative requise ? [cite: 105]
* [cite_start]**Software/AEH :** Modification du DAL ou nouveau software DAL A/B/C ? [cite: 106]
* [cite_start]**Interoperability :** Impact sur une capacité opérationnelle approuvée (PBN, Datalink, RVSM) ? [cite: 107]

[cite_start]**4.3.3 Processus d'Approbation** [cite: 108]
| Type | Article | Approbation |
| :--- | :--- | :--- |
| Minor Change | 21.A.95 | [cite_start]DOA (self-approval) ou Authority si pas de DOA [cite: 109] |
| Major Change | 21.A.97 | [cite_start]Authority (EASA) obligatoire [cite: 109] |

[cite_start]**4.3.4 Changed Product Rule (21.A.101)** [cite: 110]
[cite_start]L'article 21.A.101 répond à la question : « Quand dois-je appliquer les nouveaux CS amendments lors d'un Major Change ? [cite: 111] [cite_start]» La règle s'applique si le changement est « SIGNIFICANT », défini par GM 21.A.101. [cite: 112]

### [cite_start]4.4 Distinction Major vs Significant [cite: 113]
| Concept | Question | Conséquence |
| :--- | :--- | :--- |
| MAJOR (21.A.91) | Qui approuve le changement ? | [cite_start]Authority approval required [cite: 114] |
| SIGNIFICANT (21.A.101) | Quels CS amendments appliquer ? | [cite_start]Latest CS amendment pour areas affected [cite: 114] |

> [cite_start]**Important :** Un changement peut être MAJOR mais pas SIGNIFICANT (et inversement). [cite: 115]

---

## [cite_start]5. Module EXPERT — Fonctionnalités Utilisateur [cite: 116]

### [cite_start]5.1 Vue d'Ensemble [cite: 117]
| Fonction | Nom | Description |
| :--- | :--- | :--- |
| 📚 LEARN | Parcours Structurés | [cite_start]Modules de formation progressifs couvrant Part 21, CS-25, interfaces [cite: 118] |
| 🎯 PRACTICE | Cas Pratiques | [cite_start]Scénarios réalistes de classification, compliance, décisions [cite: 118] |
| 🔍 EXPLORE | Navigation Réglementaire | [cite_start]Exploration interactive du graphe Part 21 avec liens contextuels [cite: 118] |
| 📡 WATCH | Veille Réglementaire | [cite_start]Alertes sur NPAs, changements de CS, nouvelles ED Decisions [cite: 118] |
| 💬 ASK | Assistant Expert | [cite_start]Chat contextuel RAG pour questions/réponses sourcées [cite: 118] |
| 🧪 ASSESS | Auto-évaluation | [cite_start]Tests de compétences et suivi de progression [cite: 118] |

### [cite_start]5.2 LEARN — Parcours de Formation [cite: 119]
* [cite_start]Type Certification Fundamentals (Fondation, ~8h) [cite: 120]
* [cite_start]Certification Basis Strategies (Avancé) [cite: 121]
* [cite_start]DOA Privileges & Limitations (Avancé) [cite: 122]
* [cite_start]Software & AEH Certification (Spécialiste) [cite: 123]
* [cite_start]System Safety in TC Context (Spécialiste) [cite: 124]
* [cite_start]EASA vs FAA Part 21 (Comparatif) [cite: 125]

### [cite_start]5.3 PRACTICE — Cas Pratiques [cite: 126]
* [cite_start]Classification de changements (Major/Minor) avec justification [cite: 127]
* [cite_start]Établissement de Certification Basis [cite: 128]
* [cite_start]Évaluation 21.A.101 (Significant Change) [cite: 129]
* [cite_start]Identification des CS impactés [cite: 130]
* [cite_start]Réponse à des questions Authority [cite: 131]

### [cite_start]5.4 EXPLORE — Navigation Réglementaire [cite: 132]
* [cite_start]Arborescence Part 21 avec tous les articles [cite: 133]
* [cite_start]Texte réglementaire intégral + AMC/GM associés [cite: 134]
* [cite_start]Explication en langage clair (plain language) [cite: 135]
* [cite_start]Vue graphe interactive des dépendances [cite: 136]

### [cite_start]5.5 WATCH — Veille Réglementaire [cite: 137]
* [cite_start]Détection automatique des nouvelles NPAs et Opinions [cite: 138]
* [cite_start]Analyse d'impact générée par IA [cite: 139]
* [cite_start]Visualisation des diffs pour les modifications [cite: 140]
* [cite_start]Alertes configurables par domaine [cite: 141]

### [cite_start]5.6 ASK — Assistant Expert [cite: 142]
* [cite_start]Recherche sémantique dans la base vectorielle (ChromaDB) [cite: 143]
* [cite_start]Génération de réponse par LLM avec contexte [cite: 144]
* [cite_start]Citation obligatoire des sources [cite: 145]
* [cite_start]Garde-fous anti-hallucination (voir Section 11.1) [cite: 146]

---

## [cite_start]6. Knowledge Graph — Modèle de Données [cite: 147]

### [cite_start]6.1 Structure des Nœuds [cite: 148]
| Attribut | Type | Description |
| :--- | :--- | :--- |
| node_id | TEXT (PK) | [cite_start]Identifiant unique (ex: part21:IR:21.A.91) [cite: 149] |
| node_type | ENUM | [cite_start]IR, AMC, GM, CS, STANDARD, SARP [cite: 149] |
| reference_code | TEXT | [cite_start]Code de référence (ex: 21.A.91) [cite: 149] |
| content_text | TEXT | [cite_start]Texte intégral du paragraphe [cite: 149] |
| content_hash | TEXT | [cite_start]Hash MD5 pour détection de changements [cite: 149] |
| hierarchy_path | TEXT | [cite_start]Chemin hiérarchique [cite: 149] |

### [cite_start]6.2 Types de Relations (Arêtes) [cite: 150]
| Type de Relation | Sémantique |
| :--- | :--- |
| IMPLEMENTS | [cite_start]Le CS transpose un SARP ICAO [cite: 151] |
| ACCEPTABLE_MEANS | [cite_start]L'AMC démontre conformité au CS/IR [cite: 151] |
| GUIDANCE_FOR | [cite_start]Le GM explique un CS/AMC/IR [cite: 151] |
| REFERENCES | [cite_start]Citation explicite d'un standard industriel [cite: 151] |
| REQUIRES | [cite_start]Dépendance vers un autre domaine [cite: 151] |
| EQUIVALENT_TO | [cite_start]Équivalence ED ↔ DO (EUROCAE/RTCA) [cite: 151] |
| SUPERSEDES | [cite_start]Remplacement (versioning) [cite: 151] |
| IF_MINOR / IF_MAJOR | [cite_start]Branchement conditionnel [cite: 151] |
| LEADS_TO | [cite_start]Flux processuel (étape suivante) [cite: 151] |

### [cite_start]6.3 Exemple de Traversée [cite: 152]
[cite_start]Requête : « Je veux modifier le calculateur FMS sur A350 » [cite: 153]
1. [cite_start]Entrée « FMS » + « modification » → Nœud 21.A.90 [cite: 154]
2. [cite_start]21.A.90 → 21.A.91 (Classification) → Check GM Appendix A [cite: 155]
3. [cite_start]Software change DAL A/B → Potentiellement MAJOR [cite: 156]
4. [cite_start]MAJOR → 21.A.97 → 21.A.101 (Significant?) [cite: 157]
5. [cite_start]→ 21.A.17 (TC Basis) → CS-25.1309, CS-25.1302 [cite: 158]
6. [cite_start]Output : Liste complète des exigences avec références [cite: 159]

---

## [cite_start]7. Schéma de Base de Données [cite: 160]

### [cite_start]7.1 Organisation en Domaines [cite: 161]
| Domaine | Tables Principales | Description |
| :--- | :--- | :--- |
| HARVEST | harvest_sources, harvest_documents, harvest_document_versions | [cite_start]Configuration et tracking des sources [cite: 162] |
| KNOWLEDGE | regulatory_nodes, regulatory_edges, regulatory_changes | [cite_start]Graphe réglementaire et historique [cite: 162] |
| EXPERT | learning_paths, learning_modules, practice_scenarios, user_progress | [cite_start]Contenu pédagogique et progression [cite: 162] |
| ALERTING | alert_subscriptions, notifications | [cite_start]Préférences et notifications [cite: 162] |

### [cite_start]7.2 Stockage Complémentaire [cite: 163]
* [cite_start]**ChromaDB :** Embeddings vectoriels pour recherche sémantique RAG [cite: 164]
* [cite_start]**File Storage :** PDFs originaux archivés [cite: 165]

---

## [cite_start]8. Spécification API [cite: 166]

### [cite_start]8.1 Endpoints Principaux [cite: 167]
| Module | Endpoint | Description |
| :--- | :--- | :--- |
| EXPLORE | GET /api/nodes/{node_id} | [cite_start]Récupérer un nœud avec ses relations [cite: 168] |
| EXPLORE | GET /api/nodes/search | [cite_start]Rechercher des nœuds [cite: 168] |
| EXPLORE | POST /api/graph/traverse | [cite_start]Traverser le graphe [cite: 168] |
| ASK | POST /api/ask | [cite_start]Poser une question à l'assistant [cite: 168] |
| WATCH | GET /api/changes | [cite_start]Récupérer les changements récents [cite: 168] |
| WATCH | GET /api/changes/{id}/diff | [cite_start]Détail d'un diff [cite: 168] |
| LEARN | GET /api/learn/paths | [cite_start]Liste des parcours [cite: 168] |
| LEARN | GET /api/learn/modules/{id}/content | [cite_start]Contenu d'un module [cite: 168] |
| PRACTICE | GET /api/practice/scenarios | [cite_start]Liste des scénarios [cite: 168] |
| PRACTICE | POST /api/practice/scenarios/{id}/submit | [cite_start]Soumettre les réponses [cite: 168] |
| HARVEST | GET /api/harvest/sources | [cite_start]Statut des sources (Admin) [cite: 168] |
| HARVEST | POST /api/harvest/sources/{id}/sync | [cite_start]Déclencher synchronisation [cite: 168] |

---

## [cite_start]9. Référentiel de Compétences Expert TC [cite: 169]

### [cite_start]9.1 Connaissance Réglementaire (Le « Quoi ») [cite: 170]
* [cite_start]Maîtrise de Part 21 Section A (Subparts B, D, E, J, M, P) [cite: 171]
* [cite_start]Compréhension des liens Part 21 ↔ CS-25 ↔ CS-E ↔ CS-ACNS [cite: 172]
* [cite_start]Connaissance des AMC/GM et leur valeur juridique [cite: 173]
* [cite_start]Awareness des différences EASA / FAA / TCCA / CAAC [cite: 174]

### [cite_start]9.2 Savoir-Faire Processuel (Le « Comment ») [cite: 175]
* [cite_start]Établir une Certification Basis (21.A.17 / 21.A.97 + 21.A.101) [cite: 176]
* [cite_start]Classifier un changement (Major/Minor) avec justification [cite: 177]
* [cite_start]Construire une Compliance Matrix et définir les MoC [cite: 178]
* [cite_start]Gérer les interfaces Authority (TCM, CRI, Findings) [cite: 179]

### [cite_start]9.3 Jugement & Expérience (Le « Pourquoi ») [cite: 180]
* [cite_start]Anticiper les points de friction avec l'Autorité [cite: 181]
* [cite_start]Reconnaître les patterns de problèmes [cite: 182]
* [cite_start]Adapter l'approche selon le contexte (TC vs STC vs DOA scope) [cite: 183]

### [cite_start]9.4 Veille & Adaptation (Le « Demain ») [cite: 184]
* [cite_start]Suivre les NPAs et anticiper les impacts [cite: 185]
* [cite_start]Comprendre les tendances (cybersecurity, AI, sustainability) [cite: 186]
* [cite_start]Contribuer aux consultations et façonner les règles [cite: 187]

---

## [cite_start]10. Architecture Technique et Sécurité [cite: 188]

### [cite_start]10.1 Technologie Base de Données Graphe [cite: 189]
[cite_start]Le choix actuel repose sur PostgreSQL avec extension Apache AGE plutôt qu'une base graphe native (Neo4j). [cite: 190] [cite_start]Cette décision est basée sur l'analyse suivante : [cite: 191]

| Option | Avantages | Inconvénients |
| :--- | :--- | :--- |
| PostgreSQL + AGE | Stack unifiée, requêtes SQL + Cypher, maturité, coût maîtrisé | [cite_start]Moins performant pour traversées profondes (>5 hops) [cite: 192] |
| Neo4j | Optimisé graphe, Cypher natif, visualisation intégrée | [cite_start]Stack additionnelle, coût licence Enterprise [cite: 192] |
| PostgreSQL seul | Simple, pas de dépendance | [cite_start]Requêtes récursives complexes [cite: 192] |

> [cite_start]**Recommandation :** Démarrer avec PostgreSQL + tables relationnelles pour le PoC, migrer vers AGE si les besoins de traversée le justifient en Phase 2. [cite: 193]

### [cite_start]10.2 Architecture Authentification et RBAC [cite: 194]

[cite_start]**10.2.1 Authentification** [cite: 195]
* [cite_start]OAuth 2.0 / OIDC via Keycloak ou Auth0 [cite: 196]
* [cite_start]SSO corporate (SAML 2.0 pour intégration entreprises) [cite: 197]
* [cite_start]MFA obligatoire pour rôles Admin [cite: 198]

[cite_start]**10.2.2 Rôles RBAC** [cite: 199]
| Rôle | Permissions |
| :--- | :--- |
| VIEWER | [cite_start]Lecture EXPLORE, ASK [cite: 200] |
| LEARNER | + [cite_start]LEARN, PRACTICE, ASSESS [cite: 200] |
| EXPERT | + [cite_start]WATCH (alertes personnalisées) [cite: 200] |
| ADMIN | + [cite_start]Gestion utilisateurs, HARVEST monitoring [cite: 200] |
| SUPERADMIN | + [cite_start]Configuration sources, accès multi-tenant [cite: 200] |

[cite_start]**10.2.3 Multi-Tenancy** [cite: 201]
* [cite_start]Modèle retenu : Schema-per-tenant (PostgreSQL) [cite: 202]
* [cite_start]Chaque organisation = schema dédié [cite: 203]
* [cite_start]Données réglementaires publiques = schema partagé [cite: 204]
* [cite_start]Progression/notes utilisateur = schema tenant [cite: 205]
* [cite_start]Row-Level Security (RLS) pour isolation stricte [cite: 206]
* [cite_start]tenant_id injecté via JWT claims → contexte requête [cite: 207]

### [cite_start]10.3 Choix du LLM et Confidentialité [cite: 208]

| Modèle | Déploiement | Confidentialité | Performance |
| :--- | :--- | :--- | :--- |
| Claude API (Anthropic) | Cloud | Bonne (ZDR disponible) | [cite_start]Excellente [cite: 209] |
| GPT-4 API (OpenAI) | Cloud | Moyenne | [cite_start]Excellente [cite: 209] |
| Mistral Large | Cloud EU / On-prem | Très bonne | [cite_start]Très bonne [cite: 209] |
| Llama 3 70B | On-premise | Totale | [cite_start]Bonne [cite: 209] |

[cite_start]**10.3.1 Recommandations selon contexte** [cite: 210]
* [cite_start]Usage individuel/PME : Claude API avec Zero Data Retention (ZDR) [cite: 211]
* [cite_start]Corporate (type Airbus) : Mistral on-premise ou Llama 3 sur infra dédiée [cite: 212]
* [cite_start]Hybride : RAG local + LLM API pour génération (données anonymisées) [cite: 213]

[cite_start]**10.3.2 Mesures de Protection IP** [cite: 214]
* [cite_start]Pas de données propriétaires dans les prompts (uniquement texte réglementaire public) [cite: 215]
* [cite_start]Embeddings générés localement [cite: 216]
* [cite_start]Logs et audit trail des requêtes [cite: 217]
* [cite_start]Option air-gapped pour environnements sensibles [cite: 218]

---

## [cite_start]11. Logique Métier et Conformité [cite: 219]

### [cite_start]11.1 Stratégie Anti-Hallucination [cite: 220]
[cite_start]La prévention des hallucinations est critique pour un outil d'aide à la décision en certification aéronautique. [cite: 221] [cite_start]L'architecture repose sur quatre niveaux de protection : [cite: 222]

[cite_start]**11.1.1 Niveau 1 — Retrieval-Grounded Responses** [cite: 223]
* [cite_start]Réponse UNIQUEMENT basée sur chunks récupérés de la base [cite: 224]
* [cite_start]Citation obligatoire des sources (node_id, reference_code) [cite: 225]
* [cite_start]Confidence score affiché à l'utilisateur [cite: 226]
* [cite_start]Si retrieval score < seuil → message explicite d'incertitude [cite: 227]

[cite_start]**11.1.2 Niveau 2 — Structured Output for Critical Decisions** [cite: 228]
[cite_start]Pour la classification Major/Minor : [cite: 229]
* [cite_start]Pas de réponse libre — checklist structurée imposée [cite: 230]
* [cite_start]Chaque critère GM 21.A.91 = question binaire + justification [cite: 231]
* [cite_start]L'IA ne « décide » pas — elle guide l'utilisateur [cite: 232]
* [cite_start]Output = tableau YES/NO/NA par critère avec sources [cite: 233]

[cite_start]**11.1.3 Niveau 3 — Human-in-the-Loop Mandatory** [cite: 234]
* [cite_start]Disclaimer systématique sur chaque réponse [cite: 235]
* [cite_start]Pas de génération de documents officiels par l'IA [cite: 236]
* [cite_start]Traçabilité complète : qui a validé, quand, avec quelles sources [cite: 237]

[cite_start]**11.1.4 Niveau 4 — Feedback Loop** [cite: 238]
* [cite_start]Bouton « Cette réponse est incorrecte » → review humain [cite: 239]
* [cite_start]Corrections intégrées dans amélioration continue [cite: 240]
* [cite_start]Métriques : taux de contestation par type de question [cite: 241]

> [cite_start]**Principe fondamental :** L'IA est un retriever et un structurer, pas un décideur. [cite: 242] [cite_start]Elle ne dit jamais « Ce changement est Minor » mais « Selon les critères GM 21.A.91, voici l'analyse. [cite: 243] La décision finale vous appartient. [cite_start]» [cite: 244]

### [cite_start]11.2 Gestion des Standards Paywalled [cite: 245]
Les standards EUROCAE/RTCA/SAE sont mis à jour sans notification publique. [cite_start]Stratégie de mitigation : [cite: 246]

[cite_start]**11.2.1 Catalog Monitoring (Automatique)** [cite: 247]
* [cite_start]Scrape des pages publiques (liste des standards) [cite: 248]
* [cite_start]Détection de nouvelles versions [cite: 249]
* [cite_start]Alerte admin → « Nouvelle version détectée, upload requis » [cite: 250]

[cite_start]**11.2.2 Upload Manuel Contrôlé** [cite: 251]
* [cite_start]Interface admin pour upload PDF [cite: 252]
* [cite_start]Parsing assisté avec validation humaine [cite: 253]
* [cite_start]Versioning strict (ED-12C v1, v2, etc.) [cite: 254]

[cite_start]**11.2.3 Integrity Checks** [cite: 255]
* [cite_start]Relations marquées « POTENTIALLY_STALE » si standard > 12 mois sans refresh [cite: 256]
* [cite_start]Warning affiché à l'utilisateur dans EXPLORE/ASK [cite: 257]
* [cite_start]Cross-reference validation avec citations EASA [cite: 258]

### [cite_start]11.3 Périmètre Subpart G (Production) [cite: 259]
[cite_start]Question soulevée : Pourquoi exclure initialement Subpart G alors que 21.A.44 inclut les obligations de coordination design/production ? [cite: 260]
[cite_start]Justification initiale : Focus Phase 1 sur le cœur TC/Changes avant élargissement. [cite: 261]
[cite_start]Limitation reconnue : Un expert TC complet doit comprendre l'interface design ↔ production. [cite: 262]
[cite_start]Approche révisée : [cite: 263]

| Phase | Couverture Subpart G |
| :--- | :--- |
| Phase 1 (PoC) | [cite_start]Interface seulement : 21.A.44 → 21.A.139 (lien placeholder) [cite: 264] |
| Phase 2 (MVP) | [cite_start]Articles clés : 21.A.139, 21.A.145, 21.A.147 [cite: 264] |
| Phase 3 | [cite_start]Couverture complète + liens bidirectionnels [cite: 264] |

---

## [cite_start]12. Stratégie et Déploiement [cite: 265]

### [cite_start]12.1 KPIs Phase 1 (Proof of Concept) [cite: 266]

[cite_start]**12.1.1 Module HARVEST** [cite: 267]
* [cite_start]✓ Scraper EASA Easy Access Rules opérationnel [cite: 268]
* [cite_start]✓ Part 21 (Subparts B, D, E) + CS-25 Chapter A ingérés [cite: 269]
* [cite_start]✓ > 500 nœuds réglementaires créés [cite: 270]
* [cite_start]✓ > 1000 relations extraites [cite: 271]
* [cite_start]✓ Détection de changement fonctionnelle (test avec NPA) [cite: 272]

[cite_start]**12.1.2 Knowledge Graph** [cite: 273]
* [cite_start]✓ Traversée 21.A.91 → toutes relations en < 100ms [cite: 274]
* [cite_start]✓ Couverture : 100% des articles Part 21 Subpart B & D [cite: 275]
* [cite_start]✓ Précision relations : > 90% (validation manuelle 50 edges) [cite: 276]

[cite_start]**12.1.3 Interface EXPLORE** [cite: 277]
* [cite_start]✓ Navigation arborescente fonctionnelle [cite: 278]
* [cite_start]✓ Affichage texte + AMC/GM associés [cite: 279]
* [cite_start]✓ Vue graphe interactive (5 utilisateurs test satisfaits) [cite: 280]

[cite_start]**12.1.4 Qualité** [cite: 281]
* [cite_start]✓ 0 erreur factuelle détectée sur Part 21 B/D [cite: 282]
* [cite_start]✓ Feedback utilisateurs test : NPS > 7/10 [cite: 283]
* [cite_start]✓ Documentation technique complète [cite: 284]

> [cite_start]Timeline cible : 8 semaines (temps partiel) [cite: 285]

### [cite_start]12.2 Framework Responsabilité Juridique [cite: 286]

[cite_start]**12.2.1 Nature de l'Outil** [cite: 287]
[cite_start]CertifExpert est un OUTIL D'AIDE À LA DÉCISION, pas un outil de décision automatique. [cite: 288] [cite_start]Analogie : comme Westlaw pour les juristes — aide à trouver l'information, ne plaide pas. [cite: 289]

[cite_start]**12.2.2 Disclaimers Contractuels (Terms of Service)** [cite: 290]
* [cite_start]« Les réponses générées sont indicatives uniquement » [cite: 291]
* [cite_start]« La responsabilité de toute décision de certification incombe exclusivement à l'utilisateur » [cite: 292]
* [cite_start]« CertifExpert ne se substitue pas à l'avis d'un CVE, DER, ou représentant Authority » [cite: 293]

[cite_start]**12.2.3 Disclaimers In-App** [cite: 294]
[cite_start]Affichés systématiquement sur chaque réponse ASK, résultat PRACTICE, et classification suggérée. [cite: 295]

[cite_start]**12.2.4 Traçabilité (Audit Log)** [cite: 296]
* [cite_start]Qui a posé quelle question, quand [cite: 297]
* [cite_start]Quelles sources ont été retournées [cite: 298]
* [cite_start]L'utilisateur a-t-il validé/contesté [cite: 299]
* [cite_start]→ En cas de litige : preuve que l'outil a fourni les bonnes sources [cite: 300]

[cite_start]**12.2.5 Architecture Défensive** [cite: 301]
[cite_start]L'IA ne génère JAMAIS : [cite: 302]
* [cite_start]De document de certification officiel [cite: 303]
* [cite_start]De classification définitive (Major/Minor) [cite: 304]
* [cite_start]De Compliance Statement [cite: 305]
* [cite_start]De signature ou approbation [cite: 306]

[cite_start]Elle génère UNIQUEMENT : [cite: 307]
* [cite_start]Des analyses sourcées [cite: 308]
* [cite_start]Des checklists à valider [cite: 309]
* [cite_start]Des références réglementaires [cite: 310]
* [cite_start]Du contenu pédagogique [cite: 311]

---

## [cite_start]13. Prochaines Étapes [cite: 312]

### [cite_start]13.1 Phase 1 — Proof of Concept (8 semaines) [cite: 313]
1. [cite_start]Implémenter le scraper EASA Easy Access Rules (Part 21, CS-25) [cite: 314]
2. [cite_start]Construire le schéma de base de données PostgreSQL [cite: 315]
3. [cite_start]Développer le parser PDF pour extraction structurée [cite: 316]
4. [cite_start]Créer le graphe de relations pour Part 21 Subparts B et D [cite: 317]
5. [cite_start]Prototyper l'interface EXPLORE [cite: 318]

### [cite_start]13.2 Phase 2 — MVP [cite: 319]
1. [cite_start]Ajouter les sources FAA et standards industriels (interface) [cite: 320]
2. [cite_start]Implémenter le RAG Engine avec ChromaDB [cite: 321]
3. [cite_start]Développer l'assistant ASK avec garde-fous anti-hallucination [cite: 322]
4. [cite_start]Créer les premiers parcours LEARN [cite: 323]
5. [cite_start]Développer 5-10 scénarios PRACTICE [cite: 324]
6. [cite_start]Ajouter Subpart G articles clés [cite: 325]

### [cite_start]13.3 Phase 3 — Production [cite: 326]
1. [cite_start]Compléter la couverture des sources (ICAO, autres autorités) [cite: 327]
2. [cite_start]Système de veille WATCH avec alertes [cite: 328]
3. [cite_start]Auto-évaluation ASSESS [cite: 329]
4. [cite_start]Multi-tenancy et RBAC complet [cite: 330]
5. [cite_start]Optimisation performance et scalabilité [cite: 331]
6. [cite_start]Déploiement utilisateurs pilotes [cite: 332]

### [cite_start]13.4 Décisions à Prendre [cite: 333]
| Décision | Options | Critères |
| :--- | :--- | :--- |
| Framework frontend | Vue.js, React | [cite_start]Compétences équipe, écosystème [cite: 334] |
| LLM pour RAG | Claude API, Mistral, Llama 3 | [cite_start]Confidentialité, coût, performance [cite: 334] |
| Hébergement | Cloud public, On-premise, Hybride | [cite_start]Sécurité, coût, maintenance [cite: 334] |
| Standards paywalled | Upload manuel, Reference-only | [cite_start]Droits, maintenance [cite: 334] |
| Modèle économique | SaaS, Licence, Freemium | [cite_start]Cible utilisateurs [cite: 334] |

---

## [cite_start]Annexe A — Glossaire [cite: 335]
| Terme | Définition |
| :--- | :--- |
| TC | [cite_start]Type Certificate — Certificat de type délivré pour un nouveau design d'aéronef [cite: 336] |
| STC | [cite_start]Supplemental Type Certificate — Certificat pour modification par un tiers [cite: 336] |
| DOA | [cite_start]Design Organisation Approval — Agrément d'organisation de conception [cite: 336] |
| POA | [cite_start]Production Organisation Approval — Agrément d'organisation de production [cite: 336] |
| DAH | [cite_start]Design Approval Holder — Détenteur d'un agrément de conception [cite: 336] |
| CVE | [cite_start]Compliance Verification Engineer — Ingénieur de vérification de conformité [cite: 336] |
| DER | [cite_start]Designated Engineering Representative (FAA) [cite: 336] |
| IR | [cite_start]Implementing Rules — Règles d'application (texte contraignant) [cite: 336] |
| AMC | [cite_start]Acceptable Means of Compliance — Moyens acceptables de conformité [cite: 336] |
| GM | [cite_start]Guidance Material — Matériel d'orientation (non contraignant) [cite: 336] |
| CS | [cite_start]Certification Specifications — Spécifications de certification [cite: 336] |
| NPA | [cite_start]Notice of Proposed Amendment — Avis de projet de modification [cite: 336] |
| TCDS | [cite_start]Type Certificate Data Sheet — Fiche de données du certificat de type [cite: 336] |
| AFM | [cite_start]Aircraft Flight Manual — Manuel de vol [cite: 336] |
| ICA | [cite_start]Instructions for Continued Airworthiness [cite: 336] |
| RAG | [cite_start]Retrieval-Augmented Generation — Architecture IA combinant recherche et génération [cite: 336] |
| RBAC | [cite_start]Role-Based Access Control — Contrôle d'accès basé sur les rôles [cite: 336] |
| ZDR | [cite_start]Zero Data Retention — Politique de non-rétention des données [cite: 336] |

---

## [cite_start]Annexe B — Références Documentaires [cite: 337]

[cite_start]**Réglementation EASA** [cite: 338]
* [cite_start]Regulation (EU) No 748/2012 — Initial Airworthiness [cite: 339]
* [cite_start]Easy Access Rules for Initial Airworthiness [cite: 340]
* [cite_start]CS-25 Large Aeroplanes — Amendment 27 [cite: 341]
* [cite_start]GM 21.A.91 Appendix A — Classification Criteria [cite: 342]
* [cite_start]GM 21.A.101 — Changed Product Rule Guidance [cite: 343]

[cite_start]**Réglementation FAA** [cite: 344]
* [cite_start]14 CFR Part 21 — Certification Procedures for Products and Articles [cite: 345]
* [cite_start]14 CFR Part 25 — Airworthiness Standards: Transport Category Airplanes [cite: 346]
* [cite_start]AC 21-40 — Guide for Approving Major Changes [cite: 347]
* [cite_start]Order 8110.4 — Type Certification [cite: 348]

[cite_start]**Standards Industriels** [cite: 349]
* [cite_start]DO-178C / ED-12C — Software Considerations in Airborne Systems [cite: 350]
* [cite_start]DO-254 / ED-80 — Design Assurance Guidance for Airborne Electronic Hardware [cite: 351]
* [cite_start]DO-326A / ED-202A — Airworthiness Security Process Specification [cite: 352]
* [cite_start]ARP4754A — Guidelines for Development of Civil Aircraft and Systems [cite: 353]
* [cite_start]ARP4761 — Guidelines and Methods for Conducting Safety Assessment [cite: 354]

---

## [cite_start]Annexe C — Trame d'Évaluation Architecture Review [cite: 355]
[cite_start]Cette trame peut être utilisée pour structurer les revues d'architecture du projet. [cite: 356] [cite_start]Chaque critère doit être évalué : [R] Risque, [P] Partiel, [V] Validé. [cite: 357]

**A. [cite_start]Architecture Technique** [cite: 358]
* ☐ A1. [cite_start]Stack technologique définie et justifiée [cite: 359]
* ☐ A2. [cite_start]Stratégie base de données graphe validée [cite: 360]
* ☐ A3. [cite_start]Modèle multi-tenant spécifié [cite: 361]
* ☐ A4. [cite_start]Architecture authentification/RBAC définie [cite: 362]
* ☐ A5. [cite_start]Choix LLM et mesures confidentialité documentés [cite: 363]
* ☐ A6. [cite_start]Plan de scalabilité documenté [cite: 364]

**B. [cite_start]Logique Métier & Conformité** [cite: 365]
* ☐ B1. [cite_start]Stratégie anti-hallucination documentée [cite: 366]
* ☐ B2. [cite_start]Périmètre réglementaire Phase 1 validé [cite: 367]
* ☐ B3. [cite_start]Gestion standards paywalled définie [cite: 368]
* ☐ B4. [cite_start]Processus validation contenu établi [cite: 369]
* ☐ B5. [cite_start]Interfaces Subpart G clarifiées [cite: 370]
* ☐ B6. [cite_start]Traçabilité des sources implémentée [cite: 371]

**C. [cite_start]Sécurité & Compliance** [cite: 372]
* ☐ C1. [cite_start]Analyse de risques sécurité réalisée [cite: 373]
* ☐ C2. [cite_start]GDPR/données personnelles adressé [cite: 374]
* ☐ C3. [cite_start]Politique de rétention données définie [cite: 375]
* ☐ C4. [cite_start]Framework responsabilité juridique établi [cite: 376]
* ☐ C5. [cite_start]Disclaimers et ToS rédigés [cite: 377]

**D. [cite_start]Stratégie & Déploiement** [cite: 378]
* ☐ D1. [cite_start]KPIs Phase 1 définis et mesurables [cite: 379]
* ☐ D2. [cite_start]Critères Go/No-Go Phase 2 établis [cite: 380]
* ☐ D3. [cite_start]Plan de test utilisateurs défini [cite: 381]
* ☐ D4. [cite_start]Roadmap 12 mois documentée [cite: 382]
* ☐ D5. [cite_start]Modèle économique esquissé [cite: 383]

**E. [cite_start]Conclusion Revue** [cite: 384]
* [cite_start]☐ APPROVED [cite: 385]
* [cite_start]☐ APPROVED WITH CONDITIONS [cite: 386]
* [cite_start]☐ REJECTED [cite: 387]


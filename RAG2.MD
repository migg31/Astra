# Plan d'Implémentation Technique : Astra RAG (v0.5.0+)

## Contexte et Objectifs
Mise en œuvre des recommandations du document `RAG.MD` pour résoudre la cécité sémantique, la perte de hiérarchie, le bruit et la dérive de version. L'architecture cible repose sur **PGVector** (Single Source of Truth), le pattern **Parent-Child**, la **Recherche Hybride (RRF)**, l'optimisation des requêtes et **Cohere Rerank**.

---

## EPIC 1 : Qualité des Données & Indexation Sémantique (Phase 1)

### Ticket 1.1 : Filtrage de Version et Préparation
- [ ] **Fichier :** `backend/rag/ingest_embeddings.py` (ou `store.py`)
- [ ] **Action :** Modifier la fonction `_fetch_nodes` (ou équivalent) pour filtrer strictement les données à la source : `WHERE is_latest = true`.
- [ ] **Objectif :** Garantir que le LLM ne cite jamais de réglementations obsolètes.

### Ticket 1.2 : Breadcrumb Injection [9] & Recursive Chunking [5]
- [ ] **Fichier :** `backend/rag/ingest_embeddings.py`
- [ ] **Action :** Implémenter un `RecursiveCharacterTextSplitter` (ex: via LangChain ou custom) pour remplacer la troncature stricte à 2000 caractères. Couper sur `\n\n` et les listes.
- [ ] **Action :** Implémenter une fonction de formatage pour chaque chunk généré : `[Source] > [Path] > [Title] \n\n [Content]`.

### Ticket 1.3 : Architecture Parent-Child [6]
- [ ] **Fichiers :** `backend/database/models.py`, `backend/rag/ingest_embeddings.py`
- [ ] **Action :** Créer une nouvelle table ou modèle pour les `chunks` (Enfants) qui contiennent le texte fragmenté et le vecteur.
- [ ] **Action :** Lier chaque `chunk` (via `parent_id`) au `regulatory_node` complet (Parent).
- [ ] **Objectif :** Vectoriser l'enfant pour la précision sémantique, mais retourner le texte du Parent complet au LLM pour le contexte.

---

## EPIC 2 : Migration Infrastructure & Recherche Hybride (Phase 2)

### Ticket 2.1 : Migration vers PGVector [2]
- [ ] **Fichiers :** `docker-compose.yml`, `backend/database/models.py`, `backend/database/migrations/`
- [ ] **Action :** Remplacer l'image Postgres classique par `pgvector/pgvector:pg16`.
- [ ] **Action :** Supprimer ChromaDB du projet.
- [ ] **Action :** Ajouter les colonnes `embedding = Column(Vector(768))` et `search_vector = Column(TSVECTOR)` aux modèles appropriés. Créer les index (HNSW et GIN).

### Ticket 2.2 : Implémentation du Dual Retrieval & RRF
- [ ] **Fichier :** `backend/rag/store.py` (ou `retriever.py`)
- [ ] **Action :** Écrire la requête SQL qui effectue la recherche hybride (Vector + FTS) et calcule le score Reciprocal Rank Fusion (RRF).
- [ ] **Action :** La fonction doit retourner les documents Parents liés aux Chunks trouvés.

---

## EPIC 3 : Advanced Retrieval Pipeline (Phases 3 & 4)

### Ticket 3.1 : Query Rewriting & Hard SQL Filtering [9]
- [ ] **Fichier :** `backend/rag/responder.py` (ou nouveau `query_analyzer.py`)
- [ ] **Action :** Avant la recherche, utiliser un appel LLM léger (ou des Regex) pour extraire les codes réglementaires de la question de l'utilisateur (ex: détection de "CS-25").
- [ ] **Action :** Utiliser ces codes comme filtres SQL stricts (`WHERE code = 'CS-25'`) dans la requête de l'Epic 2 pour réduire le bruit (The "Noise" Problem).

### Ticket 3.2 : Cohere Rerank Integration [13]
- [ ] **Fichier :** `backend/rag/responder.py`
- [ ] **Action :** Ajouter le client API Cohere.
- [ ] **Action :** Une fois le Top K documents Parents récupérés via RRF, envoyer la requête utilisateur et ces documents à l'API Cohere Rerank.
- [ ] **Action :** Ne conserver que le Top N absolu reclassé par Cohere pour le passer au LLM final.

---

## EPIC 4 : Sécurisation de la Génération (Ajout technique expert)

### Ticket 4.1 : Structured Output (Anti-Hallucination)
- [ ] **Fichier :** `backend/rag/responder.py`
- [ ] **Action :** Forcer le modèle final (Mistral/Ollama) à répondre au format JSON structuré (`{ "answer": "...", "cited_node_ids": ["..."] }`).
- [ ] **Action :** Valider via Pydantic que les `cited_node_ids` existent bien dans le contexte fourni par le retriever.

### Ticket 4.2 : Synchronisation UI
- [ ] **Fichiers :** Frontend React
- [ ] **Action :** Parser la réponse JSON. Afficher la réponse texte et transformer les `cited_node_ids` en badges cliquables interactifs pilotant l'arborescence.

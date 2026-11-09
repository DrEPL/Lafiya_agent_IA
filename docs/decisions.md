# Journal des Décisions d'Architecture (ADR) - Projet Lafiya

Ce document consigne de manière chronologique toutes les décisions techniques et d'architecture structurantes prises sur le projet, conformément à la recommandation §15 du Cahier des Charges (une ligne par décision datée).

---

| Date | ID | Décision | Justification & Références CDC | Statut |
|---|---|---|---|---|
| 2026-11-09 | ADR-001 | Architecture modulaire découplée Web / Worker | Séparation du webhook FastAPI (synchrone, réactivité < 3s requise par Meta) et du Worker Taskiq (orchestration LangGraph, Qdrant, LLM) via Redis. (§4.1, §4.2, §5.2) | Validé |
| 2026-11-09 | ADR-002 | Choix de la stack de persistance (MongoDB Atlas + Beanie 2.x) | Stockage asynchrone noSQL pour les événements de journalisation (logs), états de messages et profils pseudonymes avec index TTL natifs. (§4.1, §8.1) | Validé |
| 2026-11-09 | ADR-003 | Déduplication et idempotence par Redis (TTL 7 jours) | Utilisation de clés `dedup:{wamid}` avec expiration minimale de 7 jours pour absorber la fenêtre de renvoi automatique des requêtes Meta. (§5.3) | Validé |
| 2026-11-09 | ADR-004 | Pseudonymisation immédiate des identités (user_hash) | Hachage HMAC-SHA256 dès la réception du payload. Aucun numéro en clair ni texte de santé stocké en base ou dans les logs d'événements. (§8.2, §10.4) | Validé |
| 2026-11-09 | ADR-005 | Agent IA avec LangGraph et modèle Anthropic Claude 3.5 Haiku | Prise en charge des branchements conditionnels (triage, urgence, hors périmètre, RAG, repli) avec un LLM rapide et économique. (§4.1, §6.1, §6.4) | Validé |
| 2026-11-09 | ADR-006 | RAG strict fondé exclusivement sur le corpus OMS validé | Indexation vectorielle Qdrant (text-embedding-3-small, dim 1536) filtrée sur `status=validated`. Absence de source pertinente traitée par message standard sans hallucination. (§6.3, §6.5, §7.1) | Validé |
| 2026-11-09 | ADR-007 | Garde-fous post-génération déterministes | Contrôle systématique interdisant toute formulation diagnostique ou prescription médicale avant transmission du message à WhatsApp. (§3.2, §3.4) | Validé |
| 2026-11-09 | ADR-008 | Journalisation asynchrone bufferisée | Buffer en mémoire vidant par lots (`insert_many`) toutes les 5 secondes ou 50 entrées pour ne pas impacter la latence de traitement. (§9.4, §9.10) | Validé |
| 2026-11-09 | ADR-009 | Initialisation Git et conventions de commits sans signature | Dépôt distant GitHub configuré sur `origin/main`, exclusion stricte des secrets et commits non signés validés par revue explicite. (Consignes recommandation.txt) | Validé |

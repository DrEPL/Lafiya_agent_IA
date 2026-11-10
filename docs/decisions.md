# DECISIONS — Lafiya Agent IA

Les décisions récentes sont en haut. Une décision par bloc, ajout chronologique inverse.
Règle : si la réponse à "pourquoi ce choix ?" n'est pas ici, c'est une dette à régler avant la fin de la journée.

---

## 2026-11-09 — ADR-009 : Initialisation Git, GitHub et politique de commit sans signature

**Contexte** : Démarrage du projet Lafiya. Mise sous contrôle de version du code, sécurisation des secrets et alignement avec le dépôt distant GitHub.

**Décision** :
- Initialisation du dépôt local sur la branche principale `main` et liaison au dépôt distant `https://github.com/DrEPL/Lafiya_agent_IA.git`.
- Fichier `.gitignore` exhaustif interdisant strictement l'indexation de secrets (`.env`, `.env.*`), d'environnements virtuels (`.venv`), de caches (`__pycache__`, `.ruff_cache`, `.pytest_cache`) et de conversions temporaires de documents.
- Fichier `.env.example` modèle documentant toutes les variables nécessaires sans aucune valeur secrète.

**Pourquoi** : Garantir une traçabilité rigoureuse, empêcher toute fuite de secret dès le premier commit et respecter le protocole de validation humaine défini dans les règles de collaboration.

**Décideurs** : DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-008 : Journalisation asynchrone bufferisée en MongoDB

**Contexte** : Reconstitution de la timeline complète de chaque message entrant (`webhook_received` jusqu'à `whatsapp_sent` ou `whatsapp_failed`) sans impacter la réactivité imposée par Meta (acquit HTTP 200 en moins de 3 secondes).

**Problème** : Un appel `await LogEntry.insert()` synchrone à chaque étape intermédiaire ajouterait des allers-retours réseau bloquants incompatibles avec les contraintes de latence.

**Décision** :
- Mise en œuvre d'un buffer en mémoire (queue asyncio / liste locale) vidant les entrées par lots via `insert_many` dans la collection MongoDB `logs`.
- Déclenchement du flush selon deux seuils : toutes les 50 entrées (`LOG_BUFFER_SIZE`) ou toutes les 5 secondes (`LOG_FLUSH_INTERVAL`).
- Index TTL MongoDB sur le champ `timestamp` pour purger automatiquement les logs au terme de la période de rétention (`LOG_RETENTION_DAYS`, fixé à 30 jours pour préserver le quota de 512 Mo du cluster gratuit Atlas).
- Aucun texte de message ni numéro en clair dans les champs de détail des logs (`detail`), seul le `user_hash` est utilisé.

**Décideurs** : CDC technique v0.2 (§8.2, §8.3, §9.4, §9.7) + DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-007 : Garde-fous post-génération stricts et déterministes (Sécurité Clinique)

**Contexte** : Lafiya est un outil d'information et d'orientation grand public en santé publique (diabète, HTA). Il ne constitue pas un dispositif médical ni un outil de téléconsultation.

**Règle fondatrice, non négociable** :
- Zéro diagnostic (« vous souffrez de », « il s'agit de »).
- Zéro prescription ni modification de traitement (« prenez », « augmentez la dose »).
- Zéro interprétation d'examens ou d'images médicales.
- Toute urgence médicale (douleur thoracique, dyspnée aiguë, signes neurologiques) interrompt immédiatement la génération standard et déclenche une réponse directe orientant vers les urgences locales (`emergency_contacts`).

**Implémentation du garde-fou (nœud post-génération)** :
- Contrôle déterministe par expressions régulières et règles de filtrage avant tout envoi WhatsApp.
- En cas de violation détectée, la réponse du LLM est intégralement rejetée et substituée par un message de repli sécurisé standardisé.
- Événement consigné immédiatement dans les logs (`guardrail_failed` ou `safety_rule_triggered`).

**Décideurs** : CDC technique v0.2 (§3.1, §3.2, §3.3, §3.4) + DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-006 : RAG strict sur corpus OMS validé et gestion de l'absence de source

**Contexte** : L'assistant doit délivrer des informations médicalement validées, fiables et culturellement adaptées sur le diabète et l'hypertension artérielle en zone UEMOA.

**Décision** :
- Le corpus documentaire est constitué exclusivement de documents officiels de l'Organisation Mondiale de la Santé (OMS/WHO Fact Sheets, WHO IRIS, WHO AFRO).
- Pipeline d'ingestion hors ligne : extraction, nettoyage, découpage en chunks (500 à 800 tokens, overlap 50-100 tokens), génération de vecteurs via `text-embedding-3-small` (1 536 dimensions) et stockage dans Qdrant Cloud.
- Indexation avec métadonnées obligatoires : `source_url`, `document_title`, `publication_date`, `language`, `status=validated`. Seuls les chunks validés par le référent médical sont interrogés.
- Règle anti-hallucination : Si aucun extrait pertinent n'atteint le seuil de similarité (`RAG_SCORE_THRESHOLD`), le LLM n'est pas sollicité pour inventer une réponse. Le système renvoie un message standard d'indisponibilité de source avec orientation de consultation.

**Décideurs** : CDC technique v0.2 (§6.3, §6.5, §7.1, §7.4) + DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-005 : Orchestration d'agent par LangGraph et modèle Anthropic Claude 3.5 Haiku

**Contexte** : Le parcours de traitement d'une question nécessite des branchements conditionnels stricts (détection d'urgence, filtrage hors périmètre, triage linguistique, recherche RAG, évaluation de sécurité).

**Décision** :
- Utilisation de LangGraph pour modéliser le graphe d'états d'exécution.
- Nœuds du graphe : `triage` -> `safety_rules` -> (`direct_reply` | `retrieve` -> `generate` -> `guardrail`) -> `send_whatsapp`.
- Modèle LLM de génération : Anthropic Claude 3.5 Haiku (identifiant configuré via variable d'environnement `LLM_MODEL`). Choisi pour son ratio coût/vitesse très performant et sa rigueur dans le respect des prompts système sous contrainte.
- Prompt système intégrant l'interdiction de diagnostic/prescription et obligeant à répondre uniquement à partir des extraits fournis.

**Décideurs** : CDC technique v0.2 (§4.1, §6.1, §6.4) + DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-004 : Pseudonymisation immédiate et protection de la vie privée (RGPD / Données de santé)

**Contexte** : Traitement de données de santé sur un canal de messagerie grand public (WhatsApp). Respect impératif de la vie privée et limitation stricte de la conservation des données personnelles identifiables.

**Décision** :
- Le numéro de téléphone de l'utilisateur n'est jamais stocké en clair en base de données.
- Dès la réception du webhook, calcul d'un `user_hash = HMAC-SHA256(phone_number, USER_HASH_SECRET)`.
- Seul `user_hash` sert de clé d'identification dans les collections `user_profiles` et les traces de messages. Le numéro réel n'est relu qu'au moment précis de l'appel d'envoi vers l'API WhatsApp Graph.
- Commande `STOP` supportée nativement : suppression ou désactivation du profil utilisateur sur simple demande.
- Aucun contenu de message libre n'est journalisé dans les logs techniques standards.

**Décideurs** : CDC technique v0.2 (§8.2, §10.4) + DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-003 : Déduplication et idempotence par Redis (TTL 7 jours)

**Contexte** : Meta WhatsApp Cloud API peut rejouer un même webhook en cas de délai de réponse HTTP ou de coupure réseau, pendant une fenêtre pouvant atteindre 7 jours.

**Problème** : Risque d'envoyer plusieurs fois la même réponse à l'utilisateur ou d'exécuter des requêtes LLM redondantes et coûteuses.

**Décision** :
- Déduplication au niveau de la couche Web FastAPI dès réception du webhook via une clé Redis atomique `dedup:{wamid}` (`SET NX EX`).
- TTL de la clé fixé à 7 jours (604 800 secondes) pour couvrir intégralement la fenêtre de retry de Meta.
- États de la clé : `processing` lors de la prise en charge, puis `done` après traitement.
- En cas de détection d'un doublon : retour immédiat d'un code HTTP 200 OK à Meta et arrêt du traitement, avec émission de l'événement `duplicate_detected`.

**Décideurs** : CDC technique v0.2 (§5.2, §5.3) + DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-002 : Persistance opérationnelle via MongoDB Atlas et ODM Beanie 2.x

**Contexte** : Besoin d'un stockage flexible, asynchrone et persistant pour les événements de journalisation (`LogEntry`), le suivi d'état des messages (`InboundMessage`), les profils pseudonymes (`UserProfile`), les répertoires de santé (`HealthFacility`) et les traces d'audit (`AnswerTrace`).

**Décision** :
- Utilisation de MongoDB Atlas (cluster gratuit au stade prototype) avec le driver asynchrone Motor et l'ODM Beanie 2.x.
- Remplacement des structures relationnelles héritées d'anciennes versions par des documents Pydantic typés avec initialisation via le cycle de vie FastAPI (`lifespan`).
- Création automatique des index au démarrage de l'application (index uniques sur `wamid`, `user_hash` et index TTL automatiques sur les dates d'expiration).
- Tâche quotidienne automatisée (planificateur) effectuant un `find_one` pour maintenir actif le cluster Atlas et prévenir la mise en veille automatique après 30 jours d'inactivité.

**Décideurs** : CDC technique v0.2 (§4.1, §4.4, §8.1, §8.2) + DrEPL (développeur) (2026-11-09).

---

## 2026-11-09 — ADR-001 : Architecture découplée Web (FastAPI) et Worker (Taskiq + Redis)

**Contexte** : Meta WhatsApp impose un acquittement strict du webhook HTTP en moins de 3 secondes sous peine d'échec de distribution et de renvois en boucle. L'exécution d'un pipeline complet (triage, recherche vectorielle Qdrant, génération LLM Claude, contrôle de garde-fou) excède fréquemment cette durée.

**Décision** :
- Séparation stricte de l'application en deux processus découplés :
  1. **Processus Web (FastAPI)** : vérification de la signature HMAC-SHA256 (`X-Hub-Signature-256`), déduplication Redis, mise en file de la tâche via Taskiq, et retour immédiat d'un code 200 OK à Meta.
  2. **Processus Worker (Taskiq)** : dépilage de la tâche depuis Redis, exécution du graphe LangGraph (recherche RAG, appels LLM, garde-fous) et appel de l'API Graph Meta pour expédier la réponse.
- Aucune opération d'inférence LLM ni de recherche vectorielle n'est exécutée dans le cycle de requête Web.

**Décideurs** : CDC technique v0.2 (§4.1, §4.2, §5.2) + DrEPL (développeur) (2026-11-09).

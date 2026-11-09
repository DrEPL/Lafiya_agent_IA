# Lafiya - Assistant IA WhatsApp de Prévention Santé

Assistant WhatsApp d'information et d'orientation sur le **diabète** et l'**hypertension artérielle** dans la zone UEMOA.

## Principes clés & Limites cliniques
- **Information et orientation uniquement** : pas de diagnostic médical, pas de prescription thérapeutique.
- **Orientation vérifiée** : répertoires fixes de structures sanitaires et de numéros d'urgence validés.
- **Confidentialité** : pseudonymisation immédiate (`user_hash`), aucun texte médical ni numéro en clair dans les logs d'événements.
- **Corpus OMS validé** : génération appuyée sur une recherche RAG stricte de sources officielles validées par le référent médical.

## Architecture
- **Web API** : FastAPI (réception webhook Meta WhatsApp, déduplication Redis, mise en file Taskiq).
- **Worker** : Taskiq + LangGraph (triage, garde-fous, recherche vectorielle Qdrant, génération LLM Anthropic Claude).
- **Stockage opérationnel & Logs** : MongoDB Atlas piloté par Beanie 2.x asynchrone (index TTL sur les événements).
- **Cache & Déduplication** : Redis (TTL 7 jours sur les wamid).

## Documentation
- [Journal des Décisions d'Architecture (ADR)](docs/decisions.md)

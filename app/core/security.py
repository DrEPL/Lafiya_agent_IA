"""Module de sécurité pour le webhook Meta et la protection des données.

Conformité CDC :
- Vérification de la signature HMAC-SHA256 (X-Hub-Signature-256) en temps constant (§5.7, §10.3).
- Pseudonymisation immédiate du numéro de téléphone de l'utilisateur (§8.2, §10.4).
"""

import hashlib
import hmac


def verify_whatsapp_signature(
    payload_body: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    """Vérifie l'authenticité de la signature envoyée par Meta.

    Args:
        payload_body: Corps brut (raw bytes) de la requête HTTP entrante.
        signature_header: En-tête 'X-Hub-Signature-256' transmis par Meta (format: 'sha256=...').
        app_secret: Secret de l'application Meta WhatsApp Cloud.

    Returns:
        True si la signature est valide, False sinon.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header[7:].strip()
    computed_signature = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


def hash_phone_number(phone_number: str, hash_secret: str) -> str:
    """Génère le pseudonyme 'user_hash' irréversible d'un numéro de téléphone.

    Aucun numéro en clair n'est stocké en base de données. Seul ce hash
    est utilisé comme identifiant dans les profils et les traces.

    Args:
        phone_number: Numéro au format international (ex. '221770000000').
        hash_secret: Secret cryptographique de pseudonymisation (USER_HASH_SECRET).

    Returns:
        Chaîne hexadécimale SHA-256 du numéro haché avec sel secret.
    """
    normalized_phone = phone_number.strip().replace(" ", "").replace("+", "")
    return hmac.new(
        key=hash_secret.encode("utf-8"),
        msg=normalized_phone.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

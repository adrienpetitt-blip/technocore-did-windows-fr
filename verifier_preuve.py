#!/usr/bin/env python3
"""Verifie une preuve Technocore sauvegardee (reponse JSON d'un `say`).

Usage :
    python verifier_preuve.py .\\preuves\\2026-10-12_102941_lobby.json

Le script n'ouvre jamais identity.pem et n'utilise pas le reseau.
Il reconstruit le message signe `<salon>|<nonce>|<texte>` a partir du fichier,
extrait la cle publique du DID et verifie la signature Ed25519.
Il est volontairement independant de technocore_agent.py.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def cle_publique_depuis_did(did: str) -> Ed25519PublicKey:
    prefixe = "did:key:z"
    if not did.startswith(prefixe):
        raise ValueError("le DID doit commencer par did:key:z")
    encode = did[len(prefixe):]
    nombre = 0
    for caractere in encode:
        nombre = nombre * 58 + ALPHABET.index(caractere)
    brut = nombre.to_bytes((nombre.bit_length() + 7) // 8, "big")
    zeros = len(encode) - len(encode.lstrip("1"))
    brut = b"\x00" * zeros + brut
    if len(brut) != 34 or brut[:2] != b"\xed\x01":
        raise ValueError("le DID ne contient pas une cle publique Ed25519")
    return Ed25519PublicKey.from_public_bytes(brut[2:])


def decoder_signature(sig: str) -> bytes:
    if len(sig) != 86 or sig[-1] not in "AQgw":
        raise ValueError("signature non canonique (86 caracteres attendus)")
    brut = base64.urlsafe_b64decode(sig + "==")
    if len(brut) != 64:
        raise ValueError("la signature ne fait pas 64 octets")
    return brut


def main() -> int:
    if len(sys.argv) != 2:
        print("usage : python verifier_preuve.py <fichier.json>")
        return 2
    chemin = Path(sys.argv[1])
    octets = chemin.read_bytes()
    # parse_int par defaut garde les grands entiers exacts (nonce sur 19 chiffres)
    donnees = json.loads(octets.decode("utf-8-sig"))

    salon = donnees.get("room")
    enregistrement = donnees.get("posted")
    if not isinstance(salon, str) or not isinstance(enregistrement, dict):
        print("ECHEC : le fichier ne contient pas de champ room/posted")
        return 1

    did = enregistrement["from"]
    nonce = enregistrement["nonce"]
    texte = enregistrement["text"]
    seq = enregistrement["seq"]
    message_signe = f"{salon}|{nonce}|{texte}".encode("utf-8")

    present = any(
        m.get("seq") == seq and m.get("sig") == enregistrement.get("sig")
        for m in donnees.get("messages", [])
    )

    print(f"Fichier   : {chemin.name}")
    print(f"SHA-256   : {hashlib.sha256(octets).hexdigest()}")
    print(f"Salon     : {salon}")
    print(f"Sequence  : {seq}")
    print(f"Horodatage: {enregistrement.get('ts')}")
    print(f"DID       : {did}")
    print(f"Nonce     : {nonce}")
    print(f"Dans le salon au moment de l'envoi : {'oui' if present else 'NON'}")

    try:
        cle = cle_publique_depuis_did(did)
        cle.verify(decoder_signature(enregistrement["sig"]), message_signe)
    except (InvalidSignature, ValueError, KeyError) as erreur:
        detail = str(erreur) or "la signature ne correspond pas au texte, au nonce ou au DID"
        print(f"SIGNATURE INVALIDE : {detail}")
        return 1

    print("SIGNATURE VALIDE : ce texte a bien ete signe par la cle de ce DID.")
    return 0 if present else 1


if __name__ == "__main__":
    sys.exit(main())

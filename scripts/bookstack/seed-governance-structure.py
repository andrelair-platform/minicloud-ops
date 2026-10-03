#!/usr/bin/env python3
"""
Seed the BookStack governance intranet information architecture (idempotent).

Creates the 12 function **shelves** (minicloud-platform-docs insurance-platform/governance-intranet §6),
and for the Phase-1 pilot shelves (RH, Juridique, Underwriting) a "Cadre de gouvernance" book holding the
5 hierarchy template pages (Politique → Standard → Directive → Procédure → Runbook, §6). Re-runnable:
skips anything whose name already exists.

RUN ON THE CONTROLLER. Reads the BookStack API token from Vault `platform/bookstack` key `api-token`
(bootstrap it first with bootstrap-token-to-vault.sh) using the read-only ops token, and talks to the
internal API over the minicloud CA.
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
VAULT = "https://vault.10.0.0.200.nip.io"
BASE = "https://intranet.10.0.0.200.nip.io/api"
CA = f"{HOME}/minicloud-ca.crt"
CTX = ssl.create_default_context(cafile=CA)

SHELVES = [
    ("RH", "Ressources Humaines — charte de travail, règlement intérieur, onboarding"),
    ("Juridique", "Legal — modèles de contrats, notes juridiques, clauses"),
    ("Underwriting", "Souscription — appétit, éligibilité, référral, DoA, tarification"),
    ("Claims", "Sinistres — gestion, réserves, recours, fraude/SIU"),
    ("Pricing & Portfolio", "Tarification & portefeuille — standards de pricing, pilotage"),
    ("Risk Engineering", "Ingénierie des risques — audits de site, prévention, CAT"),
    ("Reinsurance & Captive", "Réassurance & captive — traités, facultatives, fronting"),
    ("Finance & Actuarial", "Finance & actuariat — provisionnement, investissement, IFRS 17"),
    ("Compliance & Governance", "Conformité & gouvernance — Solvabilité II, ORSA, contrôle interne"),
    ("IT / Security / DORA", "IT / Sécurité / DORA — InfoSec, BCP, incident, change"),
    ("International Programmes", "Programmes internationaux — polices master/locales, flux cross-border"),
    ("Corporate / Direction", "Corporate / Direction — gouvernance d'entreprise, délégations"),
]

# Shelves that get a governance book now (need-first: the 3 Phase-1 pilots + IT/Security/DORA for the
# live platform/IS capabilities annotated in Backstage). Others get a book when a live capability maps to them.
PILOTS = ["RH", "Juridique", "Underwriting", "IT / Security / DORA"]

# the 5-level documentation hierarchy (§6) — template pages seeded in each pilot's governance book
HIERARCHY = [
    ("01 Politique (Policy)",
     "**Niveau : POLICY — Quoi / Pourquoi / principe obligatoire.**\n\n"
     "Portée Groupe/Entreprise, approuvée par le conseil / le CUO. Énonce l'intention et les principes "
     "non négociables. Ne décrit PAS le comment (voir Directive / Procédure).\n\n"
     "> _Gabarit — remplacer :_ objet · champ d'application · principes · autorité d'approbation · "
     "cadence de revue · références réglementaires (Solvabilité II Pilier 2, IDD, DORA, ACPR)."),
    ("02 Standard",
     "**Niveau : STANDARD — exigences obligatoires (ce qui DOIT être vrai).**\n\n"
     "Rend la Politique mesurable : seuils, contrôles obligatoires, exigences minimales.\n\n"
     "> _Gabarit :_ exigences · seuils · contrôles requis · preuves attendues."),
    ("03 Directive (Guideline)",
     "**Niveau : GUIDELINE — comment on opère normalement (la référence métier du quotidien).**\n\n"
     "La référence que le métier consulte pour travailler. Pour l'Underwriting, un sous-ensemble de ces "
     "directives est aussi **exécutable** (appétit / éligibilité / référral / tarification) — voir le "
     "complément exécutable.\n\n"
     "> _Gabarit :_ bonnes pratiques · cas · exceptions · liens vers les règles exécutables."),
    ("04 Procédure",
     "**Niveau : PROCEDURE — le processus exact (pas-à-pas).**\n\n"
     "> _Gabarit :_ déclencheur · étapes numérotées · rôles (four-eyes / SoD) · entrées/sorties."),
    ("05 Runbook",
     "**Niveau : RUNBOOK — exécution opérationnelle (gestes concrets).**\n\n"
     "> _Gabarit :_ préconditions · commandes/actions · vérifications · rollback · escalade."),
]

EXTRA_PAGES = {
    "Underwriting": [
        ("00 Complément exécutable (policy-as-code)",
         "Un sous-ensemble des directives de souscription est **exécuté** par le workbench "
         "`ktayl-underwriting` : appétit, éligibilité, référral, plafonds DoA, planchers de tarification, "
         "four-eyes. L'intranet reste la **source de vérité** ; les workflows en appliquent les règles "
         "critiques.\n\nFamilles de gouvernance couvertes : **03 Underwriting · 04 Pricing & Portfolio · "
         "07 Risk Engineering**. Registre de capacités (Backstage) : colonnes Policy/Standard/Guideline/"
         "Procedure/Controls/Approval/Evidence (§8)."),
    ],
}


def api(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Token {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return json.loads(r.read() or "{}")


def vault_api_token():
    ops = open(f"{HOME}/.vault-ops-token").read().strip()
    req = urllib.request.Request(f"{VAULT}/v1/secret/data/platform/bookstack")
    req.add_header("X-Vault-Token", ops)
    with urllib.request.urlopen(req, context=CTX, timeout=15) as r:
        return json.loads(r.read())["data"]["data"]["api-token"]


def list_all(kind, token):
    out, offset = {}, 0
    while True:
        page = api("GET", f"/{kind}?count=100&offset={offset}", token=token)
        for it in page.get("data", []):
            out[it["name"]] = it["id"]
        if offset + 100 >= page.get("total", 0):
            break
        offset += 100
    return out


def main():
    token = vault_api_token()
    shelves = list_all("shelves", token)
    books = list_all("books", token)

    # 1. shelves
    for name, desc in SHELVES:
        if name not in shelves:
            shelves[name] = api("POST", "/shelves", {"name": name, "description": desc}, token)["id"]
            print(f"+ shelf  {name}")
        else:
            print(f"= shelf  {name}")

    # 2. pilot governance books + hierarchy pages
    for shelf_name in PILOTS:
        book_name = f"{shelf_name} — Cadre de gouvernance"
        if book_name not in books:
            book_id = api("POST", "/books", {"name": book_name,
                          "description": f"Hiérarchie documentaire de gouvernance — {shelf_name}"}, token)["id"]
            books[book_name] = book_id
            print(f"+ book   {book_name}")
        else:
            book_id = books[book_name]
            print(f"= book   {book_name}")
        # attach the book to its shelf
        api("PUT", f"/shelves/{shelves[shelf_name]}", {"books": [book_id]}, token)
        # pages: extras first, then the 5 hierarchy levels
        existing_pages = {p["name"] for p in api("GET", f"/books/{book_id}", token=token).get("contents", [])}
        for title, md in EXTRA_PAGES.get(shelf_name, []) + HIERARCHY:
            if title not in existing_pages:
                api("POST", "/pages", {"book_id": book_id, "name": title, "markdown": md}, token)
                print(f"    + page {shelf_name} / {title}")

    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:300]}")

#!/usr/bin/env python3
"""
Populate the BookStack governance books with simulated-but-credible content (idempotent — overwrites
the gabarit page bodies). Grounded in Solvency II Pillar 2 (system of governance), IDD POG, DORA
(5 pillars), GDPR/ACPR. SIMULATION content for the ktayl-solution insurance IS — not legal advice.

RUN ON THE CONTROLLER. Reads the API token from Vault `platform/bookstack` (ops token) over the minicloud CA.
Content is keyed by (book_slug, page_slug) and PUT to the matching existing pages.
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
VAULT = "https://vault.10.0.0.200.nip.io"
INTERNAL = "https://intranet.10.0.0.200.nip.io/api"
CTX = ssl.create_default_context(cafile=f"{HOME}/minicloud-ca.crt")

UW = "underwriting-cadre-de-gouvernance"
IT = "it-security-dora-cadre-de-gouvernance"
RH = "rh-cadre-de-gouvernance"
JUR = "juridique-cadre-de-gouvernance"

CONTENT = {
    # ───────────────────────── UNDERWRITING ─────────────────────────
    (UW, "01-politique-policy"): """# Politique de souscription

> **Niveau : POLITIQUE** · Approuvée par le CUO / Comité de souscription · Revue annuelle
> *Document de simulation — ktayl-solution (assureur IARD B2B). Cadre Solvabilité II Pilier 2 + IDD.*

## 1. Objet
Définir les principes d'acceptation et de tarification des risques, en cohérence avec l'**appétit au
risque** du Groupe et la stratégie de souscription, afin de protéger la solvabilité et la rentabilité
technique de ktayl-solution.

## 2. Champ d'application
Toutes les branches IARD B2B souscrites par ktayl-solution (Dommages aux biens, Bris de machine,
Responsabilité civile, Lignes financières, Marine, Construction, Programmes internationaux).

## 3. Principes directeurs
1. **Souscrire dans l'appétit défini** — aucun risque hors-appétit sans dérogation tracée et approuvée.
2. **Séparation des pouvoirs** — toute acceptation respecte la **matrice de délégation (DoA)**.
3. **Double regard (four-eyes)** — au-delà des seuils, une seconde validation indépendante est obligatoire.
4. **Plancher technique** — aucune prime inférieure à la prime technique (sinistralité attendue + chargements).
5. **Conformité** — filtrage sanctions / LCB-FT et respect de la **gouvernance produit (IDD/POG)** sur le marché cible.
6. **Traçabilité** — chaque décision (accepter / référer / refuser) est documentée et auditable.

## 4. Rôles et autorité
- **CUO (Chief Underwriting Officer)** — titulaire de la politique ; approuve les dérogations majeures.
- **Comité de souscription** — arbitre les risques au-delà de la DoA individuelle.
- **Conseil d'administration** — approuve l'appétit au risque (via l'ORSA).

## 5. Références
Solvabilité II (art. 41-44, système de gouvernance) · IDD art. 25 (POG) · Politique de gestion des
risques · ORSA · Politique LCB-FT & sanctions. Déclinaison opérationnelle : voir le **Standard**, la
**Directive** et le **complément exécutable** (`ktayl-underwriting`).
""",
    (UW, "02-standard"): """# Standard de souscription

> **Niveau : STANDARD** — exigences obligatoires (ce qui DOIT être vrai). *Simulation.*

## Exigences minimales
| # | Exigence | Contrôle |
|---|---|---|
| S1 | Tout risque est évalué contre la **grille d'appétit** (branche, exposition, zone CAT) | Badge appétit dans le workbench |
| S2 | Le **dossier de souscription** est complet (valeurs assurées, sinistralité ≥ 5 ans, géo-CAT, rapports RE) | Contrôle de complétude |
| S3 | **Référral obligatoire** au-dessus des seuils (voir Directive) | Blocage workflow jusqu'à décision |
| S4 | Prime **≥ prime technique** (sinistralité attendue + frais + coût du capital + marge) | Contrôle tarifaire / plancher |
| S5 | **Cumul CAT** par zone suivi et dans la limite de rétention/traité | Contrôle des cumuls |
| S6 | Filtrage **sanctions / LCB-FT** effectué | Écran de conformité |
| S7 | **Décision documentée** + justification + approbation | Journal d'audit append-only |

## Seuils de référence (simulation)
- Capacité maximale par risque : **25 M€** (au-delà → Comité de souscription).
- Rétention nette par sinistre : **2 M€** (au-delà → réassurance facultative).
- Limite de cumul CAT par zone : définie par la Politique de réassurance.

Les seuils chiffrés et la matrice DoA font l'objet de la **Directive de souscription**.
""",
    (UW, "03-directive-guideline"): """# Directive de souscription

> **Niveau : DIRECTIVE** — la référence métier du quotidien. Un sous-ensemble est **exécuté** par
> `ktayl-underwriting` (voir *Complément exécutable*). *Simulation.*

## 1. Appétit par branche
| Branche | Appétit préféré | Neutre | Hors-appétit |
|---|---|---|---|
| Dommages aux biens | Tertiaire, industrie légère, valeurs < 25 M€ | Industrie lourde | Sites SEVESO seuil haut sans prévention |
| Bris de machine | Équipements standards, maintenance documentée | Équipements critiques | Prototypes / sans historique |
| Responsabilité civile | PME/ETI services & industrie | Grandes expositions US | Produits à rappel systémique |
| Lignes financières | D&O ETI non cotées | Sociétés cotées | Entités sous enquête |
| Marine | Marchandises conteneurisées | Vrac spécialisé | Zones sous embargo |

## 2. Déclencheurs de référral (obligatoire)
| Critère | Seuil → référral | Référer vers |
|---|---|---|
| Capacité demandée | > 25 M€ | Comité de souscription |
| Zone CAT | Cumul zone > limite traité | Risk Engineering + Réassurance |
| Sinistralité | Ratio S/P 5 ans > 70 % | Souscripteur senior |
| Dérogation tarifaire | Prime < plancher technique | CUO |
| Marché cible (POG) | Hors marché cible défini | Conformité produit |

## 3. Matrice de délégation (DoA)
| Niveau | Prime annuelle | Capacité | Autorité |
|---|---|---|---|
| N1 — Souscripteur | ≤ 50 k€ | ≤ 5 M€ | Individuelle |
| N2 — Souscripteur senior | ≤ 250 k€ | ≤ 15 M€ | + four-eyes |
| N3 — Responsable souscription | ≤ 1 M€ | ≤ 25 M€ | + four-eyes |
| N4 — CUO / Comité | > 1 M€ | > 25 M€ | Comité |

## 4. Tarification
La prime proposée doit être **≥ au plancher technique**. Toute dérogation exige un référral CUO et une
justification écrite. Les chargements (frais, acquisition, coût du capital, marge) suivent le barème en vigueur.

## 5. Double regard & séparation des tâches
Le souscripteur qui prépare une cotation ne peut pas être le valideur final au-dessus des seuils N2+.
La liaison (bind) impose un four-eyes indépendant.

➡️ **Exécution :** ces règles d'appétit / éligibilité / référral / DoA / plancher sont appliquées en
ligne par `ktayl-underwriting` — voir le *Complément exécutable*.
""",
    (UW, "04-procedure"): """# Procédure de souscription

> **Niveau : PROCÉDURE** — le processus exact, pas-à-pas. *Simulation.*

1. **Réception de la soumission** (courtier → Submission Hub) : enregistrement + référence.
2. **Complétude du dossier** : valeurs, sinistralité, géo-CAT, rapports RE. Incomplet → retour courtier.
3. **Éligibilité & appétit** : évaluation contre la grille (Directive §1). Hors-appétit → référral ou refus.
4. **Tarification** : calcul de la prime technique + chargements ; comparaison au plancher.
5. **Référral** (si un seuil de la Directive §2 est atteint) : blocage jusqu'à décision de l'autorité compétente.
6. **Décision** : *accepter* / *référer* / *refuser*, avec justification.
7. **Double regard (four-eyes)** au-dessus des seuils N2+ (Directive §3).
8. **Liaison (bind)** : création de la police dans le PAS (`ktayl-policy-service`) ; contrat immuable.
9. **Émission** : documents contractuels + notification courtier ; écriture au journal d'audit.
""",
    (UW, "05-runbook"): """# Runbook — souscription dans le workbench

> **Niveau : RUNBOOK** — gestes opérationnels dans `ktayl-underwriting`. *Simulation.*

- **Ouvrir une soumission** : *Submissions → la référence*. Le **badge d'appétit** (vert/orange/rouge) indique l'éligibilité.
- **Déclencher un référral** : si le workbench signale un seuil atteint, le dossier passe en *Referred* ; renseigner le motif.
- **Saisir une dérogation** : champ *Dérogation* + justification → routage automatique vers le CUO.
- **Valider en four-eyes** : un second souscripteur habilité ouvre *Pending approval* → *Approve/Reject*.
- **Lier (bind)** : *Decision → Bind* ; la police est créée dans le PAS (immuable) et consignée au journal d'audit.
- **En cas d'erreur** : une police liée ne se modifie pas — émettre un avenant / annulation selon la Procédure.
""",
    (UW, "00-complement-executable-policy-as-code"): """# Complément exécutable (policy-as-code)

Un sous-ensemble des **directives de souscription** est **exécuté** par le workbench
`ktayl-underwriting` — l'intranet reste la **source de vérité**, les workflows en appliquent les règles critiques.

## Règles appliquées en ligne
| Règle (Directive) | Appliquée par |
|---|---|
| Appétit / éligibilité par branche (§1) | Moteur d'appétit (badge) |
| Déclencheurs de référral (§2) | Blocage workflow + routage |
| Matrice de délégation / DoA (§3) | Contrôle d'autorité au bind |
| Plancher de tarification (§4) | Contrôle tarifaire |
| Double regard / SoD (§5) | Étape d'approbation |

**Familles de gouvernance couvertes :** 03 Underwriting · 04 Pricing & Portfolio · 07 Risk Engineering.
**Registre de capacités (Backstage) :** la carte *Gouvernance & conformité* de `ktayl-underwriting`
relie ce service à la Politique / au Standard / à la Directive / à la Procédure ci-contre.
""",
    # ───────────────────────── IT / SECURITY / DORA ─────────────────────────
    (IT, "01-politique-policy"): """# Politique de gouvernance ICT (DORA)

> **Niveau : POLITIQUE** · Titulaire : RSSI / Platform Admins · Revue annuelle. *Simulation.*

## 1. Objet
Assurer la **résilience opérationnelle numérique** de ktayl-solution conformément au règlement **DORA**
(UE 2022/2554) : gérer le risque ICT, détecter et traiter les incidents, tester la résilience, et
maîtriser le risque lié aux prestataires tiers.

## 2. Les 5 piliers DORA
1. **Gestion du risque ICT** — cadre d'identification, protection, détection, réponse et reprise.
2. **Gestion & notification des incidents** — classification harmonisée, notification au régulateur.
3. **Tests de résilience** — tests réguliers (jusqu'au TLPT pour les entités significatives).
4. **Risque lié aux tiers ICT** — registre des prestataires, clauses contractuelles, stratégie de sortie.
5. **Partage d'information** — échange de renseignements sur les cybermenaces.

## 3. Principes
- **Tout changement en production passe par le Git** (PR + CODEOWNERS) — aucune modification manuelle.
- **Identité = périmètre** : SSO Authentik + MFA, moindre privilège, default-deny réseau.
- **Chaîne d'approvisionnement** : images signées (cosign) + SBOM ; admission contrôlée (Gatekeeper/OPA).
- **Continuité** : sauvegardes testées (restauration prouvée), auto-unseal, RTO/RPO définis.

## 4. Références
DORA art. 5-16 (gestion du risque ICT), art. 17-23 (incidents), art. 24-27 (tests), art. 28-30 (tiers) ·
NIS2 · Politique de sécurité de l'information. Déclinaison : Standard & Directive ci-contre.
""",
    (IT, "02-standard"): """# Standard — gestion des changements & sécurité

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

| # | Exigence | Contrôle |
|---|---|---|
| C1 | Toute modification de production via **PR + revue CODEOWNERS** | Règle de branche / ruleset |
| C2 | **Commits signés** (GPG) | Ruleset "verified signatures" |
| C3 | Images **signées cosign + SBOM** attaché | CI (dual-push ghcr) |
| C4 | **Admission contrôlée** (Gatekeeper/OPA) : non-root, pas de `:latest`, registres autorisés, limites | Webhook d'admission |
| C5 | **Aucune action manuelle** sur ArgoCD (sync/patch) — réconciliation GitOps uniquement | Hook + discipline |
| C6 | Secrets via **Vault → ESO** (jamais en clair dans Git) | `guard-write` + revue |
| C7 | **Change-record** (un enregistrement d'audit ITIL/DORA par PR de prod) | Automatisation |
| C8 | **Sauvegardes** quotidiennes + **restauration testée** (RTO/RPO) | Drill de restauration |

## Seuils / fenêtres
- Déploiement prod : via PR gated (pas de fenêtre figée — canary + rollback automatique).
- Incident majeur ICT : notification initiale selon les délais DORA.
""",
    (IT, "03-directive-guideline"): """# Directive — GitOps & déploiement

> **Niveau : DIRECTIVE** — la référence d'ingénierie. *Simulation.*

## Flux de livraison (trunk-based)
`PR → CI (build+test+scan+sign+SBOM) → merge main → Kargo promeut dev → (vérif) → PR prod gated CODEOWNERS → ArgoCD`

- **Un seul artefact** promu de dev vers prod (Kargo) — jamais d'édition manuelle de tag.
- **Prod auto-sync git-gated** : l'approbation vit dans Git (PR), ArgoCD réconcilie (~3 min).
- **Livraison progressive** : Rollout canary + analyse métrique → abandon automatique si dégradation.
- **Secrets** : `ExternalSecret` → Vault ; jamais de secret en clair.
- **Réseau** : default-deny egress + autorisations explicites (DLP, egouvernée).

## Bonnes pratiques
- Branches courtes (`feat/`,`fix/`), supprimées à la fusion.
- Un service custom (dev+prod, image propre, tag immuable) → **Kargo** ; sinon bump de version → ArgoCD.
- Pas de pin d'hôte (`nodeSelector`) — Longhorn est réseau ; éviter les SPOF.
""",
    (IT, "04-procedure"): """# Procédure — changement en production (PR → prod)

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation.*

1. **Brancher** depuis `main` (`feat/`/`fix/`).
2. **Implémenter + tester** (L0-L4 selon le tier) ; mettre à jour la documentation.
3. **Ouvrir la PR** → la CI s'exécute (lint, tests, scan Trivy/Checkov, build, cosign, SBOM).
4. **Revue CODEOWNERS** sur les chemins gated ; corriger jusqu'au vert.
5. **Fusion `--squash`** (commit signé) → `main`.
6. **Kargo** promeut l'artefact en **dev**, vérifie, puis ouvre la **PR de prod** (gated CODEOWNERS).
7. **Approbation prod** → fusion → **ArgoCD** réconcilie ; le **change-record** est créé.
8. **Surveiller** le canary ; en cas de dégradation, abandon/rollback automatique.
""",
    (IT, "05-runbook"): """# Runbook — incident ICT & reprise

> **Niveau : RUNBOOK** — gestes opérationnels. *Simulation.*

## Incident ICT (cycle DORA)
1. **Détecter** (alerte Prometheus/Alertmanager, Falco, log Loki).
2. **Classifier** (gravité, impact, fonctions touchées) selon la grille DORA.
3. **Notifier** (interne ; régulateur si seuil majeur atteint, délais DORA).
4. **Contenir** (isoler, cordon de nœud, bascule de service).
5. **Rétablir** (rollback GitOps / restauration depuis sauvegarde).
6. **Post-mortem** + alimentation de la bibliothèque de contrôles.

## Reprise (exemples)
- **Rollback applicatif** : revenir au tag précédent via PR (Kargo/ArgoCD).
- **Restauration base** : CNPG depuis la sauvegarde (R2), RTO prouvé par drill.
- **Nœud défaillant** : cordon + reprogrammation (volumes Longhorn réseau se rattachent ailleurs).
""",
    # ───────────────────────── RH ─────────────────────────
    (RH, "01-politique-policy"): """# Politique RH

> **Niveau : POLITIQUE** · Titulaire : DRH · Revue annuelle. *Simulation.*

## 1. Objet
Définir le cadre de gestion des collaborateurs de ktayl-solution : recrutement, intégration, conditions
de travail, et protection des données des salariés.

## 2. Principes
1. **Égalité de traitement & non-discrimination** à toutes les étapes.
2. **Protection des données RH (RGPD)** — minimisation, finalité, durée de conservation, droits des personnes.
3. **Poste de travail numérique BYOD** — appareils personnels, accès navigateur-first, identité = périmètre (charte numérique).
4. **Moindre privilège** — accès applicatifs accordés par rôle, via le processus IAM à double approbation.

## 3. Autorité
DRH (titulaire) ; Direction pour les décisions structurantes ; DPO consulté pour les traitements de données RH.

## 4. Références
Code du travail · RGPD · Charte informatique / numérique · Politique d'accès (IAM/IGA). Déclinaison :
Standard, Directive, Procédure ci-contre.
""",
    (RH, "02-standard"): """# Standard RH

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

| # | Exigence |
|---|---|
| R1 | Un **règlement intérieur** et une **charte informatique** signés à l'embauche |
| R2 | **Temps de travail** conforme et enregistré selon la réglementation |
| R3 | Données RH conservées selon la **durée légale** puis purgées (RGPD) |
| R4 | Tout accès applicatif via le **processus IAM à double approbation** (jamais de compte partagé) |
| R5 | **Offboarding** : révocation des accès le jour du départ |
| R6 | **MFA** obligatoire sur toutes les applications SSO |
""",
    (RH, "03-directive-guideline"): """# Directive RH

> **Niveau : DIRECTIVE** — référence quotidienne. *Simulation.*

## Intégration (onboarding)
- Création de l'identité (Authentik) + rattachement aux **groupes `Direction …`** correspondant au poste.
- Remise de la charte numérique + accès aux espaces intranet pertinents (BookStack, par shelf).
- Parcours d'intégration (1ère semaine) + référent.

## Télétravail / BYOD
- Appareils personnels : accès **navigateur-first**, données côté serveur, pas de synchronisation locale pour les données CONFIDENTIEL/RESTREINT.
- Sessions SSO + MFA ; ré-authentification pour les actions sensibles.

## Mouvements / départs
- Changement de poste → ajustement des groupes (droits) via IAM.
- Départ → **offboarding** (révocation immédiate, voir Procédure).
""",
    (RH, "04-procedure"): """# Procédure — intégration & départ

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation.*

## Onboarding
1. Demande RH → création de l'identité (Authentik).
2. Rattachement aux groupes `Direction …` selon la fiche de poste (→ rôles applicatifs synchronisés).
3. Signature règlement intérieur + charte informatique.
4. Attribution des accès (demande IAM → **double approbation** → provisioning).
5. Parcours d'intégration + remise des accès intranet.

## Offboarding
1. Notification de départ (RH).
2. **Révocation des accès** (désactivation Authentik + retrait des groupes) le jour J.
3. Restitution / effacement des données ; clôture des comptes applicatifs.
""",
    (RH, "05-runbook"): """# Runbook — gestion des comptes

> **Niveau : RUNBOOK** — gestes opérationnels (via `ktayl-iam` + Authentik). *Simulation.*

- **Créer un collaborateur** : demande IAM → double approbation → l'utilisateur est créé dans Authentik et rattaché aux groupes.
- **Donner un accès** : demande d'entitlement → approbation du responsable + sécurité → provisioning.
- **Changer de poste** : ajuster les groupes `Direction …` → les rôles applicatifs (BookStack, etc.) se resynchronisent à la connexion.
- **Départ** : workflow d'offboarding → désactivation + retrait des groupes → accès coupés immédiatement.
""",
    # ───────────────────────── JURIDIQUE ─────────────────────────
    (JUR, "01-politique-policy"): """# Politique juridique

> **Niveau : POLITIQUE** · Titulaire : Direction Juridique & Compliance · Revue annuelle. *Simulation.*

## 1. Objet
Encadrer la gestion contractuelle et la maîtrise des risques juridiques de ktayl-solution : contrats,
délégations de signature, conformité réglementaire et protection des données.

## 2. Principes
1. **Tout engagement contractuel** repose sur un modèle validé ou une revue juridique.
2. **Délégation de signature** formalisée et respectée (matrice de pouvoirs).
3. **Clauses obligatoires** : protection des données (DPA/RGPD), responsabilité, droit applicable, confidentialité.
4. **Conservation & traçabilité** des contrats et des avis juridiques.

## 3. Autorité
Direction Juridique & Compliance (titulaire) ; escalade à la Direction au-delà des seuils d'engagement.

## 4. Références
Code civil / commercial · RGPD · Réglementation assurance (ACPR) · Politique de conformité. Déclinaison :
Standard, Directive, Procédure ci-contre.
""",
    (JUR, "02-standard"): """# Standard juridique

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

| # | Exigence |
|---|---|
| J1 | Utiliser un **modèle de contrat validé** ; tout écart → revue juridique |
| J2 | **Clauses minimales** présentes : DPA/RGPD, responsabilité, droit applicable, confidentialité, résiliation |
| J3 | **Signature** conforme à la matrice de délégation de pouvoirs |
| J4 | Contrat **archivé** et référencé (traçabilité, durée de conservation) |
| J5 | **Sous-traitance de données** : DPA + registre des sous-traitants (RGPD art. 28) |
""",
    (JUR, "03-directive-guideline"): """# Directive juridique

> **Niveau : DIRECTIVE** — référence quotidienne. *Simulation.*

## Revue contractuelle — seuils d'escalade
| Type / enjeu | Traitement |
|---|---|
| Contrat standard (modèle, sans écart) | Signature selon délégation, sans revue |
| Écart au modèle / clause non standard | **Revue juridique** obligatoire |
| Engagement > seuil financier défini | Escalade Direction |
| Traitement de données personnelles | **DPA** + consultation DPO |
| Litige / mise en demeure | Direction Juridique immédiatement |

## Bonnes pratiques
- Partir systématiquement du **modèle validé** ; documenter chaque écart.
- Vérifier la **matrice de pouvoirs** avant toute signature.
- Conserver l'avis juridique dans l'espace Juridique (traçabilité).
""",
    (JUR, "04-procedure"): """# Procédure — validation d'un contrat

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation.*

1. **Demande** émanant du métier (avec contexte + enjeu financier).
2. **Choix du modèle** validé ; identification des écarts éventuels.
3. **Revue juridique** si écart / clause sensible / données personnelles (DPA).
4. **Validation** des clauses obligatoires (Standard J2).
5. **Signature** selon la matrice de délégation de pouvoirs.
6. **Archivage** + référencement (traçabilité, durée de conservation).
""",
    (JUR, "05-runbook"): """# Runbook — demande juridique

> **Niveau : RUNBOOK** — gestes opérationnels. *Simulation.*

- **Soumettre une demande** : via l'espace Juridique (intranet) avec le contexte + les pièces.
- **Obtenir un modèle** : récupérer le modèle validé correspondant au besoin.
- **Escalader** : litige / mise en demeure → notifier immédiatement la Direction Juridique & Compliance.
- **Archiver** : déposer le contrat signé + l'avis dans l'espace Juridique (référence unique).
""",
}


def _token():
    ops = open(f"{HOME}/.vault-ops-token").read().strip()
    req = urllib.request.Request(f"{VAULT}/v1/secret/data/platform/bookstack")
    req.add_header("X-Vault-Token", ops)
    with urllib.request.urlopen(req, context=CTX, timeout=15) as r:
        return json.loads(r.read())["data"]["data"]["api-token"]


def _api(method, path, token, body=None, base=INTERNAL):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{base}{path}", data=data, method=method)
    req.add_header("Authorization", f"Token {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return json.loads(r.read() or "{}")


def main():
    token = _token()
    # map book slug -> {page slug -> page id}
    books, offset = {}, 0
    while True:
        page = _api("GET", f"/books?count=100&offset={offset}", token)
        for b in page.get("data", []):
            books[b["slug"]] = b["id"]
        if offset + 100 >= page.get("total", 0):
            break
        offset += 100

    page_ids = {}
    for bslug, bid in books.items():
        detail = _api("GET", f"/books/{bid}", token)
        for c in detail.get("contents", []):
            if c["type"] == "page":
                page_ids[(bslug, c["slug"])] = c["id"]

    done = 0
    for (bslug, pslug), md in CONTENT.items():
        pid = page_ids.get((bslug, pslug))
        if not pid:
            print(f"! missing page {bslug}/{pslug} — skipped")
            continue
        _api("PUT", f"/pages/{pid}", token, {"markdown": md})
        print(f"updated {bslug}/{pslug}")
        done += 1
    print(f"DONE — {done}/{len(CONTENT)} pages populated")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {e.url}: {e.read().decode()[:400]}")

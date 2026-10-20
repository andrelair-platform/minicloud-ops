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
# Wave 2 — the business-domain governance books (slugs follow BookStack's slugify of
# "<shelf> — Cadre de gouvernance"; verify once after seeding — main() warns on any mismatch).
PRICING = "pricing-portfolio-cadre-de-gouvernance"
RISKENG = "risk-engineering-cadre-de-gouvernance"
REINS = "reinsurance-captive-cadre-de-gouvernance"
FINACT = "finance-actuarial-cadre-de-gouvernance"
INTL = "international-programmes-cadre-de-gouvernance"

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

## 1bis. Segmentation marché (taille de risque)
L'appétit et le mode de traitement se déclinent par **segment de marché** — orthogonal à la branche.
Bornes indicatives (simulation) ; le segment conditionne l'autorité (DoA §3) et l'**approche tarifaire**
(voir Pricing — Directive §4).

| Segment | Profil indicatif (CA) | Prime indicative | Traitement | Autorité (DoA) | Distribution |
|---|---|---|---|---|---|
| **TPE / PME (Small)** | < 50 M€ | < 25 k€ | produits standardisés, souscription allégée/volume, RE rare | N1 | directe / courtage de proximité |
| **Middle Market (ETI)** | 50 M€ – 1,5 Md€ | 25 k€ – 250 k€ | semi-sur-mesure, RE sélective, référral ciblé | N2–N3 (four-eyes) | courtage |
| **Grandes entreprises / Corporate** | > 1,5 Md€ | > 250 k€ | sur-mesure, RE obligatoire, lignes/co-assurance fréquentes | N4 — CUO / Comité | courtage grands comptes |
| **Multinational** | groupes multi-pays | programme | master + polices locales | Comité | courtage international (voir Programmes internationaux) |

Le **Middle Market (ETI)** est le cœur de cible : assez complexe pour justifier une souscription experte,
assez standard pour rester tarifé sur base GLM + jugement borné (plancher technique maintenu).

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
    (RH, "00-charte-informatique-numerique"): """# Charte informatique & numérique

> **Annexe au règlement intérieur** · Titulaire : **RH** · Co-rédaction : **RSSI / IT** · Consultation **CSE**
> · **Signée à l'embauche** · Revue annuelle. *Document de simulation — ktayl-solution.*

## 1. Objet & portée
Définir les règles de **bon usage** du système d'information de ktayl-solution. S'applique à tout
collaborateur, intérimaire ou prestataire disposant d'un accès. La charte est une **annexe au règlement
intérieur** : son non-respect expose à des sanctions disciplinaires.

## 2. Contexte BYOD (à lire en premier)
ktayl-solution **ne gère pas d'appareils** (pas de MDM/poste fourni) : chacun utilise son **matériel
personnel**. La sécurité repose donc sur l'**identité, la session, l'application et la donnée** — pas sur
l'appareil (voir *workplace-architecture*). Principe : **appareil = non fiable → l'identité est le périmètre**.
- Accès **navigateur-first** aux applications derrière **Authentik (SSO + MFA)**.
- La donnée reste **côté serveur** ; éviter toute copie locale, surtout pour les données sensibles.

## 3. Règles d'usage
1. **Comptes & authentification** — un compte nominatif ; **MFA obligatoire** ; aucun partage d'identifiants ; ne jamais contourner le SSO.
2. **Messagerie & internet** — usage professionnel ; usage privé résiduel toléré et raisonnable ; pas d'envoi de données RESTRICTED hors des canaux autorisés.
3. **Données & classification** — respecter les classes **P0–P3** ; pas de stockage de données CONFIDENTIEL/RESTREINT sur un support personnel ; privilégier l'édition **en ligne** (Nextcloud/OnlyOffice).
4. **Sécurité de la session** — OS et navigateur à jour ; verrouillage de l'appareil ; signaler sans délai tout incident/perte/suspicion (→ Sécurité/IT, cycle DORA).
5. **Secrets** — aucun secret (mot de passe, token, clé) en clair dans un e-mail, un ticket ou un dépôt.
6. **Interdits** — contournement des contrôles, installation d'outils non autorisés sur les surfaces gérées, exfiltration de données, usage illicite.

## 4. Données personnelles & supervision (RGPD)
La journalisation et la supervision sont **proportionnées**, à finalité de **sécurité** et de conformité
(DORA), **sans surveillance individuelle permanente**. Les salariés en sont **informés** ; les droits RGPD
(accès, rectification…) s'exercent auprès du **DPO**. Les durées de conservation des journaux sont définies
par la politique de sécurité.

## 5. BYOD — responsabilités du collaborateur
Faute d'appareil géré (pas d'effacement à distance), l'employé s'engage à : verrouiller l'appareil,
maintenir l'OS à jour, ne pas conserver de données RESTREINT en local, et déclarer immédiatement la perte
d'un appareil ayant un accès actif (→ révocation de session côté identité).

## 6. Sanctions
Tout manquement peut entraîner une **sanction disciplinaire** (règlement intérieur) et, le cas échéant, des
poursuites civiles/pénales.

## 7. Gouvernance & références
Titulaire **RH** ; co-rédaction **RSSI/IT** ; **consultation CSE** ; **signature individuelle** à l'embauche ;
revue annuelle. Références : **Code du travail** (règlement intérieur) · **RGPD** · **DORA** (résilience ICT,
voir *IT / Security / DORA*) · Politique de sécurité · Politique d'accès **IAM/IGA** (`ktayl-iam`) ·
*workplace-architecture* (BYOD, identité = périmètre).

> **Acceptation :** la signature (onboarding) vaut acceptation. Elle est tracée dans le dossier RH ;
> l'accès effectif est conditionné aux approbations IAM (voir *Runbook — gestion des comptes*).
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
    # ───────────────────────── PRICING & PORTFOLIO ─────────────────────────
    (PRICING, "01-politique-policy"): """# Politique de tarification & pilotage de portefeuille

> **Niveau : POLITIQUE** · Titulaire : Chief Actuary + CUO · Approuvée par le Comité technique · Revue annuelle
> *Simulation — ktayl-solution (IARD B2B). Cadre Solvabilité II Pilier 2 + IDD/POG (value-for-money).*

## 1. Objet
Garantir que chaque prime émise est **techniquement adéquate** (couvre la sinistralité attendue + les
chargements) et que le portefeuille est piloté pour préserver la rentabilité et la solvabilité.

## 2. Principes directeurs
1. **Plancher technique** — aucune prime commerciale sous la **prime technique** sans dérogation tracée.
2. **Tarif approuvé & versionné** — aucun barème en production sans validation indépendante + sign-off actuariel ; tout barème est **immuable et versionné**.
3. **Un modèle est une boîte noire à l'entraînement, jamais au pricing** — le prix reste reconstructible indépendamment de tout modèle/IA.
4. **Reproductibilité** — toute cotation est rejouable à l'identique (manifeste de cotation).
5. **Pilotage** — adéquation tarifaire, dérive et ratio réel/attendu (A/E) suivis en continu.
6. **POG/value-for-money** — la tarification respecte le marché cible produit (IDD).

## 3. Références
Solvabilité II (provisions, coût du capital) · IDD art. 25 (POG) · ACPR · ADR-009 (évolution tarifaire :
modèle de perte → tarif approuvé → moteur déterministe). Déclinaison : Standard · Directive · complément exécutable.
""",
    (PRICING, "02-standard"): """# Standard de tarification & gouvernance des modèles

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

## Exigences minimales
| # | Exigence | Contrôle |
|---|---|---|
| P1 | Prime commerciale **≥ prime technique** (sinistralité + frais + coût du capital + marge) | Contrôle de plancher |
| P2 | Tout barème (`rate_table`) est **versionné, immuable, daté** (date d'effet) | ADR-004 |
| P3 | **Enregistré ≠ approuvé** — validation indépendante (out-of-time, calibration, stabilité, biais) **puis** sign-off actuariel avant publication | Registre MLflow + gate actuariel |
| P4 | Arrondis, bandes d'autorité et règles commerciales **encodés dans le tarif approuvé** | Artefact tarifaire |
| P5 | **Manifeste de cotation** persisté (versions modèle/tarif/règles + faits + preuves + décomposition) | Journal append-only |
| P6 | Suivi **A/E** (réel vs attendu) par segment + dérive de facteurs | Tableau de bord de pilotage |

## Seuils de référence (simulation)
- Ratio de sinistralité cible (loss ratio) de pilotage : **≤ 60 %** technique.
- Dérogation sous plancher technique : **référral CUO** obligatoire + justification écrite.
- Révision du barème : au moins **annuelle**, ou sur alerte A/E.
""",
    (PRICING, "03-directive-guideline"): """# Directive de tarification

> **Niveau : DIRECTIVE** — la référence métier. Un sous-ensemble est **exécuté** par `ktayl-underwriting`
> (moteur de tarification) — voir *Complément exécutable*. *Simulation.*

## 1. Construction de la prime (de la prime pure à la prime quittancée)
```
COÛT DU SINISTRE ATTENDU  (modèle de perte GLM fréquence × sévérité)
= PRIME PURE
  + chargement de frais (acquisition + gestion)
  + marge de risque / coût du capital (Solvabilité II)
  + provision CAT (modélisée séparément)
= INDICATION TECHNIQUE
  × ajustement commercial (borné, tracé, soumis à l'autorité)
= PRIME COMMERCIALE
  + taxes (TCA/IPT selon territoire) + frais
= PRIME QUITTANCÉE
```

## 2. Bandes de chargement / remise (exemples, simulation)
| Facteur | Effet | Gate |
|---|---|---|
| Occupation (tarif) | ×relativité GLM par classe | Barème |
| TIV élevé (> 5 M€) | majoration | Barème |
| Protection incendie (sprinkler) | remise | Rapport Risk Engineering |

## 3. Dérogations & référral
Prime < plancher technique → **référral CUO**. Ajustement commercial au-delà de la bande → autorité supérieure.
La **réassurance n'est pas une remise par risque** : elle alimente la provision CAT + le coût du capital au niveau **portefeuille** (voir Réassurance & Captive).

## 4. Approche tarifaire par segment de marché
La **méthode** de tarification dépend du segment (voir Underwriting — Directive §1bis) ; le **plancher
technique** et le manifeste s'appliquent dans tous les cas.

| Segment | Méthode | Jugement souscripteur |
|---|---|---|
| **TPE / PME (Small)** | tarif **portefeuille / GLM algorithmique** (barème pur) | nul ou minime |
| **Middle Market (ETI)** | **GLM + jugement borné** (ajustement commercial dans la bande, tracé) | encadré, dans la DoA |
| **Grandes entreprises / Corporate** | **tarification individuelle** (expérience / exposition), RE obligatoire | fort, souvent référé CUO |
| **Multinational** | allocation par territoire + **taxes/IPT** | via Programmes internationaux |

Quel que soit le segment, une prime sous le **plancher technique** exige un référral CUO ; l'ajustement
commercial reste **borné et tracé** (jamais de dérogation silencieuse).

➡️ **Exécution :** relativités, plancher et manifeste appliqués par `ktayl-underwriting` — voir *Complément exécutable*.
""",
    (PRICING, "04-procedure"): """# Procédure — publier un nouveau barème (tarif)

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation. Cf. ADR-009.*

1. **Préparer les données** : exposition, sinistres, termes de police, mise à niveau inflation, qualité des données.
2. **Entraîner le modèle** : GLM fréquence/sévérité ; diagnostics (lift, Gini, A/E par facteur).
3. **Validation indépendante** : hors-échantillon, calibration, stabilité, **contrôle de biais/proxy**, performance par segment.
4. **Sign-off actuariel** : revue + approbation du tarif retenu (gate nommé, consigné à la RACI).
5. **Publication immuable** : coefficients **+ règles + arrondis + dates d'effet + autorité** = un artefact versionné (MLflow + table tarifaire).
6. **Déploiement contrôlé** : promotion GitOps, tests de régression, rollback ; champion/challenger.
7. **Suivi en production** : A/E par segment, dérive, taux de référral/dérogation.

> Une dérogation de cotation suit la **Procédure de souscription** (référral CUO).
""",
    (PRICING, "05-runbook"): """# Runbook — opérations tarifaires

> **Niveau : RUNBOOK** — gestes opérationnels. *Simulation.*

- **Publier un barème** : promouvoir la nouvelle version du tarif approuvé (PR GitOps gated) → le moteur charge la version.
- **Rollback** : repointer sur la version précédente (immuable) ; aucune cotation historique n'est altérée (manifeste).
- **Champion/challenger** : router une part du trafic vers le barème candidat ; comparer l'A/E avant bascule.
- **Alerte A/E / dérive** : si le ratio réel/attendu sort de la bande → geler les évolutions à risque, ouvrir une revue actuarielle.
- **Rejouer une cotation** : récupérer le manifeste (versions modèle/tarif/règles + faits) → recalcul à l'identique.
""",
    (PRICING, "00-complement-executable-policy-as-code"): """# Complément exécutable (policy-as-code)

La **Directive de tarification** est en partie **exécutée** par `ktayl-underwriting` — l'intranet reste la
**source de vérité**, le moteur applique les règles critiques de façon déterministe et reproductible.

## Règles appliquées en ligne
| Règle (Directive) | Appliquée par |
|---|---|
| Relativités / barème approuvé (`rate_table`, versionné) | Moteur de tarification `rate()` |
| Plancher technique | Contrôle tarifaire (référral CUO si sous plancher) |
| Décomposition explicable (ligne à ligne) | `QuoteBreakdown` (trace legible) |
| Reproductibilité | **Manifeste de cotation** (versions + faits + preuves) |

**Architecture (ADR-009) :** modèle de perte (GLM, hors-ligne, MLflow — jamais appelé au pricing) →
**tarif approuvé** (artefact gouverné, immuable) → **moteur déterministe** (le seam pur `rate()`).
Un modèle est une boîte noire à l'entraînement, **jamais au pricing**. SHAP = validation du modèle,
**pas** l'arithmétique de la prime.
""",
    # ───────────────────────── RISK ENGINEERING ─────────────────────────
    (RISKENG, "01-politique-policy"): """# Politique d'ingénierie des risques

> **Niveau : POLITIQUE** · Titulaire : Responsable Risk Engineering · Revue annuelle. *Simulation.*

## 1. Objet
Évaluer et améliorer la **qualité des risques** souscrits (prévention, protection) et fournir à la
souscription et à la tarification une information de risque fiable et traçable.

## 2. Principes directeurs
1. **Évaluation sur site** — les risques significatifs font l'objet d'une visite + évaluation **COPE** (Construction, Occupation, Protection, Exposition).
2. **Recommandations priorisées** — chaque constat donne lieu à une recommandation classée par criticité + délai.
3. **Boucle avec la souscription** — la note de qualité de risque alimente l'appétit et la tarification (ex. remise protection).
4. **Prévention CAT** — exposition catastrophe caractérisée (zone, cumul) et transmise à la réassurance.
5. **Traçabilité** — visites, constats et suivi de remédiation documentés.

## 3. Références
Solvabilité II (gestion des risques) · normes de prévention incendie (ex. sprinkler) · Politique de souscription · Politique de réassurance.
""",
    (RISKENG, "02-standard"): """# Standard d'ingénierie des risques

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

| # | Exigence | Contrôle |
|---|---|---|
| RE1 | Visite de site obligatoire au-dessus d'un seuil de **TIV / occupation à risque** | Déclencheur de visite |
| RE2 | Évaluation **COPE** documentée + note de qualité de risque | Fiche d'évaluation |
| RE3 | Recommandations classées **critique / majeure / mineure** avec délai | Registre de recommandations |
| RE4 | **Ré-inspection** selon la criticité (critique ≤ 12 mois) | Cadence de ré-inspection |
| RE5 | Protections minimales vérifiées (détection/extinction, compartimentage) | Check-list de protection |
| RE6 | Exposition **CAT** (zone, cumul) renseignée pour la souscription/réassurance | Donnée de cumul |

## Seuils de référence (simulation)
- Visite obligatoire : TIV > **10 M€** ou occupation hors-standard.
- Recommandation critique non levée → **référral souscription** (impact appétit/tarif).
""",
    (RISKENG, "03-directive-guideline"): """# Directive d'ingénierie des risques

> **Niveau : DIRECTIVE** — la référence métier. *Simulation.*

## 1. Évaluation COPE
- **Construction** : matériaux, résistance au feu, compartimentage.
- **Occupation** : activité, process, charge calorifique, stockage.
- **Protection** : sprinklers, détection, moyens de secours, organisation.
- **Exposition** : voisinage, zone CAT (inondation, tempête, sismique).

## 2. Notation & impact tarifaire
La note de qualité de risque et les protections confirmées **alimentent la tarification** : ex. une
protection sprinkler vérifiée ouvre droit à la **remise de protection** du barème (voir Pricing — Directive).
Une recommandation critique ouverte peut dégrader l'appétit ou imposer une surprime.

## 3. Suivi des recommandations
Chaque recommandation est suivie jusqu'à clôture ; les critiques non levées remontent à la souscription.
""",
    (RISKENG, "04-procedure"): """# Procédure — visite de risque

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation.*

1. **Déclenchement** : soumission au-dessus du seuil TIV/occupation → planifier une visite.
2. **Visite de site** : évaluation COPE + relevé des protections + exposition CAT.
3. **Notation** : attribuer la note de qualité de risque.
4. **Recommandations** : émettre + classer (critique/majeure/mineure) + délai.
5. **Transmission** : fiche + note + recommandations → souscription/tarification (et réassurance si CAT).
6. **Suivi** : tracer la remédiation ; ré-inspecter selon la criticité.
""",
    (RISKENG, "05-runbook"): """# Runbook — ingénierie des risques

> **Niveau : RUNBOOK** — gestes opérationnels. *Simulation.*

- **Enregistrer une visite** : créer la fiche COPE + la note de qualité de risque.
- **Émettre une recommandation** : criticité + délai + responsable côté assuré.
- **Escalader** : recommandation critique non levée → notifier le souscripteur (impact appétit/tarif).
- **Clôturer** : enregistrer la preuve de remédiation + planifier la ré-inspection.
""",
    # ───────────────────────── REINSURANCE & CAPTIVE ─────────────────────────
    (REINS, "01-politique-policy"): """# Politique de réassurance & captive

> **Niveau : POLITIQUE** · Titulaire : Direction Réassurance + CFO · Approuvée par le Conseil · Revue annuelle. *Simulation.*

## 1. Objet
Protéger le **capital** et lisser la **volatilité** des résultats en transférant une partie des risques,
dans le respect de l'appétit et des exigences de solvabilité.

## 2. Principes directeurs
1. **Programme cohérent** — traités proportionnels / non-proportionnels dimensionnés sur l'exposition et l'appétit.
2. **Rétention maîtrisée** — rétention nette par risque / par événement dans les limites fixées.
3. **Sécurité des contreparties** — réassureurs au-dessus d'une notation minimale ; diversification.
4. **CAT** — couverture catastrophe dimensionnée sur les cumuls (lien Risk Engineering).
5. **Captive** — utilisée dans un cadre gouverné (collatéral, substance, conformité).
6. **Effet tarifaire au niveau portefeuille** — la réassurance informe la **provision CAT** et le **coût du capital** du tarif, **non** une remise par risque (cf. Pricing / ADR-009).

## 3. Références
Solvabilité II (atténuation du risque / SCR) · ORSA · Politique de souscription · Politique financière.
""",
    (REINS, "02-standard"): """# Standard de réassurance

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

| # | Exigence | Contrôle |
|---|---|---|
| R1 | Notation minimale réassureur : **A-** (sinon dérogation + collatéral) | Contrôle de sécurité |
| R2 | Cession maximale par contrepartie (concentration) | Suivi des cumuls de cession |
| R3 | Rétention nette : par risque **≤ 2 M€**, par événement selon le programme CAT | Contrôle de rétention |
| R4 | Facultative obligatoire **au-delà de la rétention** / hors traité | Déclencheur de placement |
| R5 | **Bordereaux** (primes cédées / sinistres) produits trimestriellement | Cadence bordereaux |
| R6 | Captive : collatéral + reporting conformes | Contrôle captive |
""",
    (REINS, "03-directive-guideline"): """# Directive de réassurance

> **Niveau : DIRECTIVE** — la référence métier. *Simulation.*

## 1. Traité vs facultative
- **Traité** (automatique) : couvre un portefeuille défini ; proportionnel (quote-part/excédent) ou non-proportionnel (XS).
- **Facultative** : risque individuel au-delà de la rétention/du traité, ou hors-appétit du traité.

## 2. Cessions & recouvrements
La cession suit la structure du programme ; les **recouvrements** sont comptabilisés nets des primes cédées
et du collatéral. Primes cédées, pertes retenues, recouvrements et provisions CAT sont traités de façon
**cohérente** (pas de double-compte).

## 3. Lien avec la tarification
La réassurance agit au niveau **portefeuille/capital** : elle dimensionne la **provision CAT** et le
**coût du capital** repris dans l'indication technique — **jamais** une remise soustraite d'une prime individuelle.
""",
    (REINS, "04-procedure"): """# Procédure — placement & recouvrement

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation.*

1. **Détection** : risque au-dessus de la rétention / hors traité → besoin de facultative.
2. **Placement facultatif** : sélection de réassureurs (notation), cotation, confirmation de couverture.
3. **Enregistrement de la cession** : parts, conditions, référence.
4. **Bordereaux** : production trimestrielle (primes cédées / sinistres).
5. **Recouvrement** : sur sinistre dépassant la rétention → déclarer + recouvrer auprès des réassureurs.
6. **Renouvellement** : revue annuelle du programme (exposition, appétit, sécurité).
""",
    (REINS, "05-runbook"): """# Runbook — réassurance

> **Niveau : RUNBOOK** — gestes opérationnels. *Simulation.*

- **Enregistrer une cession** : parts + conditions + contrepartie (contrôle de notation).
- **Déclencher un recouvrement** : sinistre > rétention → ouvrir le recouvrement + suivre l'encaissement.
- **Produire un bordereau** : extraire primes cédées / sinistres de la période.
- **Renouveler un traité** : préparer l'exposition + les cumuls ; négocier ; mettre à jour les rétentions/limites.
""",
    # ───────────────────────── FINANCE & ACTUARIAL ─────────────────────────
    (FINACT, "01-politique-policy"): """# Politique finance & actuariat

> **Niveau : POLITIQUE** · Titulaire : CFO + Chief Actuary · Approuvée par le Conseil · Revue annuelle. *Simulation.*

## 1. Objet
Assurer l'**adéquation des provisions techniques**, la solidité du capital et la fiabilité de l'information
financière (Solvabilité II + IFRS 17), au service d'une tarification et d'un pilotage sains.

## 2. Principes directeurs
1. **Provisions adéquates** — meilleure estimation (best estimate) + **marge de risque**, revues périodiquement.
2. **Capital** — couverture du **SCR** au-dessus du seuil d'appétit ; ORSA annuel.
3. **IFRS 17** — mesure des contrats selon le modèle applicable (PAA / GMM).
4. **Fonction actuarielle** — opinion indépendante sur provisions, tarification et réassurance.
5. **Investissement** — prudence (personne prudente), adossement actif/passif.
6. **Qualité des données** — données alimentant les provisions et les modèles contrôlées.

## 3. Références
Solvabilité II (art. 48 fonction actuarielle ; provisions techniques ; SCR/ORSA) · IFRS 17 · ACPR.
""",
    (FINACT, "02-standard"): """# Standard finance & actuariat

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

| # | Exigence | Contrôle |
|---|---|---|
| F1 | Provisions = **best estimate + marge de risque**, méthodologie documentée | Revue actuarielle |
| F2 | Revue des provisions au moins **trimestrielle** + à la clôture | Cadence de revue |
| F3 | Couverture **SCR ≥ seuil d'appétit** (ex. 150 %) | Suivi du ratio de solvabilité |
| F4 | **Opinion de la fonction actuarielle** sur provisions / tarif / réassurance | Rapport annuel |
| F5 | Qualité des données (exhaustivité, exactitude, pertinence) attestée | Contrôle qualité données |
| F6 | Mesure **IFRS 17** cohérente (modèle, frontières de contrat) | Clôture IFRS 17 |
""",
    (FINACT, "03-directive-guideline"): """# Directive finance & actuariat

> **Niveau : DIRECTIVE** — la référence métier. *Simulation.*

## 1. Provisionnement
Estimer la charge ultime par méthodes actuarielles (ex. Chain-Ladder / Bornhuetter-Ferguson), dériver la
**meilleure estimation** + la **marge de risque** (coût du capital).

## 2. Lien avec la tarification
Le **coût du capital** et la sinistralité attendue nourrissent l'**indication technique** du pricing
(voir Pricing — Directive). La fonction actuarielle émet un avis sur l'adéquation du tarif.

## 3. IFRS 17 & reporting
Classer les contrats, choisir le modèle de mesure (PAA pour les contrats courts IARD), produire les états.
Réconcilier vue **statutaire (Solvabilité II)** et **IFRS 17**.
""",
    (FINACT, "04-procedure"): """# Procédure — clôture & revue des provisions

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation.*

1. **Arrêté des données** : sinistres, primes, exposition de la période (qualité contrôlée).
2. **Calcul des provisions** : best estimate + marge de risque par branche.
3. **Revue actuarielle** : analyse des écarts (réel vs attendu), justification.
4. **SCR / fonds propres** : produire le ratio de solvabilité.
5. **IFRS 17** : mesure + états financiers ; réconciliation statutaire/IFRS.
6. **Opinion & reporting** : rapport de la fonction actuarielle ; cycle ORSA annuel.
""",
    (FINACT, "05-runbook"): """# Runbook — finance & actuariat

> **Niveau : RUNBOOK** — gestes opérationnels. *Simulation.*

- **Lancer le calcul de provisionnement** : exécuter la méthode sur les triangles de la période.
- **Produire le SCR / fonds propres** : générer le ratio de solvabilité + le tableau de couverture.
- **Clôturer** : états IFRS 17 + réconciliation statutaire.
- **Escalader** : ratio de solvabilité sous le seuil d'appétit → alerte CFO + Conseil (ORSA).
""",
    # ───────────────────────── INTERNATIONAL PROGRAMMES ─────────────────────────
    (INTL, "01-politique-policy"): """# Politique — programmes internationaux

> **Niveau : POLITIQUE** · Titulaire : Direction Programmes Internationaux · Revue annuelle. *Simulation.*

## 1. Objet
Gouverner les **programmes master + polices locales** pour les clients multinationaux, en conformité avec
les règles d'assurance **admise / non-admise**, la fiscalité locale et les sanctions.

## 2. Principes directeurs
1. **Conformité territoriale** — polices locales **admises** là où le non-admis est interdit ; fronting agréé.
2. **DIC/DIL** — la master comble les écarts de garantie/limite des polices locales (Difference in Conditions/Limits).
3. **Allocation de prime** — répartition master/locales documentée + **taxes (TCA/IPT) par territoire**.
4. **Sécurité du fronting** — partenaires locaux sélectionnés (notation, agrément).
5. **Cash-before-cover** — encaissement avant prise d'effet là où requis.
6. **Sanctions** — filtrage des territoires/parties.

## 3. Références
Règles admis/non-admis par pays · fiscalité assurance (IPT) · IDD · Politique LCB-FT & sanctions · Politique de souscription.
""",
    (INTL, "02-standard"): """# Standard — programmes internationaux

> **Niveau : STANDARD** — exigences obligatoires. *Simulation.*

| # | Exigence | Contrôle |
|---|---|---|
| I1 | Police **locale admise** émise là où le non-admis est interdit | Contrôle de conformité pays |
| I2 | Partenaire de **fronting** agréé + notation minimale | Contrôle de sécurité |
| I3 | **Taxes / IPT** calculées + réglées par territoire | Contrôle fiscal |
| I4 | **Cash-before-cover** respecté là où requis | Contrôle d'encaissement |
| I5 | Allocation de prime master/locales **documentée + cohérente** | Contrôle d'allocation |
| I6 | Filtrage **sanctions** des territoires/parties | Écran de conformité |
""",
    (INTL, "03-directive-guideline"): """# Directive — programmes internationaux

> **Niveau : DIRECTIVE** — la référence métier. *Simulation.*

## 1. Structurer un programme
Définir la **police master** (groupe) + les **polices locales** (filiales) ; préciser le **fronting** et les **DIC/DIL**.

## 2. Allocation de prime & taxes
Allouer la prime entre master et locales selon l'exposition par territoire ; calculer les **taxes/IPT**
locales. La **prime quittancée** locale intègre l'IPT applicable (cf. Pricing — Directive, étape taxes/fees).

## 3. Conformité
Vérifier admis/non-admis par pays, les obligations fiscales, le cash-before-cover et les sanctions avant émission locale.
""",
    (INTL, "04-procedure"): """# Procédure — mise en place d'un programme & émission locale

> **Niveau : PROCÉDURE** — pas-à-pas. *Simulation.*

1. **Cadrer le programme** : périmètre pays, structure master/locales, fronting, DIC/DIL.
2. **Vérifier la conformité** : admis/non-admis, fiscalité (IPT), sanctions par territoire.
3. **Allouer la prime** : répartition master/locales + taxes locales.
4. **Émettre la master** + instruire les **polices locales** (partenaires de fronting).
5. **Encaisser** : cash-before-cover là où requis.
6. **Réconcilier** : flux cross-border (primes, taxes, sinistres) suivis et rapprochés.
""",
    (INTL, "05-runbook"): """# Runbook — programmes internationaux

> **Niveau : RUNBOOK** — gestes opérationnels. *Simulation.*

- **Enregistrer une police locale** : territoire + partenaire de fronting + conditions (DIC/DIL vs master).
- **Calculer l'allocation + l'IPT** : répartir la prime par territoire + appliquer la taxe locale.
- **Contrôler la conformité** : admis/non-admis + sanctions + cash-before-cover avant émission.
- **Réconcilier** : rapprocher les flux cross-border (primes cédées, taxes, sinistres) par période.
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

#!/usr/bin/env python3
"""
Map Authentik groups -> BookStack roles and gate the Phase-1 pilot spaces (idempotent).

BookStack OIDC assigns a user the role whose display_name == an incoming group name. So this creates
roles NAMED EXACTLY like the Authentik groups:
  - "authentik Admins"              -> full admin perms (so akadmin administers BookStack via SSO)
  - "Direction RH"                  -> contributor, owns the RH shelf/book
  - "Direction Juridique & Compliance" -> contributor, owns Juridique
  - "Direction Souscription"        -> contributor, owns Underwriting
Then on each pilot's governance book it sets content-permissions: the owning Direction role = full CRUD,
fallback = view (all staff read, only the owning Direction edits; Admins bypass). Books cascade to pages.

RUN ON THE CONTROLLER. Reads the API token from Vault `platform/bookstack` (ops token) over the minicloud CA.
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
CTX = ssl.create_default_context(cafile=f"{HOME}/minicloud-ca.crt")

# shelf name (as seeded) -> owning Authentik group == BookStack role name
PILOTS = {
    "RH": "Direction RH",
    "Juridique": "Direction Juridique & Compliance",
    "Underwriting": "Direction Souscription",
    "IT / Security / DORA": "Direction IT / SI",
}
ADMIN_ROLE = "authentik Admins"  # owner's group -> admin-equivalent role

CONTRIBUTOR_PERMS = [
    "bookshelf-view-all", "book-view-all", "chapter-view-all", "page-view-all",
    "book-create-own", "chapter-create-own", "page-create-own",
    "book-update-own", "chapter-update-own", "page-update-own",
    "book-delete-own", "chapter-delete-own", "page-delete-own",
    "image-create-own", "image-update-own", "image-delete-own",
    "attachment-create-own", "attachment-update-own", "attachment-delete-own",
    "comment-create-own", "comment-update-own", "comment-delete-own",
    "content-export", "revision-view-all", "receive-notifications",
]


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


def all_by_name(kind, token):
    out, offset = {}, 0
    while True:
        page = api("GET", f"/{kind}?count=100&offset={offset}", token=token)
        key = "display_name" if kind == "roles" else "name"
        for it in page.get("data", []):
            out[it[key]] = it["id"]
        if offset + 100 >= page.get("total", 0):
            break
        offset += 100
    return out


def main():
    token = vault_api_token()
    roles = all_by_name("roles", token)
    shelves = all_by_name("shelves", token)
    books = all_by_name("books", token)

    # admin perm vocabulary = whatever the built-in Admin role has
    admin_perms = api("GET", f"/roles/{roles['Admin']}", token=token)["permissions"]

    # 1. ensure roles (name == Authentik group)
    def ensure_role(name, perms, desc):
        if name in roles:
            print(f"= role {name}")
            return roles[name]
        rid = api("POST", "/roles", {"display_name": name, "description": desc, "permissions": perms}, token)["id"]
        roles[name] = rid
        print(f"+ role {name}")
        return rid

    ensure_role(ADMIN_ROLE, admin_perms, "BookStack admins (synced from Authentik 'authentik Admins')")
    for shelf, group in PILOTS.items():
        ensure_role(group, CONTRIBUTOR_PERMS, f"Owns the {shelf} governance space")

    # 2. gate each pilot book (+ shelf): owning Direction role = CRUD; fallback = view for all
    for shelf, group in PILOTS.items():
        role_id = roles[group]
        book_name = f"{shelf} — Cadre de gouvernance"
        gate = dict(
            fallback_permissions=dict(inheriting=False, view=True, create=False, update=False, delete=False),
            role_permissions=[dict(role_id=role_id, view=True, create=True, update=True, delete=True)],
        )
        if book_name in books:
            api("PUT", f"/content-permissions/book/{books[book_name]}", gate, token)
            print(f"gated book  {book_name} -> {group} (CRUD), all-staff view")
        # shelf: owning role view+update (rename/describe), others view
        shelf_gate = dict(
            fallback_permissions=dict(inheriting=False, view=True, create=False, update=False, delete=False),
            role_permissions=[dict(role_id=role_id, view=True, create=True, update=True, delete=False)],
        )
        api("PUT", f"/content-permissions/bookshelf/{shelves[shelf]}", shelf_gate, token)
        print(f"gated shelf {shelf} -> {group}")

    print("DONE")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {e.url}: {e.read().decode()[:400]}")

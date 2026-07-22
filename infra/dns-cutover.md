# DNS cutover runbook — delegate airportbar.app + tylerdorland.com to Cloud DNS

This runbook takes the two domains from hand-typed Squarespace records to
Terraform-managed Cloud DNS zones (`infra/dns.tf`) **without downtime**. It is a
procedure, not a script: the nameserver switch (step 5) is a **one-time manual
action Tyler performs at the registrar**. No agent and no CI job repoints
nameservers.

**Golden rule:** the zones and every record must exist and be verified to serve
*identical answers* **before** any nameserver is switched. Create → verify →
switch. Never switch first.

---

## 0. Live records captured (source of truth for replication)

Captured 2026-07-21 by `dig` against the **authoritative** nameservers (not a
cache). `infra/dns.tf` mirrors exactly this, TTLs included.

### airportbar.app — currently on Squarespace NS (`nse{1..4}.squarespacedns.com`)

| Name | Type | TTL | Value(s) |
|---|---|---|---|
| `airportbar.app.` | A | 14400 | 216.239.32.21, .34.21, .36.21, .38.21 |
| `airportbar.app.` | AAAA | 14400 | 2001:4860:4802:{32,34,36,38}::15 |
| `airportbar.app.` | TXT | 14400 | `google-site-verification=Xhx-dwQlBFmQ5rZ-x4dX5LwIod2ZNVs1fvc-nMAIsbg`; `v=spf1 -all` |
| `www.airportbar.app.` | CNAME | 14400 | ghs.googlehosted.com. |
| `_dmarc.airportbar.app.` | TXT | 14400 | `v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s` |

No MX (domain sends no mail). No CAA.

### tylerdorland.com — currently on legacy Cloud DNS NS (`ns-cloud-c{1..4}.googledomains.com`)

These nameservers belong to a **Google-Domains-era zone in a Google-owned
project**, not to any zone in `team-higgs-platform` (verified live 2026-07-21:
that project has **zero** managed zones). They are therefore **not importable**
here — the new Terraform zone gets a **different** `ns-cloud-XX` set, so this
domain still needs a registrar NS repoint at cutover.

| Name | Type | TTL | Value(s) |
|---|---|---|---|
| `tylerdorland.com.` | A | 14400 | 198.185.159.145 (Squarespace site) |
| `tylerdorland.com.` | TXT | 3600 | `google-site-verification=EU9g8d00Sv9XU4gVZCBg_0WjocS_w_frt5DpIwDT5WY`; `v=spf1 include:_spf.google.com ~all` |
| `tylerdorland.com.` | MX | 3600 | 1 aspmx.l.google.com.; 5 alt1; 5 alt2; 10 alt3; 10 alt4 (Google Workspace) |
| `www.tylerdorland.com.` | CNAME | 14400 | ext-sq.squarespace.com. |
| `higgs.tylerdorland.com.` | CNAME | 14400 | ghs.googlehosted.com. |

No CAA. No `_dmarc` today (a `p=none` DMARC record for the mail domain is a
sensible follow-up but is **not** in scope here — replication only).

**Discovery gap:** authoritative AXFR (zone transfer) was refused on both
domains, so this table is the set of records reachable by name query, not a
guaranteed-complete zone dump. Before switching NS, reconcile against the source
of truth for each domain and confirm **no records exist beyond this table**:
- **airportbar.app** — the Squarespace DNS panel (its records are hand-typed
  there today).
- **tylerdorland.com** — the legacy Google-owned Cloud DNS zone is not readable
  from `team-higgs-platform`, so reconcile against its **live authoritative
  answers** (query `ns-cloud-c1.googledomains.com` directly for every record
  type you can enumerate: A, AAAA, TXT, MX, NS, CAA, and the known `www`/`higgs`
  subdomains).

If either source shows a record not in the table above, add it to `infra/dns.tf`
**before** cutover.

---

## 1. Both zones are CREATES — there is nothing to import

Verified live on 2026-07-21 (authenticated as `tyler@tylerdorland.com`):

```sh
gcloud dns managed-zones list --project=team-higgs-platform
# -> zero zones
```

`team-higgs-platform` holds **no** managed zones. `infra/dns.tf` therefore
**creates** both zones from scratch; there is **no import path** for either
domain.

- **airportbar.app** is on Squarespace nameservers today and has no Cloud DNS
  zone. Terraform creates it fresh. Needs the step-5 registrar NS switch.
- **tylerdorland.com** currently answers from `ns-cloud-c{1..4}.googledomains.com`,
  but those belong to a **Google-Domains-era zone in a Google-owned project** —
  not importable into `team-higgs-platform`. Terraform creates a fresh zone here
  with a **different** `ns-cloud-XX` nameserver set. Because that set differs from
  what the registrar points at today, **tylerdorland.com also needs the step-5
  registrar NS switch — it is NOT zero-touch.**

**Both domains require a registrar NS repoint at cutover (step 5).** Neither is a
records-only adoption.

The apply also enables the Cloud DNS API declaratively
(`google_project_service.dns`, `dns.googleapis.com`), so a clean apply on a fresh
project is self-contained. The API was enabled by hand on 2026-07-21 as a
prerequisite; on an already-enabled project the plan simply records ownership and
makes no functional change.

---

## 2. Apply (creates zones + records; changes nothing that resolves yet)

Applying `infra/dns.tf` only populates Cloud DNS. Until the registrar delegates
to these nameservers, production traffic still flows through the old
authoritative servers — **apply is zero-impact**.

Apply happens on the standard path: **merge → CI apply via WIF** (pairs with the
Terraform-in-CI task #23). If that CI apply path is not yet live, this is a
supervised local `terraform apply` by Tyler under his own gcloud ADC (same
bootstrap caveat as the WIF import in `infra/README.md`). Agents do not apply.

Confirm the applied plan **creates** the two zones + their record sets, **enables
the Cloud DNS API** (`google_project_service.dns`), and shows **no destroys** and
**no changes to any non-DNS resource** (no `plantlog-*`, no Cloud Run, no SQL).

---

## 3. Read the new zone nameservers

```sh
cd infra && terraform output dns_zone_nameservers
```

Record both 4-nameserver sets — **both are needed at the registrar in step 5**,
because both zones are fresh creates (step 1). `airportbar.app`'s set replaces its
Squarespace nameservers; `tylerdorland.com`'s set replaces the legacy
`ns-cloud-c{1..4}.googledomains.com` set.

---

## 4. Verify replication — the gate before any NS switch

Query the **new** Cloud DNS nameservers directly (bypassing delegation) and
confirm they answer identically to the **current** authoritative servers. Do this
per domain, per record. `NEW_NS` = one nameserver from step 3; `OLD_NS` =
`nse1.squarespacedns.com` for airportbar, `ns-cloud-c1.googledomains.com` for
tylerdorland.

```sh
for rr in "airportbar.app A" "airportbar.app AAAA" "airportbar.app TXT" \
          "www.airportbar.app CNAME" "_dmarc.airportbar.app TXT"; do
  set -- $rr
  echo "== $1 $2 =="
  diff <(dig +norecurse +noall +answer @OLD_NS "$1" "$2" | sort) \
       <(dig +norecurse +noall +answer @NEW_NS "$1" "$2" | sort) \
    && echo OK || echo "MISMATCH — STOP"
done
```

Repeat for tylerdorland.com (`A`, `TXT`, `MX` at apex; `www` and `higgs` CNAMEs).
Ignore TTL-column differences only if you deliberately changed a TTL; this module
did not, so answers should match on value **and** TTL. **Any MISMATCH halts the
cutover** — fix `infra/dns.tf`, re-apply, re-verify.

---

## 5. Switch nameservers at the registrar — ONE-TIME, MANUAL, TYLER ONLY

Only after step 4 is all-OK. Do the domains **one at a time**; verify the first
recovers before touching the second.

The domains are **registered at Squarespace** (post Google-Domains migration).
The nameserver setting is in the Squarespace **domain/registrar** panel, not the
per-record DNS editor.

**airportbar.app:**
1. Squarespace → Domains → `airportbar.app` → Nameservers → **Use custom
   nameservers**.
2. Replace the four `nse{1..4}.squarespacedns.com` entries with the four
   `airportbar.app` nameservers from step 3.
3. Save.

**tylerdorland.com:** required (step 1 confirmed this is a fresh zone with a new
nameserver set — not a records-only adoption). In the Squarespace registrar panel,
replace the current `ns-cloud-c{1..4}.googledomains.com` entries with the new
`tylerdorland.com` nameserver set from step 3. This is the higher-consequence
switch — Google Workspace **mail** rides on this domain — so verify airportbar.app
fully recovered first, then do this one and watch the MX check in step 6 closely.

Registrar NS changes propagate on the parent TLD's delegation TTL (typically
minutes to a few hours; `.app` and `.com` are fast). Delegation is cached at the
parent, independent of the in-zone TTLs above.

---

## 6. Post-switch verification

```sh
dig +short NS airportbar.app        # -> the Cloud DNS set from step 3
dig +short A  airportbar.app        # -> 216.239.{32,34,36,38}.21
curl -sSI https://airportbar.app/   # -> 200 / healthy
dig +short NS tylerdorland.com      # -> Cloud DNS set
curl -sSI https://tylerdorland.com/ # -> Squarespace site still serving
dig +short MX tylerdorland.com      # -> Workspace MX intact (mail unbroken)
dig +short higgs.tylerdorland.com   # -> ghs.googlehosted.com. (bridge intact)
```

Mail (tylerdorland.com MX) is the highest-consequence record — confirm it
resolves before considering the cutover done.

---

## 7. Rollback

Because the switch is a registrar NS change, rollback is the reverse NS change —
fast and total. Restore the **old** nameservers at the registrar:

- **airportbar.app** → `nse1.squarespacedns.com`, `nse2.squarespacedns.com`,
  `nse3.squarespacedns.com`, `nse4.squarespacedns.com`.
- **tylerdorland.com** → `ns-cloud-c1.googledomains.com`,
  `ns-cloud-c2.googledomains.com`, `ns-cloud-c3.googledomains.com`,
  `ns-cloud-c4.googledomains.com`.

The old authoritative zones are untouched by this work and keep serving the same
records, so reverting NS restores the prior state. Do not delete the old
Squarespace records until the new zones have served correctly for a few days.

Do not `terraform destroy` the new zones as a rollback step during an incident —
reverting NS is enough and is instant; zone teardown is a later, deliberate
cleanup once the cutover is confirmed stable.

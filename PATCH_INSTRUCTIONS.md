# SRJ AI Audit Platform — Patch v0.2.0 Deployment Instructions

**Purpose:** Add Django ORM coverage for every remaining table in the database — engagements, respondents, documents, questions, responses, scores, reports, events, discount_credits, refund_requests — plus full Django admin registration. After this patch, the entire data model is browsable and queryable through the Django admin and ORM.

**Pre-conditions (already met as of 2026-06-24):**
- Django skeleton v0.1.0 is live at https://srj-audit-web-gor5.onrender.com/
- `accounts.0001_initial` is applied
- `accounts/migrations/0001_initial.py` exists in the repo at commit `b89ec0e`
- All Tier 1 + Tier 2 tables exist in Postgres (from srj-mcp bootstrap)
- 115 questions are loaded in the `questions` table

**What this patch does:**
- Replaces empty placeholder `models.py` and `admin.py` files in 6 apps with real definitions
- Adds initial migrations to each app with `managed=False`, registering models in Django's migration history without DDL
- Upgrades `accounts/admin.py` with richer list/filter/search/fieldsets

**What this patch does NOT do:**
- No DDL. Zero `CREATE TABLE`, zero `ALTER TABLE`. The underlying tables already exist.
- No business logic. No views, no forms, no Stripe code, no PDF templates. Those come later.
- No question-loading or question-bank module. The 115 questions are already in the DB; the Question model just maps to them.

**Estimated time:** 10-15 minutes (extraction + commit + push + verify deploy)

---

## Phase 1 — Backup current state (1 min)

Best practice before any patch. Capture the current `main` commit so you can rollback if something breaks:

```powershell
cd "C:\Users\Stephen Jordan\My Drive\SRJ AI Audit Platform\GitHub Deployment files\audit_platform"

git log -1 --oneline
# Record this SHA somewhere accessible. Should be b89ec0e or later.
```

---

## Phase 2 — Extract the patch (2 min)

You'll get the patch as `audit_platform_patch_v0_2_0.tar.gz`. Save it to your Downloads folder.

```powershell
cd "C:\Users\Stephen Jordan\My Drive\SRJ AI Audit Platform\GitHub Deployment files\audit_platform"

# Extract the tarball directly on top of your repo.
# tar is built into Windows 10/11 PowerShell.
tar -xzvf "$env:USERPROFILE\Downloads\audit_platform_patch_v0_2_0.tar.gz" -C .

# Verify the files landed where expected:
Get-ChildItem -Recurse -File -Filter "models.py" | Select-Object FullName, Length
Get-ChildItem -Recurse -File -Filter "admin.py"  | Select-Object FullName, Length
Get-ChildItem -Recurse -File -Path "*/migrations/0001_initial.py" | Select-Object FullName, Length
```

Expected: 6 `models.py` files (engagements, questionnaire, scoring, reports, billing, core), 7 `admin.py` files (those 6 plus accounts), and 6 new `0001_initial.py` migrations.

---

## Phase 3 — Local sanity check (optional but recommended, 2 min)

```powershell
# Confirm Python can syntax-parse every new file
Get-ChildItem -Recurse -File -Filter "*.py" | ForEach-Object {
    python -m py_compile $_.FullName 2>&1
}
```

No output = all files parse cleanly. Any errors will print here, before you push.

---

## Phase 4 — Commit and push (2 min)

```powershell
git status
# Should show ~19 modified/new files

git add accounts/admin.py
git add engagements/models.py engagements/admin.py engagements/migrations/0001_initial.py
git add questionnaire/models.py questionnaire/admin.py questionnaire/migrations/0001_initial.py
git add scoring/models.py scoring/admin.py scoring/migrations/0001_initial.py
git add reports/models.py reports/admin.py reports/migrations/0001_initial.py
git add billing/models.py billing/admin.py billing/migrations/0001_initial.py
git add core/models.py core/admin.py core/migrations/0001_initial.py

git status
# Verify changes are staged. Should be ~19 files.

git commit -m "Patch v0.2.0: Add ORM + admin for engagements, questionnaire, scoring, reports, billing, core (all managed=False, mirror srj-mcp bootstrap schema)"
git push
```

Render will auto-redeploy both `srj-audit-web-gor5` and `srj-audit-worker-gor5` on push.

---

## Phase 5 — Watch the deploy (3-5 min)

Render dashboard → `srj-audit-web-gor5` → Logs.

**You should see, in order:**
1. `pip install` (cached, fast)
2. `python manage.py collectstatic --noinput` (128 static files copied)
3. `python manage.py migrate` running:
   - Applying `engagements.0001_initial`... OK (faked)
   - Applying `questionnaire.0001_initial`... OK (faked)
   - Applying `scoring.0001_initial`... OK (faked)
   - Applying `reports.0001_initial`... OK (faked)
   - Applying `billing.0001_initial`... OK (faked)
   - Applying `core.0001_initial`... OK (faked)
4. `gunicorn` starts, health checks pass
5. "Your service is live"

The migrations will be **faked** because the underlying tables already exist and the models are `managed=False`. This is intentional and expected.

If anything goes wrong:
- Migration failure with "table already exists": good news, the patch is working — it means `--fake-initial` isn't being applied. Check that the build command in `render.yaml` is `migrate --fake-initial` (it should be from skeleton v0.1.0).
- Migration failure with "no such column": schema mismatch between the model and DB. Capture the error and we'll patch via SRJ MCP execute_write like we did for `users.password`.

---

## Phase 6 — Verify via admin (3 min)

After "Your service is live":

1. Open https://srj-audit-web-gor5.onrender.com/admin/ in your browser
2. Sign in as `srj@srjconsultingservices.com`
3. You should now see the following sections on the admin index:

```
ACCOUNTS
  Companies
  Users

AUTHENTICATION AND AUTHORIZATION
  Groups

BILLING
  Discount credits
  Refund requests

CORE
  Events

ENGAGEMENTS
  Documents
  Engagements
  Respondents

QUESTIONNAIRE
  Questions
  Responses

REPORTS
  Reports

SCORING
  Scores
```

4. Click **Questions** — you should see all 115 loaded questions, filterable by tier/section/type
5. Click **Engagements** — list will be empty (no engagements purchased yet)
6. Click **Companies** — list will be empty
7. Click **Events** — list will be empty (no audit events yet)

If all 13 admin sections load without 500 errors, the patch succeeded.

---

## Phase 7 — Optional smoke test: create a test engagement (2 min)

Validate ORM end-to-end by creating a row through the admin:

1. **Companies** → **Add Company**
   - Name: `Test Co`
   - Industry: `Professional Services`
   - Size bracket: `26-100 employees`
   - Save
2. **Engagements** → **Add Engagement**
   - Tier: `Tier 1 — Snapshot`
   - Company: `Test Co`
   - Buyer user: `srj@srjconsultingservices.com`
   - Status: `In Progress`
   - Save
3. Open the saved Engagement detail page. You should see empty "Respondents" and "Documents" inline panels at the bottom.

This confirms:
- The Engagement model writes correctly to the existing `engagements` table
- FK constraints to `companies(id)` and `users(id)` work
- The inline relationship traversal works

Delete the test data via the admin once verified.

---

## Rollback (if needed)

If the deploy fails and you need to roll back to the previous commit:

```powershell
cd "C:\Users\Stephen Jordan\My Drive\SRJ AI Audit Platform\GitHub Deployment files\audit_platform"

# Revert to whatever SHA was recorded in Phase 1
git revert HEAD --no-edit
git push
```

Render will redeploy the previous state automatically.

---

## What's next after this patch

With the full ORM in place, the next workstreams unlock:

1. **`questionnaire/question_bank.py` + management command** — Already loaded directly to DB this session; this command would be for re-loads / future tier 2/3 questions
2. **`questionnaire/skip_logic.py`** — Skip-logic JSONB evaluator (pure-Python; Part A §3.x)
3. **`questionnaire/views.py`** — Tier 1 flow controller (deliver next question, capture response)
4. **`scoring/frameworks/v1_audit.py`** — V1 audit scorer with OD-12/OD-13 from Part A v1.2 patch
5. **Landing page + onboarding form** — Capture email + role + company at Q1 per Decision 7-6

The order matters: skip_logic → questionnaire views → scoring engine → landing page. Each piece feeds the next.

---

**Patch prepared:** 2026-06-24
**Tarball:** `audit_platform_patch_v0_2_0.tar.gz`
**Validated:** All 12 models import cleanly under Django 6.x; all 12 migration CreateModel ops are `managed=False`; all 13 admin registrations resolve.
**No DDL required:** All target tables exist in production DB from srj-mcp bootstrap.

# Security

This document covers how the SRJ AI Audit Platform is scanned, how findings are
triaged, and which dependencies are deliberately held back.

## Reporting a vulnerability

Email **srj@srjconsultingservices.com** with the details and, where possible, a
reproduction. Please do not open a public issue for an unpatched vulnerability.

The platform handles client audit responses and generates locked PDF reports, so
findings that touch report delivery, access codes, or the questionnaire session
are treated as high priority.

## Automated scanning

`.github/workflows/security-scan.yml` runs four scanners on every push to `main`,
on every pull request, weekly on Monday at 06:00 UTC, and on demand via
**Actions → Security Scan → Run workflow**. Results land under
**Security → Code scanning**.

| Scanner | Covers |
| --- | --- |
| Semgrep | Static analysis of application code (`--config=auto`) |
| Trivy | Dependency and infrastructure-as-code scanning, CRITICAL/HIGH/MEDIUM, fixed issues only |
| Gitleaks | Secrets across the full git history |
| CodeQL | Python, `security-extended` query set |

Dependabot is configured in `.github/dependabot.yml` for GitHub Actions and for
the Python requirements at the repository root. Routine version updates are
proposed weekly. Security updates driven by GitHub's advisory database run
independently of that file and are not rate-limited by it.

## Triage

Findings are one of three things, and each is handled differently.

**A real vulnerability** is fixed, or the dependency is upgraded, and the fix is
referenced in the commit message.

**A finding that does not reach a live code path** is documented rather than
silently dismissed. If it will recur on every scan, add a scoped suppression and
explain why in the same commit.

**A false positive** gets a narrowly scoped allowlist entry. Scope every entry to
the specific file and the specific string so that a genuine credential landing in
the same file still trips the scanner. Blanket rule disablement is not acceptable;
a scanner that cries wolf gets ignored, and the next finding may be real.

### Current suppressions

`.gitleaks.toml` allowlists one string in `reports/generator.py`. The module
docstring describes the OD-18 PDF encryption design, and the `generic-api-key`
rule matches on "user password," followed by the permissions text, scoring it as
high entropy. No credential is present: `owner_password` is a function parameter
supplied from settings, and `user_password` is an intentional empty string so
that delivered reports open without a prompt.

## Dependency policy

**WeasyPrint renders every Tier 1 PDF report**, so version bumps are reviewed by
hand rather than merged automatically — major releases change CSS layout.
`dependabot.yml` excludes WeasyPrint major bumps from automated proposals for
this reason. The validation before any bump is: render `tier1_snapshot.html` on
both versions and compare page count, page sizes and per-page extracted text,
including an inflated run long enough to exercise page breaks.

It sat at 68.0 until 2026-09-15 and now runs 70.0, which closes
CVE-2026-55073 (SSRF) and CVE-2026-49452 (CSS injection). Two notes worth
keeping, because the earlier rationale in this repository was wrong about both:

The deny-all `url_fetcher` in `reports/generator.py` did **not** mitigate the
SSRF. `write_pdf()` ignored the document's fetcher on the `xmp_metadata` and
`attachments` channels and built a fresh default one — being bypassed was the
vulnerability. The platform was unaffected only because `write_pdf()` is called
with no arguments. Keep the deny-all fetcher anyway: it is what blocks remote
and `file://` loads on the normal render path.

The CSS injection had nothing to do with `url_fetcher` either. It required
`presentational_hints=True`, which is never set.

The general lesson: a compensating control is only a control if it sits in the
path the advisory describes. Record which mechanism a mitigation actually
blocks, not which one it is near.

## Secrets

No credentials belong in the repository. Runtime configuration is supplied through
environment variables — see `.env.example` for the expected names. Report storage
credentials, Stripe keys, and the PDF owner password are all read from settings at
runtime.

If a secret is ever committed, rotate it first and remove it from history second.
Rotation is what actually closes the exposure; history rewriting only limits
further spread.

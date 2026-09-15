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

## Held dependencies

**WeasyPrint is pinned at 68.0.** It renders every Tier 1 PDF report, and major
version bumps have historically changed CSS layout behaviour. Any upgrade must be
validated by generating a full report end to end and comparing the output before
it is merged, so major bumps are excluded from automated proposals in
`dependabot.yml` and reviewed by hand instead.

68.0 patches PYSEC-2026-2034. Its second SSRF advisory, PYSEC-2026-3412, remains
unpatched upstream; the deny-all `url_fetcher` in `reports/generator.py` is the
compensating control and must stay in place for as long as that advisory is open.
Removing it would reintroduce the exposure regardless of the installed version.

## Secrets

No credentials belong in the repository. Runtime configuration is supplied through
environment variables — see `.env.example` for the expected names. Report storage
credentials, Stripe keys, and the PDF owner password are all read from settings at
runtime.

If a secret is ever committed, rotate it first and remove it from history second.
Rotation is what actually closes the exposure; history rewriting only limits
further spread.

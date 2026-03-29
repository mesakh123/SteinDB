<p align="center">
  <!-- TODO: Replace with actual logo -->
  <h1 align="center">SteinDB</h1>
  <p align="center"><strong>The only bidirectional Oracle <-> PostgreSQL migration tool</strong></p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSL%201.1-blue.svg" alt="License: BSL 1.1"></a>
  <img src="https://img.shields.io/badge/tests-1%2C643%20passing-brightgreen.svg" alt="Tests: 1,643 passing">
  <img src="https://img.shields.io/badge/golden%20tests-870%2B-brightgreen.svg" alt="Golden Tests: 870+">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/i18n-18%20languages-orange.svg" alt="i18n: 18 languages">
</p>

---

## Terminal Demo

<!-- TODO: Replace with asciinema GIF recording -->
```
$ stein --version
SteinDB CLI v0.1.0

$ stein scan sample.sql --output table

SteinDB -- Oracle -> PostgreSQL Migration
================================================
Scanned: 10 objects in 0.3s

Object          Type        Schema  Complexity  Status
--------------- ----------- ------- ----------- ------
employees       TABLE       hr      2           Low
emp_seq         SEQUENCE    hr      1           Low
trg_emp_bi      TRIGGER     hr      4           Medium
active_emps     VIEW        hr      3           Low
get_salary      FUNCTION    hr      5           Medium

Summary: 8 auto-convertible, 2 need AI assistance
Savings estimate: ~$180K/year in Oracle licensing

$ stein convert sample.sql --output converted/ --mode rules
Converting... ======================== 100%
Converted: 8/10 objects (rules), 2 forwarded to AI
Output: converted/

$ stein verify converted/
All 8 conversions: GREEN (confidence: 100%)
```

## Quick Start

```bash
pip install steindb && stein scan sample.sql
```

That's it. No Oracle Client needed, no account required, works offline.

```bash
# Scan your Oracle schema
stein scan your-oracle-export.sql

# Convert with deterministic rules only (no AI, fully offline)
stein convert your-oracle-export.sql --output ./converted/ --rules-only

# Convert with AI assistance (BYOK -- your API keys)
export STEIN_API_KEY=sk-your-openai-key
stein convert your-oracle-export.sql --output ./converted/ --model gpt-4o

# PostgreSQL to Oracle (reverse direction)
stein convert --direction pg_to_oracle your-pg-export.sql --output ./converted/

# Verify the converted output
stein verify ./converted/

# Generate an HTML report
stein report ./converted/
```

## Features

- **Bidirectional** -- Oracle to PostgreSQL AND PostgreSQL to Oracle. The only tool that does both.
- **90%+ automation** -- Deterministic rules handle the majority with 100% accuracy. AI handles the remaining 10%.
- **Built-in verification** -- Every converted object gets a confidence score (0.0-1.0). Syntax-checked, EXPLAIN dry-run tested, structurally compared.
- **Works offline** -- Rules-only mode runs entirely on your machine. No cloud, no network calls, no data leaving your environment.
- **BYOK (Bring Your Own Key)** -- Use GPT-4o, Claude, Gemini, or local models via Ollama. Your code never touches our servers.
- **870+ golden test pairs** -- Every accuracy claim is verifiable. Run `stein test --golden` yourself.
- **Handles the hard parts** -- CONNECT BY, PL/SQL packages, AUTONOMOUS_TRANSACTION, Oracle empty string = NULL, and the other "silent killers" that break migrations.

## Comparison

| Feature | SteinDB | Ora2Pg | AWS SCT |
|---------|----------|--------|---------|
| Automation rate | 90%+ | 40-60% | 40-60% |
| PL/SQL conversion | Rules + AI | Limited | Limited |
| Bidirectional (PG to Oracle) | Yes | No | No |
| Verification with confidence scores | Yes | No | No |
| Offline mode | Yes | Yes | No |
| BYOK model support | Yes | N/A | N/A |
| CONNECT BY handling | Automated | Manual | Partial |
| Package decomposition | Automated | Manual | Manual |
| Silent bug detection | 7 static analysis rules | No | No |
| Price (CLI) | Free | Free | AWS account required |
| Source available | Yes (BSL 1.1) | Yes (PostgreSQL license) | No |

## Supported Conversions

35 rule modules covering 870+ constructs in both directions:

| Category | Examples | Status |
|----------|----------|--------|
| Data Types | VARCHAR2, NUMBER, DATE, CLOB, BLOB (23 Oracle / 15 PG types) | Fully automated |
| Functions | NVL, DECODE, SYSDATE, NVL2, ROWNUM | Fully automated |
| DDL | CREATE TABLE, ALTER TABLE, indexes, constraints, sequences | Fully automated |
| PL/SQL | Procedures, functions, packages, triggers, exceptions | Rules + AI |
| DML | CONNECT BY, MERGE, (+) joins, analytic functions | Rules + AI |
| Static Analysis | Empty string = NULL, DATE vs TIMESTAMP, SELECT INTO bugs | 7 detection rules |

## Internationalization

SteinDB CLI supports 18 languages: English, Japanese, Korean, Chinese (Simplified & Traditional), German, French, Portuguese (Brazil), Spanish, Hindi, Indonesian, Thai, Vietnamese, Turkish, Italian, Dutch, Polish, and Arabic.

Set your language:
```bash
export STEIN_LOCALE=ja  # Japanese
stein scan sample.sql
```

## Pricing

The CLI tool is **free and open source** (BSL 1.1). Rules-only mode works offline with no account required.

Paid tiers add AI-assisted conversion, team collaboration, and managed cloud features.

## Cloud Service (Coming Soon)

SteinDB Cloud is an upcoming managed platform that extends the CLI:

- **Web Playground** -- paste SQL and convert instantly in your browser
- **AI-Assisted Conversion** -- hosted LLM inference for the ~10% the rule engine forwards
- **Team Collaboration** -- invite team members, share conversions, manage API keys
- **Cloud Migration** -- direct database-to-database migration between AWS RDS, GCP Cloud SQL, Azure PostgreSQL, and on-premise instances
- **Post-Migration Monitoring** -- continuous PostgreSQL performance monitoring after migration
- **OAuth Login** -- sign in with Google or GitHub
- **Dashboard** -- conversion history, usage analytics, billing management

## Links

- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

SteinDB is source-available under the [Business Source License 1.1](LICENSE).

- **You CAN**: read, modify, self-host, and use in production for your own migrations.
- **You CANNOT**: offer SteinDB as a competing hosted service.
- **After 4 years**: each version converts to Apache License 2.0.

Same model as HashiCorp Terraform, Sentry, and CockroachDB.

---

Oracle is a registered trademark of Oracle Corporation. PostgreSQL is a registered trademark of the PostgreSQL Community Association of Canada. SteinDB is not affiliated with, endorsed by, or sponsored by Oracle Corporation or the PostgreSQL Global Development Group.

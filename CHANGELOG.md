# Changelog

All notable changes to SteinDB CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## v0.1.0 (2026-03-28) -- Initial Release

### Features
- Bidirectional Oracle <-> PostgreSQL migration (O2P and P2O)
- 34 rule modules (21 O2P + 13 P2O) with >99% correctness on deterministic conversions
- AI-assisted conversion for remaining ~10% via BYOK (Bring Your Own Key)
- 5-stage async verification pipeline (parse, EXPLAIN, remnant detection, structural, confidence)
- CLI commands: `scan`, `convert`, `verify`, `report`, `auth`, `config`, `cloud`
- Scanner: DDL parser (12 object types), complexity scorer (24 patterns), dependency graph
- Live Oracle database connection (thin mode, no Oracle Client needed)
- HTML and JSON report generation with savings estimates
- Cloud migration planning for AWS RDS/Aurora, GCP Cloud SQL/AlloyDB, Azure PostgreSQL
- 18 language translations (i18n): en, ja, ko, zh-CN, zh-TW, de, fr, pt-BR, es, hi, id, th, vi, tr, it, nl, pl, ar
- Homebrew and PyPI distribution
- Free and offline: rules-only mode requires no account, no network, no signup

### Supported Conversions (O2P)
- Data types: VARCHAR2, NUMBER, DATE, CLOB, BLOB, NVARCHAR2, RAW, LONG, and more (23 types)
- Functions: NVL, NVL2, DECODE, SYSDATE, SYSTIMESTAMP, TO_DATE, TO_CHAR, SUBSTR, INSTR
- SQL syntax: CONNECT BY, (+) outer joins, ROWNUM, DUAL, MINUS, analytic functions
- DDL: CREATE TABLE, ALTER TABLE, sequences, indexes, constraints, partitioning, storage cleanup
- PL/SQL: triggers, procedures, functions, packages, exception handling, cursors, BULK COLLECT
- Grants, synonyms, materialized views

### Supported Conversions (P2O)
- Data types: TEXT, BYTEA, BOOLEAN, SERIAL, BIGSERIAL, UUID, JSONB, ARRAY, and more
- Functions: NOW(), CURRENT_TIMESTAMP, string_agg, array_agg
- SQL syntax: LIMIT/OFFSET, RETURNING, DISTINCT ON, type casting (::)
- DDL: GENERATED ALWAYS AS IDENTITY, IF EXISTS, partial indexes
- PL/pgSQL: triggers, functions, RAISE NOTICE/EXCEPTION, PERFORM

### Security
- BYOK model: your API keys stay local, never stored or proxied
- SSRF protection on LLM router (blocks localhost, private IPs, AWS metadata)
- Prompt injection defense (NFKC normalization, canary tokens, pattern detection)
- No telemetry by default (opt-in only)

### Quality
- 1,735 automated tests passing
- 95.27% code coverage
- 382+ golden test YAML pairs
- mypy strict mode, ruff linting, pre-commit hooks
- Property-based testing (Hypothesis)
- Performance benchmarks

### Contact
- Security issues: cmesakh@ymail.com
- License questions: cmesakh@ymail.com

# Security policy

Version 0.1 is a local reference implementation. Do not expose demo mode publicly or upload confidential production records without reviewing [the threat model](docs/security.md).

When this repository is published, use GitHub's **Report a vulnerability** feature if private reporting is enabled. If unavailable, open a minimal issue asking for a private contact channel without posting exploit details or sensitive data. The maintainer must configure private reporting before public release; no response SLA is promised for this initial project.

A useful report includes affected commit/version, a minimal synthetic reproduction, trust boundary crossed, severity rationale and safe remediation suggestions. Do not include company records, secrets or information obtained through unauthorized access.

Dependency advisories are checked with open-source tooling in CI. A clean audit is point-in-time evidence, not a security guarantee. The project does not execute model-generated code or SQL, and it includes no AI mutation tools.

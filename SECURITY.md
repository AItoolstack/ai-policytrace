# Security And Privacy

PolicyTrace is designed for document extraction workflows that may involve sensitive personal data.

## Public Demo Rules

- Use only synthetic or redacted PDFs.
- Do not commit real customer documents.
- Do not commit `.env` or API keys.
- Do not commit `output/`, session folders, debug artifacts, or generated extraction JSON from real documents.
- Rotate any key that was ever stored in a local file before publishing the repository.

## Secrets

Local development uses `.env`, which is ignored by git.

Production deployments should use platform secrets:

- Hugging Face Spaces: Space Secrets
- GitHub Actions: Repository Secrets
- Cloud platforms: managed secret stores

## Uploaded Files

The local API stores uploaded PDFs under `output/sessions/`. Session folders are deleted on startup when they are older than `pipeline.session_ttl_days`.

For production use, add authentication, stronger retention controls, audit logging, and external storage policies before accepting real documents.

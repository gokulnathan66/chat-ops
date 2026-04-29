# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please send an email to
**gokulnathan.b@aivar.tech** with the subject line `[SECURITY] <brief description>`.

Include as much of the following information as possible:

- Type of issue (e.g. prompt injection, credential exposure, SSRF, etc.)
- Full paths of source file(s) related to the issue
- Location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

## Response Timeline

| Stage    | Target SLA |
| -------- | ---------- |
| Acknowledgement | 48 hours |
| Triage & severity assessment | 7 days |
| Fix & release | 30 days |

We will keep you informed of progress throughout the process. If you have not
received a response within 48 hours, please follow up to ensure we received
your original message.

## Security Best Practices for Users

### Secrets Management

- **Never commit `.env` files** to version control. Use `.env.example` as a
  template and keep real credentials out of git.
- Store secrets in **AWS Secrets Manager** or **AWS Parameter Store** rather
  than environment variables in production.
- **Rotate Bedrock and Langfuse keys** regularly and immediately if you suspect
  they have been compromised.
- Use IAM roles with least-privilege policies for Bedrock access rather than
  long-lived access keys.

### Infrastructure

- Restrict Bedrock model access using **IAM Service Control Policies (SCPs)**
  at the AWS Organization level to limit which models and regions can be
  invoked.
- **Qdrant API key over HTTP**: If your Qdrant instance is not behind TLS,
  the API key is transmitted in plaintext. Always place Qdrant behind HTTPS
  (e.g., via an ALB or nginx with a valid certificate) in production
  environments.
- Restrict Qdrant network access to your application's security group or VPC
  — do not expose it to the public internet.

### Application

- Validate and sanitize all user inputs before passing them to the LangGraph
  pipeline to reduce prompt injection risk.
- Enable Langfuse tracing only in environments where you control access to the
  Langfuse instance, as traces may contain sensitive user queries.
- Review IAM policies attached to the Lambda execution roles in
  `iac/terraform-aws/` before deploying to production.

## Known Security Considerations

### Bedrock IAM SCP Restrictions

AWS Service Control Policies can silently deny Bedrock `InvokeModel` calls
even when the IAM role policy appears to allow them. If you encounter
unexpected `AccessDeniedException` errors, verify that no SCP at the
organization or account level is restricting Bedrock access for your region
or model ARN.

### Qdrant API Key Over HTTP

The default `QDRANT_HOST=http://localhost:6333` configuration transmits the
`QDRANT_API_KEY` over unencrypted HTTP. This is acceptable for local
development but **must not be used in production**. Always configure a
`https://` host for any non-local Qdrant deployment.

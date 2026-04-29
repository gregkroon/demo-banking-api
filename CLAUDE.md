# Demo Banking API - Harness + Claude Code Integration

## Project Overview

This is a demo Flask-based banking API showcasing Harness CI/CD integration with Claude Code. The project intentionally includes vulnerable dependencies for Security Testing Orchestration (STO) demonstrations.

**Repository**: `demo-banking-api` (Harness Code)
**Tech Stack**: Python 3.11+, Flask, JWT authentication
**Registry**: Harness Artifact Registry (HAR)

## API Endpoints

- `GET /health` - Health check
- `POST /auth/login` - Generate JWT token (demo: any non-empty credentials work)
- `GET /accounts` - List all accounts
- `GET /accounts/<account_id>` - Get account details
- `GET /accounts/<account_id>/balance` - Get account balance
- `POST /transfers` - Transfer funds between accounts
- `GET /transactions` - List all transactions

## Harness Pipeline Architecture

### Main Pipeline: demo-banking-api

**Template-Based Structure** (uses account-level templates):
1. **Build and Test** (ci_build_test template)
   - Runs unit tests with pytest
   - Claude Code coverage check (80% threshold)
   - Builds and pushes Docker image to HAR
   - STO container scan
   - SBOM generation with Syft + Cosign attestation

2. **Deploy to Dev** (cd_k8s_rolling template)
   - Environment: dev
   - Infrastructure: dev_k8s
   - Namespace: banking-dev
   - Artifact tag: `<+pipeline.sequenceId>`

3. **Production Approval** (production_gate template)
   - Manual approval required
   - Change ticket input
   - Disallows pipeline executor from approving

4. **Deploy to Production** (cd_k8s_rolling template)
   - Environment: production
   - Infrastructure: prod_k8s
   - Namespace: banking-prod
   - Artifact tag: `<+pipeline.sequenceId>`

### Related Pipeline: fx-rates-api

Similar structure using the same account-level templates with different service/registry references.

## Project-Level Templates

1. **ci_build_test** - CI Stage template
   - Variables: serviceRepo, registryRef
   - Steps: Run tests, Claude coverage check, build/push Docker, STO scan, SBOM generation

2. **cd_k8s_rolling** - CD Stage template
   - Kubernetes rolling deployment with rollback strategy
   - Variable: namespace

3. **production_gate** - Approval Stage template
   - Production deployment approval gate
   - Variable: serviceName

## Harness Resources

**Services**:
- `demo_banking_api` - Kubernetes service with HAR artifact source
- `fx_rates_api` - Similar configuration for FX rates service

**Environments**:
- `dev` - Development environment
- `production` - Production environment

**Infrastructures**:
- `dev_k8s` - Kubernetes cluster for dev
- `prod_k8s` - Kubernetes cluster for production

**Registries**:
- `banking-api` - HAR connector for demo-banking-api
- `fx-rates-api` - HAR connector for fx-rates-api

## Key Conventions

### Artifact Tagging
- Always use `<+pipeline.sequenceId>` for artifact tags to ensure traceability
- Also tag with `latest` in CI builds

### Pipeline Inputs
When creating pipelines with templates, you must provide:
- Branch via `build` property in codebase
- Artifact sources with `primaryArtifactRef` and `sources` for each deployment stage
- Do NOT specify `connectorRef` in codebase - use repoName only

### Codebase Configuration
```yaml
properties:
  ci:
    codebase:
      repoName: <repo-name>
      build: <+input>
```

### Deployment Stage Artifact Input
```yaml
serviceInputs:
  serviceDefinition:
    spec:
      artifacts:
        primary:
          sources:
            - identifier: harnessartifactregistry
              type: Har
              spec:
                type: docker
                spec:
                  tag: <+pipeline.sequenceId>
```

## OPA Policies

**Image Security Policy Set**:
- Image Security Policy - Blocks critical CVEs
- SBOM Required Policy - Requires SBOM generation

**Production Deployment Policy Set**:
- Change Window Policy - Enforces Mon-Fri 08:00-17:00 AEST
- Production Deployment Policy - Governance checks

## Development Workflow

1. Make code changes locally
2. Run tests: `source .venv/bin/activate && pytest tests/ -v`
3. Commit and push to main branch
4. Pipeline triggers automatically or manually
5. Monitor via Harness UI or Claude Code with `harness_diagnose`

## Common Operations

### Trigger Pipeline
```
harness_execute(resource_type='pipeline', resource_id='demo_banking_api', action='run', inputs={'branch': 'main'})
```

### Monitor Execution
```
harness_diagnose(resource_type='pipeline', resource_id='demo_banking_api', options={'execution_id': '<id>', 'include_visual': true})
```

### Revert Code Changes
```bash
git revert <commit-hash> --no-edit
git push origin main
```

## Important Notes

- This is a DEMO project with intentionally vulnerable dependencies
- Authentication is simplified (any credentials work)
- In-memory data storage (resets on restart)
- NOT production-ready - for demonstration purposes only
- use only MCP to create and execute entities

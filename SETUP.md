# Demo Environment Setup Guide

This guide covers everything needed to run the Harness + Claude Code demo in a fresh Harness account. Follow the sections in order — account-level resources must exist before project-level ones.

---

## Overview

The demo uses two Harness projects and two services:

| Service | Scenario | Harness Code Repo | HAR Registry scope |
|---------|----------|-------------------|--------------------|
| `demo-banking-api` | Scenario 1 — Day in the Life | `demo-banking-api` | Project-level (`banking-api`) |
| `fx-rates-api` | Scenario 2 — New Service Onboarding | `fx-rates-api` | **Account-level** (`fx-rates`) |

---

## 1. Account-Level Prerequisites

These are created once and shared across all projects and teams — they are the governance layer.

### 1.1 Secrets

Create three secrets at **Account** scope (Account Settings → Secrets):

| Name | Type | Value |
|------|------|-------|
| `cosign_private_key` | **Secret File** | Your cosign private key file (generate with `cosign generate-key-pair`) |
| `cosign_password` | Secret Text | Password for the cosign private key |
| `anthropic_api_key` | Secret Text | Anthropic API key for Claude Code coverage check |

> **Generate cosign keys:**
> ```bash
> cosign generate-key-pair
> # Produces cosign.key (upload as cosign_private_key) and cosign.pub
> ```

### 1.2 Connectors

Verify these account-level connectors exist (Account Settings → Connectors):

| Identifier | Type | Purpose |
|------------|------|---------|
| `account.harnessImage` | Docker Registry | Pulls Harness-hosted CI runner images (usually pre-exists) |
| `account.k8s` | Kubernetes | Connects to your K8s cluster for deployments |

The `account.k8s` connector must have cluster-admin or sufficient RBAC to create/update Deployments, Services, ConfigMaps, and Namespaces.

### 1.3 Harness Artifact Registry — `fx-rates` (Account level)

Navigate to **Account Settings → Artifact Registries → New Registry**:

- **Name:** `fx-rates`
- **Type:** Docker
- **Scope:** Account

> This must be account-level. The `fx-rates-api` service references it as `account.fx-rates`. A project-level registry will cause a 400 error at the CD service step.

### 1.4 OPA Policies

Create four Rego policies at **Account** scope (Account Settings → Policies → Policies). Save each with real newlines — do not use `\n` escaped strings.

**Policy: `image_security_policy`** — blocks critical CVEs
```rego
package pipeline_environment

deny[msg] {
  input.pipeline.stages[_].stage.type == "SecurityTests"
  vuln := input.pipeline.stages[_].stage.spec.execution.steps[_].step.outcome.vulnerabilities[_]
  vuln.severity == "CRITICAL"
  msg := sprintf("Critical CVE found: %v — upgrade the affected package before deploying.", [vuln.packageName])
}
```

**Policy: `sbom_required_policy`** — warns if ci_build_test template is absent
```rego
package pipeline_environment

warn[msg] {
  templateRefs := [ref |
    ref := input.pipeline.stages[_].stage.template.templateRef
  ]
  not any_ci_template(templateRefs)
  msg := "BLOCKED: No SCA/SBOM scan found. Pipeline must include the ci_build_test stage template."
}

any_ci_template(refs) {
  refs[_] == "ci_build_test"
}
```

**Policy: `change_window_policy`** — warns outside Mon–Fri 08:00–17:00 AEST
```rego
package pipeline_environment

warn[msg] {
  input.pipeline.stages[_].stage.type == "Deployment"
  input.pipeline.stages[_].stage.spec.environment.environmentRef == "production"
  not in_change_window
  msg := "WARNING: Deployment is outside the approved change window (Mon-Fri 08:00-17:00 AEST). Proceed with caution."
}

in_change_window {
  hour := time.clock(time.now_ns())[0]
  day  := time.weekday(time.now_ns())
  day != "Saturday"
  day != "Sunday"
  hour >= 8
  hour < 17
}
```

**Policy: `production_deployment_policy`** — enforces prod deployment governance
```rego
package pipeline_environment

deny[msg] {
  input.pipeline.stages[_].stage.type == "Deployment"
  input.pipeline.stages[_].stage.spec.environment.environmentRef == "production"
  not has_approval_stage
  msg := "Production deployments require an approval stage before deploying."
}

has_approval_stage {
  input.pipeline.stages[_].stage.type == "Approval"
}
```

### 1.5 OPA Policy Sets

Create two policy sets at Account scope (Account Settings → Policies → Policy Sets):

**Policy Set: `image_security_policy_set`**
- **Policies:** `image_security_policy` (severity: error), `sbom_required_policy` (severity: warning)
- **Entity type:** Pipeline
- **Event:** On Run
- **Enforcement:** Enabled

**Policy Set: `production_deployment_policy_set`**
- **Policies:** `production_deployment_policy` (severity: error), `change_window_policy` (severity: warning)
- **Entity type:** Pipeline
- **Event:** On Run
- **Enforcement:** Enabled

### 1.6 Account-Level Templates

Create three Stage templates at **Account** scope (Account Settings → Templates → New Template → Stage). Each must be version `1.0`.

---

#### Template: `ci_build_test`

**Critical settings — do not miss these:**
- Build and Push step must push **both** `<+pipeline.sequenceId>` **and** `latest` tags
- HarnessSCA must use `detection: manual` with explicit `name` and `variant`
- `claude --print` must have `|| true` to be non-fatal when API credits are low

```yaml
template:
  name: ci-build-test
  identifier: ci_build_test
  versionLabel: "1.0"
  type: Stage
  spec:
    type: CI
    variables:
      - name: serviceRepo
        type: String
        value: <+input>
        description: Image repository name in HAR (e.g. demo-banking-api)
      - name: registryRef
        type: String
        value: <+input>
        description: HAR registry connector identifier (e.g. banking-api)
    spec:
      cloneCodebase: true
      platform:
        os: Linux
        arch: Amd64
      runtime:
        type: Cloud
        spec: {}
      execution:
        steps:
          - step:
              type: Run
              name: Run Unit Tests
              identifier: run_tests
              spec:
                image: python:3.11-slim
                shell: Sh
                command: |-
                  pip install --no-cache-dir -r requirements.txt pytest pytest-cov
                  pytest tests/ -v --tb=short --junitxml=test-results.xml --cov=app --cov-report=term --cov-report=json --cov-report=xml
                reports:
                  type: JUnit
                  spec:
                    paths:
                      - test-results.xml
          - step:
              type: Run
              name: Claude Code Coverage Check
              identifier: claude_coverage_check
              spec:
                connectorRef: account.harnessImage
                image: node:20-slim
                shell: Sh
                command: |-
                  npm install -g @anthropic-ai/claude-code --quiet 2>/dev/null
                  COVERAGE=$(node -e "const d=require('./coverage.json'); console.log(d.totals.percent_covered.toFixed(1))")
                  LINES=$(node -e "const d=require('./coverage.json'); console.log(d.totals.covered_lines + '/' + d.totals.num_statements)")
                  echo "=== Claude Code Coverage Check ==="
                  echo "Coverage: ${COVERAGE}% (${LINES} lines)"
                  claude --print "You are a CI quality gate for the <+stage.variables.serviceRepo> project. Test coverage is ${COVERAGE}% (${LINES} lines covered). The required threshold is 80%. Provide a 2-3 sentence assessment of the coverage quality and end with a clear verdict: PASS or FAIL." || true
                  if [ "$(node -e "const d=require('./coverage.json'); console.log(d.totals.percent_covered >= 80 ? 'pass' : 'fail')")" = "fail" ]; then
                    echo "ERROR: Coverage ${COVERAGE}% is below the 80% threshold"
                    exit 1
                  fi
                envVariables:
                  ANTHROPIC_API_KEY: <+secrets.getValue("account.anthropic_api_key")>
              when:
                stageStatus: Success
                condition: <+1 == 1>
          - step:
              type: BuildAndPushDockerRegistry
              name: Build and Push to HAR
              identifier: build_and_push
              spec:
                repo: <+stage.variables.serviceRepo>
                tags:
                  - <+pipeline.sequenceId>
                  - latest
                dockerfile: Dockerfile
                context: .
                registryRef: <+stage.variables.registryRef>
          - step:
              type: HarnessSCA
              name: HarnessContainer
              identifier: HarnessContainer
              spec:
                mode: orchestration
                config: default
                target:
                  type: container
                  detection: manual
                  name: <+stage.variables.serviceRepo>
                  variant: <+pipeline.sequenceId>
                advanced:
                  log:
                    level: info
                privileged: true
                image:
                  type: harness
                  tag: <+pipeline.sequenceId>
                  registry: <+stage.variables.registryRef>
                  image_path: <+stage.variables.serviceRepo>
          - step:
              type: SscaOrchestration
              name: Generate SBOM
              identifier: generate_sbom
              spec:
                mode: generation
                tool:
                  type: Syft
                  spec:
                    format: spdx-json
                source:
                  type: har
                  spec:
                    registry: <+stage.variables.registryRef>
                    image: <+stage.variables.serviceRepo>
                    tag: <+pipeline.sequenceId>
                attestation:
                  type: cosign
                  spec:
                    privateKey: account.cosign_private_key
                    password: account.cosign_password
                sbom_drift:
                  base: last_generated_sbom
                resources:
                  limits:
                    memory: 500Mi
                    cpu: "0.5"
```

> **Why `|| true` on `claude --print`?** Claude Code exits non-zero when the Anthropic API returns an error (e.g. insufficient credits). Without `|| true`, this fails the CI step. The coverage threshold check below it is the actual gate.
>
> **Why both `<+pipeline.sequenceId>` and `latest` in Build and Push tags?** HarnessSCA always pulls `:latest` from the registry to perform the actual container scan, regardless of the `image.tag` field. Without a `latest` tag, SCA fails on brand-new registries with "manifest unknown".
>
> **Why `detection: manual` with explicit `name`/`variant`?** `detection: auto` ignores the `image.tag` field and always resolves the variant as `latest`. `detection: manual` with explicit values correctly tracks the scan against the sequenceId build number in the STO dashboard.

---

#### Template: `cd_k8s_rolling`

```yaml
template:
  name: cd-k8s-rolling
  identifier: cd_k8s_rolling
  versionLabel: "1.0"
  type: Stage
  spec:
    type: Deployment
    variables:
      - name: namespace
        type: String
        value: <+input>
        description: Kubernetes namespace for this deployment
    spec:
      deploymentType: Kubernetes
      service:
        serviceRef: <+input>
        serviceInputs: <+input>
      environment:
        environmentRef: <+input>
        deployToAll: false
        environmentInputs: <+input>
        infrastructureDefinitions: <+input>
      execution:
        steps:
          - step:
              type: K8sRollingDeploy
              name: Rolling Deploy
              identifier: rolling_deploy
              timeout: 10m
              spec:
                skipDryRun: false
                pruningEnabled: false
        rollbackSteps:
          - step:
              type: K8sRollingRollback
              name: Rollback
              identifier: rollback
              timeout: 10m
              spec: {}
    failureStrategies:
      - onFailure:
          errors:
            - AllErrors
          action:
            type: StageRollback
```

---

#### Template: `production_gate`

```yaml
template:
  name: production-gate
  identifier: production_gate
  versionLabel: "1.0"
  type: Stage
  spec:
    type: Approval
    variables:
      - name: serviceName
        type: String
        value: <+input>
        description: Name of the service being deployed
    spec:
      execution:
        steps:
          - step:
              type: HarnessApproval
              name: Approve Production Deployment
              identifier: approve_production
              timeout: 1d
              spec:
                approvalMessage: |-
                  ## Production Deployment Approval

                  **Service:** <+stage.variables.serviceName>
                  **Build:** #<+pipeline.sequenceId>
                  **Dev smoke tests:** PASSED

                  Please review the dev deployment and approve to proceed to production.
                  This deployment is subject to the change-window policy (Mon-Fri 08:00-17:00 AEST).
                includePipelineExecutionHistory: true
                isAutoRejectEnabled: false
                approvers:
                  minimumCount: 1
                  disallowPipelineExecutor: true
                  userGroups:
                    - account._account_all_users
                approverInputs:
                  - name: ChangeTicket
                    defaultValue: ""
```

> **`disallowPipelineExecutor: true`** enforces the OPA talking point — the developer who triggered the pipeline cannot approve their own deployment.

---

## 2. Project-Level Setup

Create a project (this guide uses identifier `claude`, org `default`).

### 2.1 Harness Code Repositories

Create two repos under the project (Code → Repositories → New Repository):

| Repo name | Contents |
|-----------|----------|
| `demo-banking-api` | This repo (`/mcp/demo`) — Flask banking API |
| `fx-rates-api` | FX Rates Flask API with `Dockerfile`, `k8s/base/deployment.yaml`, `k8s/base/values.yaml`, `tests/`, `requirements.txt` |

Push the code to the `main` branch of each repo.

**Required files in each repo's `k8s/base/`:**

`deployment.yaml` — uses Go template syntax for image injection:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <service-name>
spec:
  replicas: 2
  selector:
    matchLabels:
      app: <service-name>
  template:
    metadata:
      labels:
        app: <service-name>
    spec:
      imagePullSecrets:
        - name: harness-registry-secret
      containers:
        - name: <service-name>
          image: {{.Values.image}}      # <-- Go template, NOT <+artifact.image>
          ports:
            - containerPort: 8080
```

`values.yaml` — bridges Harness expression to Go template:
```yaml
image: <+artifact.image>
```

> **Why this two-file pattern?** Harness evaluates `<+artifact.image>` in `values.yaml` first (replacing it with the full registry URL), then applies it to `deployment.yaml` via Go templating. Putting `<+artifact.image>` directly in `deployment.yaml` does **not** work with Kustomize/K8sManifest — it won't be substituted.

### 2.2 Harness Artifact Registry — `banking-api` (Project level)

Navigate to **Project → Artifact Registries → New Registry**:

- **Name:** `banking-api`
- **Type:** Docker
- **Scope:** Project

> The `banking-api` registry is project-level. The `fx-rates` registry (Section 1.3) is account-level. This difference matters: the `fx-rates-api` service must reference it as `registryRef: account.fx-rates`.

### 2.3 Environments

Create two environments (Project → Environments):

| Name | Identifier | Type |
|------|------------|------|
| `dev` | `dev` | Pre-Production |
| `production` | `production` | Production |

### 2.4 Infrastructure Definitions

Under each environment, create an infrastructure definition using the `account.k8s` connector:

**Under `dev` environment:**
- **Name:** `dev-k8s`
- **Identifier:** `dev_k8s`
- **Type:** Kubernetes Direct
- **Connector:** `account.k8s`
- **Namespace:** `banking-dev`
- **Release name:** `release-<+INFRA_KEY>`

**Under `production` environment:**
- **Name:** `prod-k8s`
- **Identifier:** `prod_k8s`
- **Type:** Kubernetes Direct
- **Connector:** `account.k8s`
- **Namespace:** `banking-prod`
- **Release name:** `release-<+INFRA_KEY>`

> The infrastructure namespace (`banking-dev` / `banking-prod`) is used for the banking-api service. The `cd_k8s_rolling` template accepts a `namespace` variable but this is informational in the approval message — the actual K8s namespace is controlled by the infrastructure definition. For the fx-rates service, the same `dev_k8s` / `prod_k8s` infrastructure is reused (K8s namespaces `fx-rates-dev` / `fx-rates-prod` must exist separately — see Section 3).

### 2.5 Services

#### Service: `demo_banking_api`

```yaml
service:
  name: demo-banking-api
  identifier: demo_banking_api
  serviceDefinition:
    type: Kubernetes
    spec:
      manifests:
        - manifest:
            identifier: k8s_manifests
            type: K8sManifest
            spec:
              store:
                type: HarnessCode
                spec:
                  repoName: demo-banking-api
                  gitFetchType: Branch
                  branch: main
                  paths:
                    - k8s/base/deployment.yaml
              skipResourceVersioning: false
              enableDeclarativeRollback: false
        - manifest:
            identifier: values
            type: Values
            spec:
              store:
                type: HarnessCode
                spec:
                  repoName: demo-banking-api
                  gitFetchType: Branch
                  branch: main
                  paths:
                    - k8s/base/values.yaml
      artifacts:
        primary:
          primaryArtifactRef: primary
          sources:
            - identifier: harnessartifactregistry
              type: Har
              spec:
                registryRef: banking-api
                type: docker
                spec:
                  imagePath: demo-banking-api
                  tag: <+input>
                  digest: ""
```

#### Service: `fx_rates_api`

```yaml
service:
  name: fx-rates-api
  identifier: fx_rates_api
  serviceDefinition:
    type: Kubernetes
    spec:
      manifests:
        - manifest:
            identifier: k8s_manifests
            type: K8sManifest
            spec:
              store:
                type: HarnessCode
                spec:
                  repoName: fx-rates-api
                  gitFetchType: Branch
                  branch: main
                  paths:
                    - k8s/base/deployment.yaml
              skipResourceVersioning: false
              enableDeclarativeRollback: false
        - manifest:
            identifier: values
            type: Values
            spec:
              store:
                type: HarnessCode
                spec:
                  repoName: fx-rates-api
                  gitFetchType: Branch
                  branch: main
                  paths:
                    - k8s/base/values.yaml
      artifacts:
        primary:
          primaryArtifactRef: primary
          sources:
            - identifier: harnessartifactregistry
              type: Har
              spec:
                registryRef: account.fx-rates
                type: docker
                spec:
                  imagePath: fx-rates-api
                  tag: <+input>
                  digest: ""
```

> **`registryRef: account.fx-rates`** — the `account.` prefix is required because the `fx-rates` HAR registry is at account scope. Using `registryRef: fx-rates` (without the prefix) causes a 400 error at the CD service step because Harness looks for a project-level connector that doesn't exist.

### 2.6 Pipelines

Use Claude (or the MCP harness tools) to create the pipelines. Both use the account-level templates created in Section 1.6.

**demo-banking-api pipeline** — ask Claude:
```
Create a Harness pipeline called demo-banking-api that uses the account-level CI/CD templates.
For CI: use account.ci_build_test with serviceRepo=demo-banking-api and registryRef=banking-api.
For CD: deploy to dev first (use the dev environment and dev_k8s infrastructure, namespace=banking-dev),
then a production approval gate, then deploy to production (prod_k8s, namespace=banking-prod).
Tag the artifact with the pipeline sequence ID.
```

**fx-rates-api pipeline** — ask Claude:
```
Create a Harness pipeline called fx-rates-api that uses the account-level CI/CD templates.
For CI: use account.ci_build_test with serviceRepo=fx-rates-api and registryRef=fx-rates.
For CD: deploy to dev first (use the dev environment and dev_k8s infrastructure, namespace=fx-rates-dev),
then a production approval gate, then deploy to production (prod_k8s, namespace=fx-rates-prod).
Tag the artifact with the pipeline sequence ID.
```

---

## 3. Kubernetes Cluster Bootstrap

Harness creates a release-tracking ConfigMap in the target namespace **before** applying any manifests — the namespace must pre-exist. All namespaces also need `harness-registry-secret` to pull images from `pkg.harness.io`.

### 3.1 Create namespaces

```bash
kubectl create namespace banking-dev
kubectl create namespace banking-prod
kubectl create namespace fx-rates-dev
kubectl create namespace fx-rates-prod
```

### 3.2 Create the image pull secret

Harness injects `harness-registry-secret` into the first namespace it deploys to. Copy it to all other namespaces:

```bash
# Run Scenario 1 through dev deploy first so Harness injects the secret into banking-dev.
# Then copy it to the other namespaces:

for NS in banking-prod fx-rates-dev fx-rates-prod; do
  kubectl get secret harness-registry-secret -n banking-dev -o json \
    | python3 -c "
import sys, json
d = json.load(sys.stdin)
d['metadata']['namespace'] = '${NS}'
del d['metadata']['resourceVersion']
del d['metadata']['uid']
del d['metadata']['creationTimestamp']
print(json.dumps(d))
" | kubectl apply -f -
done
```

> Alternatively, create the secret directly using your Harness API token (see Harness docs → Artifact Registry → Pull Secrets).

---

## 4. MCP Server Setup

The demo uses the Harness MCP server to let Claude interact with Harness via natural language.

### 4.1 Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

### 4.2 Configure MCP in Claude Code settings

Add to `~/.claude.json` (or via `claude mcp add`):

```json
{
  "mcpServers": {
    "harness": {
      "command": "npx",
      "args": ["-y", "@harness/mcp-server"],
      "env": {
        "HARNESS_API_KEY": "<your-harness-api-key>",
        "HARNESS_ACCOUNT_ID": "<your-account-id>",
        "HARNESS_DEFAULT_ORG": "default",
        "HARNESS_DEFAULT_PROJECT": "claude"
      }
    }
  }
}
```

Generate a Harness API key at Account Settings → API Keys.

### 4.3 Start Claude Code

```bash
cd /path/to/demo-banking-api
claude
```

---

## 5. Demo Reset Between Runs

### Scenario 1 reset

Revert the transaction endpoint so the feature-addition story works again:

```
Revert the account transaction endpoint commit and push to main.
```

### Scenario 2 reset

Delete only the pipeline (leave service, registry, and repo intact):

```
Delete the fx-rates-api pipeline from Harness.
```

Then recreate it with the one-sentence prompt in Section 2.6.

---

## 6. Known Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| `claude --print` exits 1, fails CI | Anthropic API credits exhausted | Add `\|\| true` to the `claude --print` line in `ci_build_test` template |
| HarnessSCA: "manifest unknown" pulling `:latest` | Build and Push only pushes sequenceId tag, not `latest` | Add `latest` to the `tags` list in the Build and Push step |
| HarnessSCA scans wrong image tag | `detection: auto` always resolves to `latest` regardless of `image.tag` | Set `detection: manual` with `name: <+stage.variables.serviceRepo>` and `variant: <+pipeline.sequenceId>` |
| CD service step: "Invalid format of YAML payload (400)" | `registryRef` in service definition doesn't match registry scope | Use `registryRef: account.fx-rates` for account-level HAR; `registryRef: banking-api` for project-level |
| Template change has no effect on re-run | Retried executions use frozen YAML from original run | Always trigger a **fresh run** after changing a template, never use Retry |
| K8s deploy fails: namespace not found | Harness tries to create release ConfigMap in non-existent namespace | Pre-create all namespaces before the first deploy (Section 3.1) |
| Image pull fails in pod | `harness-registry-secret` missing in namespace | Copy secret from `banking-dev` after first successful dev deploy (Section 3.2) |
| Cannot edit account-level template via MCP | MCP server only reaches project-level resources | Edit account templates manually in Harness UI (Account Settings → Templates) |

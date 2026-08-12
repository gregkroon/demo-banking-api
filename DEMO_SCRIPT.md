# Harness + Claude Code — Demo Script

**Theme:** Harness governs both intent and delivery. Claude can act as the developer's AI pair programmer and platform interface, while Harness templates, AI agents, policy, approvals, security scanning, and software supply-chain controls provide the guardrails from requirement through production.

**Runtime:** ~20 minutes total. For the banking feature, choose **Scenario 1A (developer-led with Claude Code)** or **Scenario 1B (spec-driven development with Jira + Harness human-in-the-loop)**, then continue to Scenario 2 if time allows.

---

## Setup Checklist (before the demo)

### Codebase

Create a folder on the laptop called `aidemo`, change directory to it, then clone the demo repositories:

```bash
git clone https://git.harness.io/EeRjnXTnS4GrLG5VNNJZUw/default/apac_ai_demo/demo-banking-api.git
git clone https://git.harness.io/EeRjnXTnS4GrLG5VNNJZUw/default/apac_ai_demo/fx-rates-api.git
git clone https://git.harness.io/EeRjnXTnS4GrLG5VNNJZUw/default/apac_ai_demo/gosample.git
```

### Claude setup

```bash
export HARNESS_API_KEY='pat.xxxxxxx'
export HARNESS_ACCOUNT_ID='EeRjnXTnS4GrLG5VNNJZUw'
export HARNESS_ORG='default'
export HARNESS_PROJECT='apac_ai_demo'
```

### Add Harness MCP

```bash
claude mcp add harness -- npx harness-mcp-v2
```

### Run Claude Code

Run Claude Code from the root of `aidemo`:

```bash
claude
```

### One-time banking demo baseline

Put `demo-banking-api/main` into the exact pre-feature state you want for every demo:

- Existing `GET /transactions` route is present.
- `GET /accounts/<account_id>/transactions` is absent.
- `.aisdlc/Features.md` is absent.
- Working tree is clean.

Create the baseline tag once:

```bash
cd ~/aidemo/demo-banking-api
git checkout main
git pull
git status
git tag demo-baseline
git push origin demo-baseline
```

Do not recreate the tag between demos. Use it as the reset point.

### Additional setup for Scenario 1B — Spec-Driven Development

Pre-stage the following before the demo:

- An **existing open Jira Item** in project `KANB`, e.g. `KANB-X`, titled **Add per-account transaction history to the Banking API**.
- The Jira Item already describes the new per-account transaction-history capability and lists Mobile Banking, Customer Support, and Compliance/Audit as consumers.
- Jira global webhook is configured for **Comment created** and points to the Harness custom webhook for `Banking Feature Spec Generator`.
- The spec pipeline uses:
  - `banking_feature_ingester_agent`
  - `banking_commit_feature_file`
  - `banking_harness_pr_author`
- The `Wait for Response` stage remains enabled as a fallback when `features_ready == false`.
- The existing `demo-banking-api` delivery pipeline remains unchanged.

For the optional automatic handoff after the implementation PR merges, configure a Harness Code **Push** trigger on `demo-banking-api`:

- Branch: `main`
- Application changes only, for example changed-file regex:

```text
^(app/.*|tests/.*|requirements.*|Dockerfile)$
```

This means a spec-only merge under `.aisdlc/**` does **not** start CI/CD, while an implementation merge does. Manual/console execution still works for Scenario 1A.

For repeated demos, prepare several identical open Jira Items (`KANB-X`, `KANB-Y`, etc.) and use a fresh one each time rather than trying to clean comment history.

---

## Scenario 1A — Day in the Life: Shipping a Feature with Claude Code

**Use this OR Scenario 1B.**

**Story:** A developer wants to add per-account transaction history to the banking API. They use Claude to write the code and get it to production — without touching the Harness UI once.

### Step 1 — Give Claude the feature request

Type in the Claude terminal:

```
Add a GET /accounts/<account_id>/transactions endpoint to the banking API.
It should return only transactions where that account is either the sender
or receiver. Add a test for it. Then commit and push to main.
```

**What Claude does:**
- Reads `app/main.py` and `tests/test_api.py` to understand the existing patterns
- Adds the endpoint after the existing `/accounts/<account_id>/balance` route:
  ```python
  @app.route("/accounts/<account_id>/transactions", methods=["GET"])
  @require_auth
  def account_transactions(account_id):
      if account_id not in ACCOUNTS:
          return jsonify({"error": "Account not found"}), 404
      txs = [t for t in TRANSACTIONS if t["from"] == account_id or t["to"] == account_id]
      return jsonify({"account_id": account_id, "transactions": txs, "count": len(txs)}), 200
  ```
- Adds a test covering the 200 and 404 cases
- Commits: `git commit -m "feat: add per-account transaction history endpoint"`
- Pushes to main

**Talking point:** *"The developer described what they wanted in plain English. Claude read the existing code, matched the patterns, wrote the test, and pushed — all without the developer opening a file."*

---

### Step 2 — Trigger the pipeline

Still in Claude:

```
Trigger the demo-banking-api pipeline on the main branch and watch it for me.
```

**What Claude does:**
- Calls `harness_execute` on `demo_banking_api` with `branch: main`
- Confirms: *"Pipeline run #N started. Monitoring..."*

**What to show in Harness UI:**
- Switch to the execution view — four stages appear: Build and Test, Deploy to Dev, Production Approval, Deploy to Production
- All grey/pending except Build and Test which turns blue/running

**Talking point:** *"One sentence. The pipeline is running. The developer doesn't know or care what's in it — and that's the point."*

---

### Step 3 — The guardrails run automatically (~3 minutes)

While the CI stage runs, narrate what's happening under the hood (visible in Harness execution logs):

| Step | What it does | Why it matters |
|------|-------------|----------------|
| Run Unit Tests | pytest with JUnit report | Catches regressions |
| Claude Code Coverage Check | Claude evaluates coverage %, writes a verdict | AI quality gate — not just a number |
| Build and Push to HAR | Docker build → `banking-api/demo-banking-api:<N>` | Immutable artifact |
| HarnessSCA | Container vulnerability scan | Flags CVEs before they reach prod |
| Generate SBOM | Syft generates software bill of materials, cosign attests it | Audit trail, supply chain compliance |

**The money moment — show the coverage check logs:**

```
=== Claude Code Coverage Check ===
Coverage: 87.3% (54/62 lines)

The demo-banking-api project maintains strong test coverage at 87.3%, 
comfortably exceeding the 80% threshold. The new account transaction 
endpoint is fully covered by the added test cases.

Verdict: PASS
```

**Talking point:** *"That's Claude — running inside the pipeline — reading the coverage report and writing a plain-English assessment. Not just a red/green number, but context a developer actually understands."*

---

### Step 4 — Dev deployment succeeds

Build and Test goes green. Deploy to Dev starts automatically.

**In Harness UI:** Show the CD stage — service `demo-banking-api`, artifact tag `<N>`, deploying to `dev_k8s` in the `banking-dev` namespace.

Ask Claude:

```
What's the current status of the pipeline?
```

Claude responds with the stage summary: Build ✅, Dev Deploy ✅, Approval ⏳

**Talking point:** *"The developer can ask Claude for a status update at any time — they don't need to watch a dashboard."*

---

### Step 5 — The production approval gate

Pipeline hits the Production Approval stage and pauses.

**What Claude reports:**

```
The pipeline has passed dev deployment and is now waiting for production approval.

Build #<N> is pending sign-off:
- Service: demo-banking-api  
- Artifact: pkg.harness.io/.../demo-banking-api:<N>
- Requires: a different user to approve (pipeline executor restriction enforced by OPA)
- Requires: a change ticket number

The pipeline cannot proceed until someone else approves.
```

**Switch to Harness UI** — show the approval gate. A second person (or second browser tab) opens the approval, enters a change ticket (e.g. `CHG-2024-001`), and clicks Approve.

**Talking point:** *"Two things just happened automatically — OPA blocked the developer from approving their own deployment, and the change ticket field was required. Neither of those are config. They're policies, enforced by the template, for every service that uses it."*

---

### Step 6 — Production deployment

Approval granted → Deploy to Production runs → succeeds.

Ask Claude:

```
What image is now running in production?
```

Claude: *"Image `pkg.harness.io/.../demo-banking-api:<N>` is deployed to `banking-prod`. Build #<N>, pushed from commit `feat: add per-account transaction history endpoint`."*

**Close the loop:** *"From a one-sentence feature request to production — unit tested, security scanned, SBOM attested, human approved — in under 10 minutes. The developer wrote zero pipeline config."*

---

## Scenario 1B — Spec-Driven Development: Jira → Human-in-the-Loop → Spec → Code → Production

**Use this OR Scenario 1A.**

**Story:** The feature already exists in Jira. A new Compliance decision arrives as a comment. Instead of sending the ticket directly to a coding agent, Harness first reconciles the requirement, detects anything a developer would otherwise have to guess, brings a human in for material decisions, and produces a version-controlled implementation contract. Only then is code written and delivered through the existing banking CI/CD pipeline.

**Core message:** *"AI can reason about the requirement, but it does not get to invent the requirement."*

---

### Step 1 — Start with the existing Jira feature

Open the pre-created Jira Item, e.g. `KANB-X`:

**Add per-account transaction history to the Banking API**

Briefly show that the existing feature already says:

- Add per-account transaction history.
- Only return transactions where the account is sender or receiver.
- Use existing authentication.
- Unknown account returns HTTP 404.
- Mobile Banking, Customer Support, and Compliance/Audit are consumers.
- Customer-facing transaction information should be current.
- Existing compliance/audit reporting must continue.

**Talking point:** *"This is where development normally starts — an existing feature in Jira. It looks reasonable, but the key question is whether it is precise enough to safely hand to an AI coding agent."*

---

### Step 2 — Add the new Compliance decision

Add this Jira comment:

```text
After talking to Compliance, we actually need the customer-facing
transaction API to use current real-time data, but Compliance needs
the existing 24-hour-old batch data for the audit feed.

The new API must not replace or change the existing audit feed.

So the freshness requirement is different per consumer and this
needs to be reflected in the design.
```

Save the comment.

**Talking point:** *"I am not copying this into a coding prompt. I update the requirement where the business already works — Jira."*

**What happens:**

```text
Jira comment created
        ↓
Custom webhook
        ↓
Banking Feature Spec Generator
        ↓
Feature Ingester Agent
```

Switch to the Harness execution.

---

### Step 3 — Show the agent reconciling the requirement

Open:

**Generate → Feature Ingester Agent**

The agent should understand that the data-freshness ambiguity is now resolved:

```text
Mobile Banking / Customer Support
→ current / real-time transaction data

Compliance / Audit
→ existing 24-hour batch feed

New API
→ must not replace or modify the audit feed
```

A useful agent summary is:

> **Capability summary:** KANB-X adds a new real-time per-account transaction history endpoint to the Banking API for customer-facing consumers, while leaving the existing 24-hour batch Compliance audit feed completely unchanged. The data-freshness ambiguity is resolved by the Jira comment — two separate data paths, no shared pipeline.

**Talking point:** *"The agent is not processing the new comment in isolation. It is reconciling the new decision with the original feature and the existing constraints."*

---

### Step 4 — The human-in-the-loop moment

The agent may still set:

```text
features_ready=false
```

because the Jira feature says **what capability is wanted**, but does not define enough of the API contract for a developer to implement without making product or architecture decisions.

The agent may produce a summary such as:

> The spec is blocked (`features_ready=false`) because the API contract — endpoint shape, request/response schema — and the authentication/authorization mechanism were not sufficiently specified in Jira, and a developer would need to make material product decisions to fill those gaps.

Harness moves to:

**Wait for Response → Ask**

The approval question should be similar to:

> What is the API contract for the new transaction history endpoint: endpoint path, HTTP method, account identifier parameter, response schema, pagination approach, and the authentication/authorization mechanism callers must use?

**Talking point:** *"This is not the human doing the agent's work. The agent has identified a decision it is not authorised to make."*

Then:

> *"Without this gate, a coding agent could simply pick an endpoint, invent a response schema and choose a pagination model. It would look productive, but we would be encoding assumptions directly into code."*

**Key line:** *"AI can infer context, but it cannot silently become the product owner or architect."*

---

### Step 5 — Human provides the missing API contract

Click **Approve or Reject** and provide this response:

```text
Use GET /accounts/{account_id}/transactions.

account_id is the existing account ID string.

For HTTP 200 return a JSON object containing:
- account_id: string
- transactions: array using the same transaction object schema already returned by GET /transactions
- count: integer

No pagination is required for v1.

Use the same authentication and authorization mechanism already used by the existing Banking API account and transaction endpoints.

An unknown account ID must return HTTP 404.
```

Click **Approve**.

**Talking point:** *"The human is not approving AI output here. The human owns the missing intent. We make the product decision once and capture it explicitly."*

---

### Step 6 — Harness writes the decision back to Jira and reruns

The next step is `JiraUpdate`.

Harness writes the human response back to the Jira Item as a comment. Because Jira is configured for **Comment created**, that update starts a second execution of `Banking Feature Spec Generator`.

```text
Human answer in Harness
        ↓
JiraUpdate
        ↓
Decision stored in Jira
        ↓
Comment-created webhook
        ↓
Feature Ingester reruns
```

**Talking point:** *"The decision is not buried in an AI chat or pipeline log. It goes back into Jira, so the requirement system remains the source of truth."*

On the second run, show that the agent now has:

```text
Business ambiguity resolved       ✅
API contract resolved             ✅
Authentication behavior resolved  ✅
features_ready=true               ✅
```

**Talking point:** *"The agent now has enough information for implementation without asking a developer to make a material product decision."*

---

### Step 7 — Generate and commit the specification

With `features_ready=true`, the pipeline runs:

```text
Open PR
  ├── Commit File
  └── Raise PR
```

Open **Commit File** and show outputs similar to:

```text
SOURCE_BRANCH=aisdlc/KANB-X
COMMIT_STATUS=SUCCESS
COMMIT_SHA=<sha>
```

The generated specification is committed to the existing repository:

```text
demo-banking-api
└── .aisdlc/
    └── Features.md
```

on source branch:

```text
aisdlc/KANB-X
```

**Talking point:** *"Once the requirement is coherent, Harness turns it into a version-controlled engineering artifact."*

---

### Step 8 — Review the spec PR

Open the Harness Code PR:

```text
aisdlc/KANB-X → main
```

Show only the important sections in `.aisdlc/Features.md`:

1. **API Contract** — `GET /accounts/{account_id}/transactions`.
2. **Consumer-Specific Requirements** — customer-facing real-time data vs Compliance 24-hour batch.
3. **Decisions and Clarifications** — the human decisions are explicitly recorded.
4. **Out of Scope** — the new API does not replace or modify the audit feed.

**Talking point:** *"This is the transformation: the Jira conversation has become a reviewable engineering contract."*

Then:

> *"The business requirement, the human decisions and the acceptance criteria are now version-controlled just like code."*

Merge the spec PR.

**Talking point:** *"AI proposes the implementation contract. A human accepts it."*

**Important:** The spec-only merge should **not** start `demo-banking-api` CI/CD because the delivery trigger is scoped to application-code changes and excludes `.aisdlc/**`.

---

### Step 9 — Implement against the accepted specification

Pull the merged specification locally:

```bash
cd ~/aidemo/demo-banking-api
git checkout main
git pull
cat .aisdlc/Features.md
```

Start Claude Code in the repository and use:

```text
Implement KANB-X using the accepted feature specification in
.aisdlc/Features.md.

Read the specification before making any changes.
Do not modify the accepted specification.
Implement the API behaviour and acceptance criteria exactly as specified.
Do not change or replace the existing Compliance audit behaviour.
Add the required tests.

Create an implementation branch feature/KANB-X, commit and push the changes,
and raise a pull request to main. Do not merge the PR.
```

**Talking point:** *"Now we are ready for coding AI, but Claude is no longer deciding what the feature means. That decision happened upstream."*

Then:

> *"Claude's job is implementation against an accepted contract."*

---

### Step 10 — Review and merge the implementation PR

Open the implementation PR:

```text
feature/KANB-X → main
```

Show that the implementation changes are primarily:

```text
app/main.py
tests/test_api.py
```

and that `.aisdlc/Features.md` has not been rewritten by the coding agent.

Approve and merge the implementation PR.

**Talking point:** *"The spec PR authorised engineering intent. This PR reviews the implementation of that intent."*

---

### Step 11 — Existing CI/CD starts automatically

The merge changes `app/**` and/or `tests/**` on `main`, so the Harness Code push trigger starts the existing:

```text
demo-banking-api
```

pipeline automatically.

Show:

```text
Build and Test
      ↓
Deploy to Dev
      ↓
Production Approval
      ↓
Deploy to Production
```

**Talking point:** *"From this point onwards, nothing changes. Spec-driven development governs what we are building. The existing delivery platform governs how that implementation reaches production."*

This automatic trigger is additive: Scenario 1A can still start the exact same pipeline manually from Claude or the Harness console.

---

### Step 12 — The delivery guardrails run

Use the same CI/CD narration as Scenario 1A:

| Step | What it does | Why it matters |
|------|-------------|----------------|
| Run Unit Tests | pytest with JUnit report | Catches regressions |
| Claude Code Coverage Check | Claude evaluates coverage and writes a verdict | AI quality gate with context |
| Build and Push to HAR | Builds immutable container artifact | Traceable artifact |
| HarnessSCA | Container vulnerability scan | Security before production |
| Generate SBOM | Syft + cosign attestation | Supply-chain evidence |

**Talking point:** *"We now have two layers of control: the specification helps ensure we are building the right thing; CI, security and governance help ensure we are building and releasing the thing right."*

---

### Step 13 — Production approval and deployment

At the Production Approval stage, enter the normal change ticket and approve using the standard demo process.

**Talking point:** *"Notice that we have had different human decisions for different reasons. Earlier, a human resolved what the requirement meant. Here, release governance decides whether this particular artifact is authorised for production."*

Let production deployment complete.

**Close the loop:**

> *"We can trace this feature from the original Jira requirement, through explicit human decisions, into a version-controlled specification, through implementation, tests, security evidence, artifact and finally production."*

> *"AI accelerated the lifecycle, but it never became the authority."*

---

### Scenario 1B condensed click path

```text
Existing Jira Item
      ↓
Add Compliance comment
      ↓
Banking Feature Spec Generator
      ↓
Feature Ingester
      ↓
Human-in-the-loop clarification if required
      ↓
JiraUpdate → automatic rerun
      ↓
Features.md
      ↓
Spec PR → review → merge
      ↓
Claude implements accepted spec
      ↓
Implementation PR → review → merge
      ↓
Automatic demo-banking-api CI/CD
      ↓
Build/Test/Security → Dev → Prod Approval → Prod
```

**Best single-line message:** *"AI can reason about the requirement, but it does not get to invent the requirement."*

---

## Scenario 2 — New Service Onboarding with Account Templates

**Story:** A new team has already built their microservice — an FX Rates API — and pushed it to a Harness Code repo. The code is there, the Harness service and artifact registry are pre-configured. All they need is a pipeline. They ask Claude to wire it up using the account-level templates. Every delivery guardrail from Scenario 1A/1B applies automatically — without the team knowing or caring what's in those templates.

**Why this matters:** The templates aren't just for the banking API. They're platform-wide guardrails. Any team, any service, same governance — with zero pipeline-writing required.

**Pre-setup (before the demo):**
- Harness Code repo `fx-rates-api` — code already pushed (Flask app, Dockerfile, k8s manifests, tests)
- HAR registry `fx-rates-api` — already created
- Harness service `fxratesapi` — already configured (K8sManifest + HAR artifact source, identifier uses lowercase without separators)
- K8s namespaces `fx-rates-dev` and `fx-rates-prod` pre-created with `harness-registry-secret`

---

### Step 1 — Show the team what already exists

In Harness UI, briefly show:
- **Code** → `fx-rates-api` repo — the code is there
- **Services** → `fxratesapi` — service defined (note: identifier is lowercase without separators), artifact source wired
- **Account Templates** → `claude` project — `ci_build_test`, `cd_k8s_rolling`, `production_gate`

**Talking point:** *"The team built the service. The platform team has already defined the standards as templates at the account level. The only missing piece is a pipeline — and that's what we're going to create now, in one sentence."*

---

### Step 2 — Ask Claude to create the pipeline

In the Claude terminal:

```
Create a Harness pipeline called fx-rates-api that uses the project-level CI/CD templates.
For CI: use ci_build_test with serviceRepo=fx-rates-api and registryRef=fx-rates-api.
For CD: deploy to dev first (use the dev environment and dev_k8s infrastructure, namespace=fx-rates-dev),
then a production approval gate, then deploy to production (prod_k8s, namespace=fx-rates-prod).
Tag the artifact with the pipeline sequence ID.
```

**What Claude does:**
- Calls `harness_create` for a new pipeline
- Wires in `ci_build_test`, `cd_k8s_rolling`, `production_gate` templates with the correct `templateInputs`
- Sets `<+pipeline.sequenceId>` as the artifact tag throughout
- **Important:** Uses `serviceRef: fxratesapi` (lowercase, no separators) to match the actual service identifier in Harness
- Confirms: *"Pipeline fx-rates-api created — 4 stages using account-level templates."*

**Show in Harness UI:** Open the new pipeline — four stages, identical structure to demo-banking-api.

**Talking point:** *"Look at this pipeline. It's structurally identical to the banking API pipeline — because it uses the same account-level templates. The fx-rates team automatically gets unit tests, Claude coverage check, STO scanning, SBOM attestation, and the production approval gate. They didn't ask for any of it. It came with the template."*

**Note on service naming:** Harness service identifiers use lowercase without separators (fx-rates-api → fxratesapi). If Claude encounters a "service not found" error, it will automatically correct the serviceRef and save this pattern to memory for future pipeline creation.

---

### Step 3 — Run the pipeline

```
Run the fx-rates-api pipeline on main and monitor it.
```

**What Claude does:**
- Calls `harness_execute` on `fx_rates_api` with `branch: main`
- Confirms: *"Pipeline run #1 started. Monitoring..."*

Pipeline executes end-to-end — same flow as Scenario 1. Show it reaching the approval gate.

**Talking point:** *"Same four stages. Same security gates. Same approval requirement. The fx-rates team got all of this for free — by using the template."*

---

### Step 4 — The approval gate (same as Scenario 1)

Pipeline pauses at Production Approval. A second person approves in the Harness UI, enters a change ticket, clicks Approve.

**Closing talking point:**

*"Two services. Two teams. Zero pipeline YAML written by either developer. Same security posture, same governance, same audit trail — because the templates encode your organisation's standards. That's the platform team's job done once, applied everywhere."*

---

## Key Talking Points (across the core scenarios)

| What the audience sees | What to say |
|------------------------|-------------|
| Jira comment starts spec workflow | "The developer does not have to translate business context into an AI prompt — the workflow starts from the system of record." |
| Agent sets `features_ready=false` | "AI can identify ambiguity, but it cannot silently become the product owner or architect." |
| Human-in-the-loop clarification | "This is human ownership of intent, not human approval of AI output." |
| Human decision written back to Jira | "The decision remains in the source-of-truth system, not buried in an AI conversation." |
| `Features.md` spec PR | "A conversation has become a version-controlled implementation contract." |
| Claude implements accepted spec | "The coding agent implements a decision; it does not make the decision." |
| Claude manually triggers pipeline in Scenario 1A | "The developer's interface is a conversation. The platform is the implementation." |
| Code merge automatically triggers pipeline in Scenario 1B | "Intent governance hands off cleanly into the same standardized delivery system." |
| Claude Code coverage check in logs | "AI isn't just writing the code — it's reviewing it too, with context, not just a number." |
| OPA blocks self-approval | "Governance isn't a checkbox. It's enforced at the platform layer, for every run, without developer configuration." |
| New pipeline uses same templates | "One set of guardrails. Every service. The platform team wrote it once." |
| SBOM with cosign attestation | "You have a signed, auditable software bill of materials for every image that reaches production." |
| `<+pipeline.sequenceId>` as tag | "Every build is traceable. You can always answer: what exact code is running in production right now?" |

---

## Failure Scenarios (optional, for deeper demos)

### CVE Block
Before running: add `cryptography==38.0.0` to `requirements.txt` (known critical CVE).
- STO scan flags it
- OPA `image_security_policy` blocks the pipeline run
- Claude reports: *"Pipeline blocked — critical CVE in cryptography package. Upgrade to >=42.0.5."*
- Fix the version, re-run, succeeds

### Coverage Drop
Before running: delete the new test.
- Claude Code coverage check drops below 80%
- Claude writes: *"Coverage is 71.2% — below the 80% threshold. FAIL."*
- Step exits 1, pipeline fails at CI
- Add the test back, re-run

### Change Window Violation (bonus)
- OPA `change_window_policy` warns if deployment is outside Mon-Fri 08:00-17:00 AEST
- Demonstrate by running outside hours — warning appears on the approval gate message

---

## Scenario 3 — Release Readiness Assessment with Harness AI

**Note:** Scenarios 3-7 demonstrate Harness platform AI capabilities directly in the Harness UI, separate from the Claude Code development workflows in Scenarios 1-2.

**Story:** A release manager needs to decide whether a build is ready for production. Instead of manually checking multiple dashboards, they use Harness AIDA (AI Development Assistant) to perform a comprehensive readiness assessment.

### Step 1 — Use Harness AIDA for release assessment

In the Harness UI, open the pipeline execution and click the **AIDA** button:

Ask AIDA:
```
Review this release for production readiness. Check build status, tests, approvals, security scans, policy violations, deployment history, rollback readiness, change ticket quality, and observability coverage. Give a go/no-go recommendation.
```

**What Harness AIDA does:**
- Analyzes the current pipeline execution across all stages
- Reviews test results, coverage metrics, and STO findings
- Checks approval history and change ticket details
- Evaluates policy compliance (OPA evaluations)
- Assesses SBOM completeness and attestation
- Provides a structured go/no-go recommendation with reasoning directly in the UI

**Talking point:** *"This is Harness AI as a release manager's co-pilot. AIDA just reviewed 8 different aspects of production readiness — things that would normally require opening multiple tabs — and gave you a single recommendation with evidence, all within the Harness platform."*

---

## Scenario 4 — AI-Generated Pipeline with Harness AIDA

**Story:** A developer has a Go microservice in a Harness Code repo and needs a complete CI/CD pipeline. Instead of copying YAML or clicking through the UI, they use Harness AIDA in the Pipeline Studio to generate the pipeline from a natural language description.

### Step 1 — Create the pipeline with Harness AIDA

In the Harness UI, navigate to **Pipelines** → **Create New Pipeline** → **Use AI Assistant**

Provide AIDA with the requirements:

```
Create a Harness pipeline for org default and project apac_ai_demo with name and identifier gosampleapp. Add tag ai_generated: "true".

Codebase configuration:
- repoName: gosample
- build: runtime input (<+input>)
- sparseCheckout: empty array

Stage 1 - CI Stage:
- Name and identifier: build
- Clone codebase: enabled
- Platform: Linux/Amd64
- Runtime: Cloud
- Step: BuildAndPushDockerRegistry
  - identifier: build_and_push_docker
  - name: Build and Push Docker
  - No connectorRef use registryRef
  - registryRef: gosampleapp
  - repo: gosample
  - tags: [latest]
  - dockerfile: Dockerfile
  - context: .
  - caching: false
  - timeout: 10m
- Failure strategy: MarkAsFailure on all errors

Stage 2 - CD Stage:
- Name and identifier: deploy
- Deployment type: Kubernetes
- Service: goapp with Kubernetes service definition
- Artifact inputs: primaryArtifactRef and sources as runtime inputs (<+input>)
- Environment: dev
- Infrastructure: dev
- Execution step: K8sRollingDeploy
  - identifier: k8s_rolling_deploy
  - name: K8s Rolling Deploy
  - skipDryRun: false
  - pruningEnabled: false
  - timeout: 10m
- Rollback step: K8sRollingRollback
  - identifier: k8s_rolling_rollback
  - name: k8s_rolling_rollback
  - pruningEnabled: false
  - timeout: 10m
- Failure strategy: StageRollback on all errors
```

**What Harness AIDA does:**
- Parses the natural language requirements
- Generates complete pipeline YAML with proper Harness schema
- Creates both CI and CD stages with correct step configuration
- Sets up failure strategies and rollback logic
- Displays the generated pipeline in the visual editor

**Show in Harness UI:** Review the generated pipeline — two stages with proper configuration, tagged with `ai_generated: true`.

**Talking point:** *"The developer described what they wanted in plain English. Harness AIDA translated it into 200+ lines of pipeline YAML — with proper schema, failure strategies, and rollback logic. No docs, no templates, just natural language in the Pipeline Studio."*

---

### Step 2 — Enhance the pipeline with security and approvals

In the Pipeline Studio, use AIDA again to modify the pipeline:

```
Modify the gosampleapp pipeline to add security scanning and an approval gate before deployment:

Add a Semgrep security scan step as the first step in the build stage:
- Use orchestration mode with default config
- Target type: repository with auto detection
- Log level: info

Add an Approval stage between the build and deploy stages:
- Use HarnessApproval step with 1 day timeout
- Require minimum 1 approver from account._account_all_users
- Include pipeline execution history in the approval message
- Allow pipeline executor to approve
- Disable auto-reject
```

**What Harness AIDA does:**
- Reads the current pipeline configuration
- Adds Semgrep step at the beginning of the build stage
- Inserts a new Approval stage between build and deploy
- Configures HarnessApproval with specified approver group and timeout
- Updates the visual pipeline editor with the changes

**Talking point:** *"The pipeline just evolved. Security scanning and human approval gates were added with a natural language request in the Harness UI — no YAML editing, no reading docs about Semgrep configuration."*

---

## Scenario 5 — Test Intelligence and PR-Based Security Scanning

**Story:** Demonstrate Harness's intelligent testing and security features.

### Step 1 — Test Intelligence in action

In the Harness UI, open the e2e pipeline execution with Test Intelligence enabled.

**What to show in Harness UI:**
- Test Intelligence dashboard showing only changed tests running
- Time savings compared to full test suite
- Test selection visualization

**Talking point:** *"Test Intelligence automatically identifies which tests are affected by code changes. Instead of running 100% of tests on every commit, you run the 15% that actually matter — cutting CI time by 5x."*

---

### Step 2 — STO on Pull Requests

In Harness Code, open a pull request that adds a dependency with a known vulnerability.

**What to show in Harness UI:**
- PR pipeline triggered automatically
- STO scan runs and detects the vulnerability
- PR check fails with security finding details
- Inline comment on the PR with remediation guidance

**Talking point:** *"Security scanning isn't just for main branch. Every PR gets scanned before merge. The security gate is at code review time, not deployment time."*

---

## Scenario 6 — Continuous Verification and Auto-Rollback

**Story:** A deployment goes to production but causes a latency spike. Harness CV detects the anomaly and automatically rolls back.

### Step 1 — Show CV configuration

In the Harness UI, navigate to the banking API production deployment and open the Continuous Verification configuration.

**What to show in Harness UI:**
- CV configured with Prometheus/Datadog metrics
- Health sources monitoring latency, error rate, throughput
- Anomaly detection thresholds

---

### Step 2 — Trigger a deployment with CV

Deploy a version that intentionally causes issues (simulated or pre-staged).

**What happens:**
- Deployment completes
- CV verification phase begins (5-10 minute window)
- Metrics show anomaly (latency spike)
- CV marks deployment as unhealthy
- Auto-rollback triggers
- Previous version restored

**Show in Harness UI:**
- CV verification timeline with red anomaly markers
- Auto-rollback execution logs
- Service restored to previous stable version

**Talking point:** *"This is closed-loop automation. Harness deployed it, monitored it, detected the problem, and fixed it — all without human intervention. The developer's code never reached users in a broken state."*

---

## Scenario 7 — OPA Policy AI Assistant with Harness AIDA

**Story:** A developer's pipeline is blocked by an OPA policy. Instead of reading Rego code or asking the platform team, they use Harness AIDA to understand why.

### Step 1 — Policy violation

Trigger a pipeline that violates a policy (e.g., missing SBOM, change window violation, critical CVE).

**Pipeline fails** with: *"Policy evaluation failed: Image Security Policy"*

---

### Step 2 — Use Harness AIDA to explain the policy failure

In the failed pipeline execution view, click the **AIDA** button and ask:

```
Why did my pipeline fail the policy check?
```

**What Harness AIDA does:**
- Reads the policy evaluation results from the execution
- Analyzes the specific Rego rules that failed
- Translates the policy logic into plain English
- Provides specific remediation steps directly in the UI

**Harness AIDA responds:**
```
Your pipeline was blocked by the "Image Security Policy" in the "Image Security" policy set.

Failed rule: "SBOM required policy"
Reason: The Docker image was pushed without a signed SBOM attestation.

To fix:
1. Ensure the "Generate SBOM" step runs after your Docker build
2. Verify cosign is configured to sign the attestation
3. The SBOM must be attested before the image is pushed to HAR

This policy is enforced on all production deployments to meet supply chain compliance requirements.
```

**Talking point:** *"OPA policies are powerful but can be complex to understand. Harness AIDA translates them right in the platform. The developer doesn't need to know Rego, understand policy structure, or read documentation — they just ask AIDA why their pipeline failed and get an answer in seconds."*

---

## Troubleshooting

### Service Naming Convention

**Issue:** Pipeline fails with "service with ref: [fx_rates_api] not found"

**Cause:** Harness service identifiers in this account use lowercase without separators, which differs from pipeline identifiers (which use underscores) and repository names (which use hyphens).

**Examples:**
- Repository: `fx-rates-api` → Service: `fxratesapi`
- Repository: `demo-banking-api` → Service: `demobankingapi`
- Pipeline: `fx_rates_api` → Service: `fxratesapi`

**Fix:** Update the pipeline's `serviceRef` field to use the lowercase, no-separator format. Claude will automatically detect this error and fix it, saving the pattern to memory.

---

## Reset Between Demos

### Scenario 1A reset — Claude Code / direct developer flow

For a dedicated demo repository, reset `main` to the known baseline rather than accumulating repeated add/revert commits.

If the automatic application-code push trigger is enabled, temporarily disable it before the reset so cleanup does not create an unwanted delivery execution.

```bash
cd ~/aidemo/demo-banking-api
git checkout main
git fetch origin
git reset --hard demo-baseline
git push --force-with-lease origin main
```

If Scenario 1A used a temporary implementation branch, delete it after the PR is merged or closed:

```bash
git push origin --delete feature/KANB-X
git fetch --prune
```

If the implementation was pushed directly to `main`, there may be no temporary branch to delete.

Verify:

```bash
git status
grep -R 'accounts/<account_id>/transactions' app tests
ls -la .aisdlc
```

Desired state:

```text
main = demo-baseline                         ✅
working tree clean                           ✅
/accounts/<account_id>/transactions absent  ✅
.aisdlc/Features.md absent                   ✅
```

Re-enable the application-code push trigger before the next Scenario 1B run.

If branch protection prevents force-push, revert the demo implementation/spec commits instead of resetting `main`.

---

### Scenario 1B reset — Spec-driven development

1. **Use a fresh pre-created Jira Item for the next run.** Do not try to clean the old Item's comment history. The agent deliberately reads all comments, so old clarification comments can change the next run.

2. **Close any stale open PRs** for the completed ticket, for example:

```text
aisdlc/KANB-X → main
feature/KANB-X → main
```

3. **Temporarily disable the application-code push trigger** on `demo-banking-api` so the repository reset does not start CI/CD.

4. **Reset `main` to the demo baseline:**

```bash
cd ~/aidemo/demo-banking-api
git checkout main
git fetch origin
git reset --hard demo-baseline
git push --force-with-lease origin main
```

5. **Delete the temporary branches after their PRs are merged or closed.**

For the spec-driven flow this normally means deleting both the generated spec branch and the implementation branch:

```bash
git push origin --delete aisdlc/KANB-X
git push origin --delete feature/KANB-X
git fetch --prune
```

Do not leave `aisdlc/KANB-X` around between demos. The spec pipeline deliberately reuses the same issue-key branch when it exists, so a stale branch can make the next run look like an update rather than a clean new spec flow.

If Harness Code automatically deleted a merged branch, an individual delete command may report that the remote ref does not exist; that is fine.

6. **Verify the clean state:**

```bash
git status
grep -R 'accounts/<account_id>/transactions' app tests
ls -la .aisdlc
git branch -r | grep -E 'aisdlc|feature/'
```

You want:

```text
working tree clean                           ✅
transaction-history endpoint absent         ✅
.aisdlc/Features.md absent                   ✅
no stale demo branches                      ✅
fresh Jira Item ready                       ✅
```

7. **Re-enable the application-code push trigger** before the next demo.

**Operator shortcut:** The only persistent assets between Scenario 1B demos are the Jira/Harness configuration and pipeline execution history. Reset `main`, close any stale PRs, delete the `aisdlc/KANB-X` and implementation branches, prune remotes, and use the next clean Jira Item.

---

### Scenario 2 reset — New service onboarding

Delete only the generated pipeline. Leave the service, registry, repository, namespaces, and templates in place:

```text
Delete the fx-rates-api pipeline from Harness.
```

---

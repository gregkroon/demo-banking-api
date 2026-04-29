# Harness + Claude Code — Demo Script

**Theme:** Claude is the developer's AI pair programmer AND their platform engineer. Harness templates are the guardrails that ensure every deployment — regardless of who writes the code — goes through security scanning, quality gates, and governed approval before reaching production.

**Runtime:** ~20 minutes total (10 min per scenario)

---

## Setup Checklist (before the demo)

- [ ] Terminal open in `/mcp/demo` with Claude Code running (`claude`)
- [ ] Harness UI open, logged in, on the `claude` project
- [ ] Second browser tab / person ready to approve the production gate
- [ ] Pipeline execution view bookmarked: `Pipelines → demo-banking-api`
- [ ] Account-level templates visible: `Account Settings → Templates`
- [ ] Run #52 execution open as "what a successful run looks like"
- [ ] Transaction endpoint reverted and pushed to main (see Reset section below)
- [ ] K8s namespaces `banking-dev` and `banking-prod` exist with `harness-registry-secret` (see Cluster Bootstrap below)

---

## Scenario 1 — Day in the Life: Shipping a Feature

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

## Scenario 2 — New Service Onboarding with Account Templates

**Story:** A new team has already built their microservice — an FX Rates API — and pushed it to a Harness Code repo. The code is there, the Harness service and artifact registry are pre-configured. All they need is a pipeline. They ask Claude to wire it up using the account-level templates. Every guardrail from Scenario 1 applies automatically — without the team knowing or caring what's in those templates.

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
Create a Harness pipeline called fx-rates-api that uses the account-level CI/CD templates.
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

## Key Talking Points (across both scenarios)

| What the audience sees | What to say |
|------------------------|-------------|
| Claude triggers the pipeline | "The developer's interface is a conversation. The platform is the implementation." |
| Claude Code coverage check in logs | "AI isn't just writing the code — it's reviewing it too, with context, not just a number." |
| OPA blocks self-approval | "Governance isn't a checkbox. It's enforced at the platform layer, for every run, without any developer configuration." |
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

## Reset Between Demos

**Scenario 1 reset** — revert the transaction endpoint on the demo-banking-api repo so the "day in the life" story works again:
```
Revert the account transaction endpoint commit and push to main.
```

**Scenario 2 reset** — delete only the pipeline (leave service, registry, and repo in place):
```
Delete the fx-rates-api pipeline from Harness.
```

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

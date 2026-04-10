package harness.policies.image_security

# Policy: Image Security Policy
# Blocks pipelines that ship images with critical CVEs

import future.keywords.if
import future.keywords.in

deny[msg] {
  some finding in input.pipeline.stages[_].spec.execution.steps[_].spec.findings
  finding.severity == "CRITICAL"
  msg := sprintf(
    "BLOCKED: Critical CVE '%v' found in package '%v' (fix version: %v)",
    [finding.cveId, finding.packageName, finding.remediation.fixedVersion]
  )
}

deny[msg] {
  some finding in input.pipeline.stages[_].spec.execution.steps[_].spec.findings
  finding.severity == "CRITICAL"
  finding.packageName == "cryptography"
  msg := "BLOCKED: Critical vulnerability in cryptography package — upgrade to >=42.0.5"
}

---

package harness.policies.sbom_required

# Policy: SBOM Required Policy
# Ensures an SBOM artefact is attached before image promotion

import future.keywords.if

deny[msg] {
  not sbom_present
  msg := "BLOCKED: No SBOM artefact found. Generate SBOM with Syft before promotion."
}

sbom_present if {
  input.pipeline.stages[_].spec.execution.steps[_].name == "Generate SBOM"
}

---

package harness.policies.production_deployment

# Policy: Production Deployment Policy
# Requires approval from a non-executor and enforces change ticket

import future.keywords.if
import future.keywords.in

deny[msg] {
  stage := input.pipeline.stages[_]
  stage.type == "Approval"
  stage.spec.execution.steps[_].spec.approvers.disallowPipelineExecutor == false
  msg := "BLOCKED: Production approval must disallow the pipeline executor from self-approving."
}

deny[msg] {
  stage := input.pipeline.stages[_]
  stage.name == "Deploy to Production"
  not environment_is_production
  msg := "BLOCKED: Production deployment stage must target the 'production' environment."
}

environment_is_production if {
  input.pipeline.stages[_].spec.environment.environmentRef == "production"
}

---

package harness.policies.change_window

# Policy: Change Window Policy
# Production deployments are only permitted Mon-Fri 08:00-17:00 AEST (UTC+10)

import future.keywords.if

warn[msg] {
  outside_change_window
  msg := "WARNING: Deployment is outside the approved change window (Mon-Fri 08:00-17:00 AEST). Proceed only with emergency CAB approval."
}

outside_change_window if {
  hour := time.clock(time.now_ns())[0]
  hour < 8
}

outside_change_window if {
  hour := time.clock(time.now_ns())[0]
  hour >= 17
}

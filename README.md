# Coding Clinic

A portfolio of **14 independent, code-only cloud and DevOps labs**. The main branch is the catalog; each implementation and its detailed README are on the corresponding `problem-N` branch.

The labs cover reusable infrastructure, automation, security, CI/CD, Kubernetes, and platform engineering. They are designed for local validation, mocked tests, and review. **No cloud or Kubernetes resources are provisioned by these labs.** Check each problem README for its prerequisites, validation steps, and any explicitly gated live-use options.

## Problem catalog

| Branch | Lab | What it demonstrates |
| --- | --- | --- |
| [problem-1](https://github.com/oguduf/coding-clinic/tree/problem-1) | [Enterprise Multi-AZ AWS VPC Terraform Module](https://github.com/oguduf/coding-clinic/tree/problem-1) | Reusable Terraform for multi-AZ public and private subnets, per-AZ NAT, and S3/ECR endpoints, with environment configurations and offline validation. |
| [problem-2](https://github.com/oguduf/coding-clinic/tree/problem-2) | [Enterprise Linux Security Hardening with Ansible](https://github.com/oguduf/coding-clinic/tree/problem-2) | CIS-aligned baseline automation for Ubuntu and RHEL, including SSH hardening, Fail2ban, and security updates. |
| [problem-3](https://github.com/oguduf/coding-clinic/tree/problem-3) | [AWS EBS Cost Optimizer](https://github.com/oguduf/coding-clinic/tree/problem-3) | Read-only Python tooling to report unattached EBS volumes by age, estimate storage cost, and create a manual review plan from synthetic fixtures by default. |
| [problem-4](https://github.com/oguduf/coding-clinic/tree/problem-4) | [Cross-Account IAM Automation: Terraform + Python](https://github.com/oguduf/coding-clinic/tree/problem-4) | Least-privilege CI/CD role assumption across AWS accounts using scoped trust, external IDs, and temporary credentials. |
| [problem-5](https://github.com/oguduf/coding-clinic/tree/problem-5) | [AWS EBS Snapshot Automation and Retention](https://github.com/oguduf/coding-clinic/tree/problem-5) | Bash and AWS CLI framework to select tagged instances, plan volume snapshots, and evaluate retention with explicit execution safeguards. |
| [problem-6](https://github.com/oguduf/coding-clinic/tree/problem-6) | [Multi-Architecture Container Security Pipeline](https://github.com/oguduf/coding-clinic/tree/problem-6) | GitHub Actions supply-chain workflow for AMD64/ARM64 builds, vulnerability gates, and controlled image publication and signing by digest. |
| [problem-7](https://github.com/oguduf/coding-clinic/tree/problem-7) | [Reusable GitHub Actions Semantic Versioning Automation](https://github.com/oguduf/coding-clinic/tree/problem-7) | Composite action that interprets Conventional Commits, calculates a SemVer bump, prepares changelog text, and supports a safe dry-run. |
| [problem-8](https://github.com/oguduf/coding-clinic/tree/problem-8) | [Terraform Plan Policy Validator](https://github.com/oguduf/coding-clinic/tree/problem-8) | Offline Python validation of Terraform plan JSON for selected S3 public-access controls, required tags, and supplied cost estimates. |
| [problem-9](https://github.com/oguduf/coding-clinic/tree/problem-9) | [Argo CD ApplicationSet and Kustomize Multi-Cluster GitOps](https://github.com/oguduf/coding-clinic/tree/problem-9) | Shared Kubernetes base with DEV, STAGE, and PROD overlays generated through an Argo CD ApplicationSet. |
| [problem-10](https://github.com/oguduf/coding-clinic/tree/problem-10) | [Automated Terraform Drift Detection and Cost Monitoring](https://github.com/oguduf/coding-clinic/tree/problem-10) | Scheduled refresh-only drift checks, a separate Infracost estimate, and optional Slack reporting; scheduling is disabled by default. |
| [problem-11](https://github.com/oguduf/coding-clinic/tree/problem-11) | [Reusable Helm Chart for a 12-Factor Kubernetes Application](https://github.com/oguduf/coding-clinic/tree/problem-11) | Reusable Helm chart with values validation, health checks, resource controls, HPA, PDB, NetworkPolicy, and optional External Secrets integration. |
| [problem-12](https://github.com/oguduf/coding-clinic/tree/problem-12) | [Python Kubernetes Secret Sync Controller](https://github.com/oguduf/coding-clinic/tree/problem-12) | Kopf controller that watches opted-in ConfigMaps and synchronizes selected values from AWS Secrets Manager into owned Kubernetes Secrets. |
| [problem-13](https://github.com/oguduf/coding-clinic/tree/problem-13) | [Kubernetes Pod Security and Compliance Auditor](https://github.com/oguduf/coding-clinic/tree/problem-13) | Read-only Python audit of Pod data for privileged containers, hostPath volumes, and missing CPU or memory limits. |
| [problem-14](https://github.com/oguduf/coding-clinic/tree/problem-14) | [Reusable Kustomize Observability and Security Component](https://github.com/oguduf/coding-clinic/tree/problem-14) | Reusable Kustomize component for metrics and log sidecars, scrape annotations, and baseline container security settings. |

## Open a lab

Select a branch in the catalog to read its full problem statement, architecture, prerequisites, usage examples, tests, and security notes.

## Main branch

The `main` branch provides this portfolio index. Each lab's source files and detailed instructions remain on its corresponding `problem-N` branch.

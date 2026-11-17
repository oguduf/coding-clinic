# Coding Clinic

A portfolio of hands-on cloud, DevOps, infrastructure-as-code, and Kubernetes labs. Each `problem-N` branch contains the implementation for one problem; the table below summarizes the branches currently published in this repository.

## Branch catalog

| Branch | Project | What it contains |
| --- | --- | --- |
| [problem-1](https://github.com/oguduf/coding-clinic/tree/problem-1) | [Enterprise Multi-AZ AWS VPC Terraform Module](https://github.com/oguduf/coding-clinic/tree/problem-1) | Reusable Terraform networking modules and environment configurations for a multi-AZ AWS VPC. |
| [problem-2](https://github.com/oguduf/coding-clinic/tree/problem-2) | [Enterprise Linux Security Hardening with Ansible](https://github.com/oguduf/coding-clinic/tree/problem-2) | Ansible-based Linux hardening for Ubuntu and RHEL, with roles and environment-specific configuration. |
| [problem-7](https://github.com/oguduf/coding-clinic/tree/problem-7) | [Reusable GitHub Actions Semantic Versioning Automation](https://github.com/oguduf/coding-clinic/tree/problem-7) | A reusable action that interprets Conventional Commits and prepares semantic versions and changelog entries. |
| [problem-8](https://github.com/oguduf/coding-clinic/tree/problem-8) | [Terraform Plan Policy Validator](https://github.com/oguduf/coding-clinic/tree/problem-8) | A Python tool that checks Terraform plan JSON against policy rules and reports or blocks violations. |
| [problem-9](https://github.com/oguduf/coding-clinic/tree/problem-9) | [Argo CD ApplicationSet and Kustomize Multi-Cluster GitOps](https://github.com/oguduf/coding-clinic/tree/problem-9) | ApplicationSet and Kustomize examples for promoting a shared application across DEV, STAGE, and PROD overlays. |
| [problem-10](https://github.com/oguduf/coding-clinic/tree/problem-10) | [Automated Terraform Drift Detection and Cost Monitoring](https://github.com/oguduf/coding-clinic/tree/problem-10) | Scheduled Terraform drift checks, Infracost estimates, and optional Slack reporting. |
| [problem-11](https://github.com/oguduf/coding-clinic/tree/problem-11) | [Reusable Helm Chart for a 12-Factor Kubernetes Application](https://github.com/oguduf/coding-clinic/tree/problem-11) | A configurable Helm chart with schema validation, HPA, PDB, NetworkPolicy, and optional External Secrets integration. |
| [problem-12](https://github.com/oguduf/coding-clinic/tree/problem-12) | [Python Kubernetes Secret Sync Controller](https://github.com/oguduf/coding-clinic/tree/problem-12) | A Kopf controller that syncs opted-in ConfigMap references from AWS Secrets Manager into owned Kubernetes Secrets. |
| [problem-13](https://github.com/oguduf/coding-clinic/tree/problem-13) | [Kubernetes Pod Security and Compliance Auditor](https://github.com/oguduf/coding-clinic/tree/problem-13) | A read-only Python auditor for privileged containers, hostPath volumes, and missing CPU or memory limits. |

## How to use a problem branch

Open a branch link above to see that lab's files, README, examples, tests, and CI checks. Each branch is an independent solution, so its README is the source of truth for setup and validation instructions.

To inspect a branch locally:

```bash
git fetch origin
git switch --track origin/problem-13
```

Replace `problem-13` with the branch you want to review. If you already have a local branch with that name, use `git switch problem-13`.

## Main branch

The `main` branch is the repository landing page and branch catalog. Lab implementations are kept on their corresponding `problem-N` branches.
# Architecture

The package separates configuration and domain rules from AWS API adapters and report output. The default CLI is fixture-only and cannot create boto3 clients.

```mermaid
flowchart LR
  CLI[Offline Python CLI] --> CFG[Validated config]
  CLI --> FX[Synthetic organization fixture]
  FX --> MODEL[Typed account and volume models]
  MODEL --> AGE[UTC volume-age filter]
  MODEL --> PRICE[Regional fixture pricing]
  AGE --> POLICY[Review exclusions]
  PRICE --> POLICY
  POLICY --> OUT[CSV JSON Markdown reports]
  POLICY --> PLAN[Non-executable review plan]
  subgraph FutureAuthorizedAdapter[Future authorized adapter, not invoked by CLI]
    ORG[AWS Organizations] --> STS[STS AssumeRole]
    STS --> EC2[EC2 DescribeVolumes and DescribeRegions]
    EC2 --> MODEL
  end
```

For future authorized callers, `runtime.scan_organization` composes the Organizations, STS, and EC2 adapters using injected sessions. Tests use fakes and mocked responses. No workflow invokes that adapter.


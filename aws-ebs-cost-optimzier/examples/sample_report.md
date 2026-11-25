# EBS Cost Optimization Report

**Execution mode:** offline-fixture  
**Coverage:** COMPLETE

All cost values are illustrative monthly run-rate estimates, not AWS charges or realized savings.
Age is calculated from volume creation time, not historical unattached duration.

## Summary

- Accounts discovered: 4
- Accounts scanned: 3
- Accounts failed: 0
- Regions scanned: 4
- Volumes inspected: 7
- Unattached volumes found: 6
- Unattached volumes meeting age threshold: 6
- Review candidates: 3
- Candidate storage: 390 GiB
- Estimated monthly run rate: $125.90 USD
- Annualized projection: $1510.80 USD

## Volumes

| Account | Region | Volume | Type | GiB | Age | Monthly USD | Review status |
|---|---|---|---|---:|---:|---:|---|
| dev-account | ap-south-1 | vol-sampledev003 | sc1 | 1000 | 90 days | unavailable | pricing is unavailable |
| dev-account | us-east-1 | vol-sampledev001 | gp3 | 100 | 45 days | 28.00 | review only |
| dev-account | us-east-1 | vol-sampledev002 | gp3 | 50 | 30 days | 4.00 | protected tag DoNotDelete=true |
| stage-account | us-west-2 | vol-samplestage001 | gp2 | 250 | 90 days | 27.50 | review only |
| stage-account | us-west-2 | vol-samplestage002 | io1 | 40 | 120 days | 70.40 | review only |
| prod-account | eu-west-1 | vol-sampleprod001 | io2 | 500 | 120 days | 2518.00 | production environment is excluded by policy |

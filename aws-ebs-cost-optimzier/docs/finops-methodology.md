# FinOps methodology

Prices in `config/pricing.example.json` are **synthetic illustrative fixtures**, with deliberately different regional values. They do not represent official AWS prices. Missing region/type prices result in `pricing_status=unavailable`; they are never treated as zero.

The estimator computes monthly run rate as provisioned GiB times fixture storage rate, plus any explicitly configured provisioned-performance charges. gp3 uses fixture allowances for 3,000 IOPS and 125 MiB/s, charging only above those levels. io1 charges all provisioned IOPS; io2 fixture rates use progressive tiers. Other listed types have storage-only fixture rates. Decimal arithmetic and half-up cent rounding avoid binary floating point drift.

The model is a normalized full-month estimate. Real AWS EBS storage and performance usage is billed over time; partial-month costs, regional price changes, discounts, credits, taxes, snapshots, data transfer, and other related services are outside this estimate. Annualized cost is 12 times monthly run rate, not realized savings. Deletion savings depend on verified ownership, retained data, recovery requirements, timing, and billing terms.

Pricing is intentionally supplied as version-controlled sample data. A future pricing provider can implement an interface around AWS published prices, but no Pricing API or live billing source is called here.


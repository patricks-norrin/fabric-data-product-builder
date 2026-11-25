# Workspaces, lakehouses and their responsibilities

`ws_extract` is *extraction as a service*: IT lands every source system as a source-aligned data product
(raw + change history) and grants access per product lakehouse. Business-domain workspaces consume
source-aligned products from other workspaces via shortcuts and build consumer-aligned data products
(Foundational, Business, Analytical — see `data-product-architecture.md` for the full definitions and
ownership/access model).

## Where Each Item Lives

Every data product, regardless of tier (source-aligned, foundational, business, analytical), keeps its
lakehouse and notebooks together in one workspace folder named `<data_product_identifier>`:
`lh_<data_product_identifier>`, `nb_extract_<id>`/`nb_cdc_<id>` (source-aligned) or `nb_model_<id>`
(foundational, proposed — not yet used by this toolpack) or `nb_dp_<id>` (business), and (when built) `pl_<id>`
or a semantic model for that same product. They share that product's lifecycle: created, versioned and
eventually retired together.

Two lakehouses are the exception — they are **workspace-wide infrastructure**, not owned by any single data
product, and stay at the **workspace root**, never inside a product folder:

- **`lh_workspace_shared_resources`** — a hard prerequisite in any workspace running `lakehouse_toolbelt`
  (`DataProduct(...)` raises an exception if it's missing; see
  `reference/lakehouse_toolbelt/docs/environment-prerequisites-and-conventions.md`). Its scope today is
  exactly `Files/configuration/data_product/*` — one subfolder per data product's config plus
  `project_configuration/project_configuration.json`. Nothing else is defined to live there.
- **`lh_shortcuts`** — a consumer-side, business-domain container for schema-level shortcuts to data in other
  workspaces. Never create a shortcut to a lakehouse in the same workspace; read that lakehouse directly.
  An extraction workspace does not need one when it only produces source-aligned products.

## Workspace Design Patterns

### Pattern 1: Separation by Product Type

```
ws_extract_dev/                    ← Source-aligned products
├── lh_exchange_rates_api
├── lh_oracle_ebs_finland
└── lh_salesforce

ws_finance_dev/                    ← Business domain
├── lh_shortcuts                   ← Shortcuts to source products
├── lh_finance_reporting
└── lh_financial_planning

ws_sales_dev/                      ← Business domain
├── lh_shortcuts
├── lh_customer_360
└── lh_sales_analytics
```

**When to use**: Medium/large orgs, multiple domains, shared foundational data.

### Pattern 2: Single Workspace

```
ws_data_platform_dev/
├── lh_exchange_rates_api          ← Source-aligned
├── lh_oracle_ebs_finland
├── lh_finance_reporting           ← Business domain
└── lh_sales_analytics
```

**When to use**: Small teams, single domain, simple access control.

### Pattern 3: Hybrid (Environment + Product Type)

Replicate Pattern 1 across `_dev`, `_test`, `_prod` environments. Promote code (not data) through environments.

### Decision Tree

```
Multiple business domains?
├─ Yes → Pattern 1 (Separation by Product Type)
└─ No → Multiple environments (dev/test/prod)?
         ├─ Yes → Pattern 3 (Hybrid)
         └─ No → Pattern 2 (Single Workspace)
```

---

## Naming Conventions

### Workspaces
- `ws_{domain}_{env}` — e.g., `ws_extract_dev`, `ws_finance_prod`
- Feature branches: `{issue_number}_ws_{domain}_{env}` — e.g., `12345_ws_extract_dev`

### Lakehouses
- Source-aligned: `lh_{data_product_identifier}` — e.g., `lh_exchange_rates_api`
- Business: `lh_{business_product_name}` — e.g., `lh_finance_reporting`
- Shortcuts container: `lh_shortcuts`

### Notebooks
- Extraction: `nb_extract_{source_system}` — e.g., `nb_extract_exchange_rates_api`
- Business: `nb_dp_{product_name}` — e.g., `nb_dp_currency_exchange_rates`

### Tables
- Raw: `{dataset_name}_raw` — e.g., `exchange_rates_raw`
- Change history: `{dataset_name}` (no suffix) — auto-created by lakehouse_toolbelt
- Business: `{business_table_name}` (no suffix)

---

## OneLake Shortcuts

Use `lh_shortcuts` only to bring data into a workspace from a different workspace. Create a schema-level
shortcut for each upstream product schema, named exactly after the source schema, so its schema and table
names stay aligned as they change. In a single-workspace setup, do not create `lh_shortcuts` to access
co-located data; read the source lakehouse directly.

### When to Use

- ✅ A business-domain workspace consuming source-aligned or other upstream data from another workspace
- ✅ Read-only cross-workspace consumption without duplicating the source data
- ❌ Do not create same-workspace shortcuts; read the source lakehouse directly
- ❌ Do not use raw data for normal tabular modeling; consume the source product's change-history tables
- ❌ No circular shortcuts or shortcut chaining

### Recommended Pattern

Create a schema-level shortcut in the consumer workspace's `lh_shortcuts` to the upstream product schema,
using the same schema name. The shortcut mirrors the source table names; consume the change-history tables
for standard tabular data:

```
ws_finance_dev/lh_shortcuts/
└── oracle_ebs_finland → schema shortcut to ws_extract_dev/lh_oracle_ebs_finland/Tables/oracle_ebs_finland/
    ├── invoice_headers
    └── invoice_lines
```

### Cross-Environment Shortcuts

```
# Dev shortcuts point to dev sources
ws_finance_dev/lh_shortcuts/oracle_ebs_finland → ws_extract_dev/lh_oracle_ebs_finland/Tables/oracle_ebs_finland/

# Prod shortcuts point to prod sources
ws_finance_prod/lh_shortcuts/oracle_ebs_finland → ws_extract_prod/lh_oracle_ebs_finland/Tables/oracle_ebs_finland/
```

Promote code (notebooks), not shortcuts. Recreate shortcuts per environment.

### Access Requirements

1. Reader permission on source lakehouse
2. Workspace viewer role on source workspace
3. Proper capacity assignment on both workspaces

### Verification Checklist

- [ ] Shortcut appears in lakehouse Files explorer
- [ ] Can read data: `spark.read.format("delta").load("Files/shortcuts/name")`
- [ ] Row count matches source
- [ ] Schema matches expected structure
- [ ] Access works for service principals

---

## Multi-Schema (GDPR Pattern)

```
lh_customer_data_product/
├── Tables/restricted/           ← Full PII, limited access
│   ├── customers
│   └── addresses
└── Tables/non_sensitive/        ← Pseudonymized, broader access
    ├── customers
    └── addresses
```

SQL: `SELECT * FROM restricted.customers`

---

## Metadata Columns Standard

### Extraction Metadata (add before lakehouse_toolbelt processing)

| Column | Type | Purpose |
|--------|------|---------|
| `dpmeta_input_file_name` | STRING | Source filename or path |
| `dpmeta_source_system_id` | STRING | Source system identifier |

### lakehouse_toolbelt CDC Metadata (auto-added)

| Column | Type | Purpose |
|--------|------|---------|
| `dpmeta_uid` | STRING | Unique identifier hash |
| `dpmeta_payload_hash` | STRING | Change detection hash |
| `dpmeta_object_version_start_time` | TIMESTAMP | Version validity start |
| `dpmeta_object_version_end_time` | TIMESTAMP | Version validity end |
| `dpmeta_loaded_to_dataplatform` | TIMESTAMP | Ingestion timestamp |

---

## Infrastructure Patterns

### Lean Pattern (Small Teams)

Single resource group, shared capacity, direct data flow.

```
rg-fabric-{env}/
├── Fabric Capacity (optional)
├── Storage Account (Terraform state)
└── Key Vault (optional)

Fabric Tenant/
├── ws_{domain}_{env}/
│   ├── lh_{source_system}        ← Source-aligned
│   └── lh_{concept}              ← Consumer-aligned (Foundational/Business, shortcuts)
```

### Enterprise Pattern (Multi-Domain)

Separated resource groups, extraction-as-a-service, domain isolation.

```
rg-fabric-platform-{env}/        ← Capacity, state, shared KV
rg-fabric-eaas-{env}/            ← Extraction credentials
rg-fabric-{domain}-{env}/        ← Per-domain resources

Fabric Tenant/
├── ws_eaas_{env}/                ← Centralized extraction
│   ├── lh_{source_1}
│   └── lh_{source_2}
├── ws_eaas_sensitive_{env}/      ← PII/sensitive sources
├── ws_{domain}_{env}/            ← Business domains consume via shortcuts
```

### Decision Matrix

| Factor | Lean | Enterprise |
|--------|------|-----------|
| Team size | < 10 | 10+ |
| Domains | 1-2 | 3+ |
| Governance | Low-Medium | High |
| Compliance | No | Yes |
| Time to value | Days | Weeks |

**Start lean, migrate to enterprise as governance needs grow.**

### Azure Naming

- Resource Group: `rg-fabric-{layer}-{env}`
- Storage: `st{purpose}{env}{region}`
- Key Vault: `kv-fabric-{layer}-{env}`
- Capacity: `cap-fabric-{env}-{sku}`

### Entra Group Pattern

- `grp-fabric-{workspace}-admins`
- `grp-fabric-{workspace}-contributors`
- `grp-fabric-{workspace}-viewers`

**Assign groups, never individual users.**

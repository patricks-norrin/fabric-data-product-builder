# Workspaces, lakehouses and their responsibilities

`ws_extract` is *extraction as a service*: IT lands every source system as a source-aligned data product
(raw + change history) and grants access per product lakehouse. Business-domain workspaces consume via
shortcuts and model business data products. Each data product's items live in a workspace folder named
`<data_product_identifier>`; `lh_workspace_shared_resources` (configuration) stays at the workspace root.

## Workspace Design Patterns

### Pattern 1: Separation by Product Type

```
ws_extract_dev/                    ← Source-aligned products
├── lh_frankfurter_api
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
├── lh_frankfurter_api             ← Source-aligned
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
- Source-aligned: `lh_{data_product_identifier}` — e.g., `lh_frankfurter_api`
- Business: `lh_{business_product_name}` — e.g., `lh_finance_reporting`
- Shortcuts container: `lh_shortcuts`

### Notebooks
- Extraction: `nb_extract_{source_system}` — e.g., `nb_extract_frankfurter_api`
- Business: `nb_dp_{product_name}` — e.g., `nb_dp_currency_exchange_rates`

### Tables
- Raw: `{dataset_name}_raw` — e.g., `exchange_rates_raw`
- Change history: `{dataset_name}` (no suffix) — auto-created by lakehouse_toolbelt
- Business: `{business_table_name}` (no suffix)

---

## OneLake Shortcuts

### When to Use

- ✅ Business domain lakehouses referencing source-aligned products
- ✅ Read-only consumption of foundational datasets
- ✅ Cross-workspace data access without duplication
- ❌ Don't shortcut to `raw/` — use `change_history/` instead
- ❌ No circular shortcuts or shortcut chaining

### Recommended Pattern

Business lakehouse shortcuts to source product's `change_history/` folder:

```
ws_finance_dev/lh_shortcuts/
├── exchange_rates → ws_extract_dev/lh_frankfurter_api/.../change_history/
├── invoices → ws_extract_dev/lh_oracle_ebs_finland/.../change_history/
└── customers → ws_extract_dev/lh_salesforce/.../change_history/
```

### Cross-Environment Shortcuts

```
# Dev shortcuts point to dev sources
ws_finance_dev/lh_shortcuts/invoices → ws_extract_dev/lh_oracle/.../change_history/

# Prod shortcuts point to prod sources
ws_finance_prod/lh_shortcuts/invoices → ws_extract_prod/lh_oracle/.../change_history/
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
│   └── lh_{business_model}       ← Business-modeled (shortcuts)
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

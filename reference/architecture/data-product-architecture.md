# Norrin data product architecture

Source of truth for the *why*: what a data product is, why one product = one lakehouse, why raw is landed
unchanged, and why SCD2 change history via `lakehouse_toolbelt` is the default for every tabular dataset.
Runtime contract (paths, config, functions): `reference/lakehouse_toolbelt/`.

# Fabric Data Product Architecture Guidelines

## Core Pattern: 1 Data Product = 1 Lakehouse

Every data product — whether source-aligned (extraction) or business-modeled — gets its own dedicated lakehouse. This enables:
- **Per-product access control** — owner defines who can read/write at lakehouse level
- **Lakehouse-level lineage** — Fabric lineage graph shows product-to-product dependencies
- **Multi-schema perspectives** — e.g., GDPR product with `restricted` schema (full PII) + `non_sensitive` schema (pseudonymized)
- **Independent lifecycle** — each product can be versioned, migrated, or deprecated independently

### Source-Aligned Data Products Explained

A **source-aligned data product** contains data from a **single source system**. It keeps the data in its original format (similar to "bronze" in medallion architecture) with minimal changes — minimal data type or encoding assumptions or transformations.

It **ALSO includes** the versioned change history that is easier to consume downstream because it's deduplicated and always a Delta table. In some diagrams this is called "silver" level, but **we keep it together with raw in the same lakehouse** because it's still the same source data as raw — just optimized for consumption.

**Why one lakehouse for both raw and change history?**
- **Governance simplicity** — one access control boundary for the entire source system
- **Logical cohesion** — both are representations of the same source data
- **Lineage clarity** — downstream consumers see one source product, not fragmented layers

## Lakehouse Folder Convention

Raw data lands in a structured folder hierarchy:

```
Files/<data_product_identifier>/<dataset_name>/raw/<load_timestamp_safe>/
```

### Path Components

- **`data_product_identifier`** — Source system or source-aligned product ID
  - Examples: `frankfurter_api`, `oracle_ebs_finland`
  - Use snake_case, descriptive names
  
- **`dataset_name`** — Logical dataset within that source
  - Examples: `exchange_rates`, `currencies`, `invoice_headers`, `invoice_lines`
  - Use snake_case, singular or plural as appropriate
  
- **`raw`** — Immutable landing zone marker
  - Always use `raw` as the folder name for landed data
  
- **`load_timestamp_safe`** — Batch identifier for each extraction/load run
  - **Primary (most cases)**: Use the loading trigger timestamp
    - **Required format**: `YYYYMMDDTHHMMSSZ` only
    - **Example**: `20260327T081530Z`
  - **Secondary option**: Use source system batch_id ONLY when the source actually has this concept
    - Must be filesystem-safe (no `:`, spaces, `/`, `\\` or other risky characters)
    - Example: `batch_12345` (if Oracle EBS provides explicit batch identifiers)

### Complete Path Examples

**Note**: Each source-aligned data product contains BOTH:
1. **raw/** — Original format ("bronze") with minimal transformations, immutable landing zone
2. **change_history/** — Deduplicated, versioned Delta table ("silver") created by lakehouse_toolbelt, easier to consume
   - Both live in the same lakehouse because they represent the same source data, just optimized for different purposes

**Source-aligned data product (Frankfurter API) - With lakehouse_toolbelt CDC**:
```
ws_extract_dev/lh_frankfurter_api/
├── Files/frankfurter_api/exchange_rates/
│   ├── raw/                                     ← "Bronze": immutable source files, minimal transformations
│   │   ├── 20260327T081530Z/rates.json          ← Timestamped batch
│   │   └── 20260408T110245Z/rates.json          ← Later extraction
│   └── change_history/                          ← "Silver": deduped, versioned Delta (lakehouse_toolbelt)
├── Files/frankfurter_api/currencies/
│   ├── raw/
│   │   └── 20260327T081530Z/currencies.json
│   └── change_history/
└── (No Tables/ - change_history is already the "silver" consumption layer)
```

**Source-aligned data product (Oracle EBS) - With lakehouse_toolbelt CDC**:
```
ws_extract_dev/lh_oracle_ebs_finland/
├── Files/oracle_ebs_finland/invoice_headers/
│   ├── raw/                                     ← "Bronze": immutable source files, minimal transformations
│   │   ├── 20260408T143022Z/headers.parquet
│   │   └── 20260408T183015Z/headers.parquet
│   ├── raw_delta/                               ← Optional: Single Delta table for snapshot fallback or intermediate processing
│   ├── checkpoint/                              ← Streaming checkpoint (when using Structured Streaming)
│   └── change_history/                          ← "Silver": deduped, versioned Delta (lakehouse_toolbelt)
├── Files/oracle_ebs_finland/invoice_lines/
│   ├── raw/
│   │   ├── 20260408T143022Z/lines.parquet
│   │   └── 20260408T183015Z/lines.parquet
│   └── change_history/
└── (No Tables/ - change_history is already the "silver" consumption layer)
```

**Source-aligned data product with non-tabular data (Product catalog with images)**:
```
ws_extract_dev/lh_product_catalog/
├── Files/product_catalog/products/              ← Tabular data with CDC
│   ├── raw/
│   │   ├── 20260408T090000Z/products.parquet
│   │   └── 20260408T150000Z/products.parquet
│   └── change_history/                          ← CDC for product metadata
├── Files/product_catalog/images/                ← Non-tabular: NO CDC
│   ├── product_12345_main.jpg
│   ├── product_12345_side.jpg
│   ├── product_67890_main.jpg
│   └── (images stored directly, no change_history/)
└── Files/product_catalog/documents/             ← Non-tabular: NO CDC
    ├── product_12345_spec.pdf
    ├── product_67890_manual.pdf
    └── (PDFs stored directly, no change_history/)
```
**Note**: Tabular data (`products/`) goes through CDC workflow. Non-tabular assets (`images/`, `documents/`) are stored directly as immutable files.

**Source-aligned data product with snapshot fallback (No CDC capability)**:
```
ws_extract_dev/lh_legacy_system/
├── Files/legacy_system/customer_master/
│   ├── raw/                                     ← Landing zone for source files
│   │   ├── 20260408T060000Z/customers.csv
│   │   └── 20260409T060000Z/customers.csv
│   └── raw_delta/                               ← Fallback: Single Delta table with all snapshots
│       └── (Delta table with snapshot_timestamp column)
└── (No change_history/ - source doesn't support CDC, using snapshots instead)
```
**Note**: When source system lacks CDC capability, fall back to `raw_delta/` as a **single Delta table** containing all snapshots with a timestamp/version column. Query specific snapshots by filtering (e.g., `WHERE snapshot_timestamp = '2026-04-08'`), eliminating need to know folder structures.

**With lakehouse_toolbelt integration**:
```
Files/<data_product_identifier>/<dataset_name>/
├── raw/<batch_identifier>/          ← Initial landing (immutable, manual)
├── raw_delta/                       ← Single Delta table with snapshots (optional, manual, when CDC unavailable)
├── checkpoint/                      ← Streaming checkpoint (only for Structured Streaming workloads)
└── change_history/                  ← Auto-created by lakehouse_toolbelt CDC upsert
```

## Workspace Architecture Pattern

### Extraction Workspace (`ws_extract_<env>`)

**Purpose**: IT-managed, extraction-as-a-service
**Characteristics**:
- Centralized landing zone for all source data
- One lakehouse per source-aligned data product
- Grants read access to business domains via shortcuts
- Responsible for raw data ingestion and initial table creation

**Naming convention**: `ws_extract_<env>` where `<env>` is `dev`, `test`, or `prod`

**Contains**:
- Source-aligned product lakehouses: `lh_<data_product_identifier>`
- Extraction notebooks: `nb_extract_<source_system>`
- Future: domain-routing + security group bindings

### Business Domain Workspaces (`ws_<domain>_<env>`)

**Purpose**: Business-domain ownership (e.g., finance, sales, marketing)
**Characteristics**:
- Consume source data via OneLake shortcuts
- Transform and model business data products
- Own business logic and data quality rules
- One lakehouse per business data product

**Naming convention**: `ws_<domain>_<env>` (e.g., `ws_finance_dev`, `ws_sales_prod`)

**Contains**:
- Shortcut lakehouse: `lh_shortcuts` (contains ONLY shortcuts to source products)
- Business product lakehouses: `lh_<business_product_name>`
- Modeling notebooks: `nb_<business_product_name>`

### Example Architecture

```
ws_extract_dev (IT-managed, extraction-as-a-service - development)
├── lh_frankfurter_api              ← source-aligned data product (with CDC)
│   ├── Files/frankfurter_api/exchange_rates/
│   │   ├── raw/<load_timestamp_safe>/
│   │   └── change_history/                  ← CDC versioned data
│   ├── Files/frankfurter_api/currencies/
│   │   ├── raw/<load_timestamp_safe>/
│   │   └── change_history/
│   └── Tables/exchange_rates_raw            ← Optional raw Delta table
├── nb_extract_frankfurter_api
├── lh_oracle_ebs_finland           ← source-aligned data product (with CDC)
│   ├── Files/oracle_ebs_finland/invoice_headers/
│   │   ├── raw/<load_timestamp_safe>/
│   │   └── change_history/                  ← CDC versioned data
│   ├── Files/oracle_ebs_finland/invoice_lines/
│   │   ├── raw/<load_timestamp_safe>/
│   │   └── change_history/
│   ├── Tables/purchase_invoices_headers_raw ← Optional raw Delta table
│   └── Tables/purchase_invoices_lines_raw
└── nb_extract_purchase_invoices

ws_finance_dev (business-domain - development)
├── lh_shortcuts                    ← shortcuts-only lakehouse
│   └── Shortcuts → ws_extract_dev/lh_frankfurter_api
│                   ws_extract_dev/lh_oracle_ebs_finland
├── lh_currency_exchange_rates      ← business data product
│   └── Tables/currency_exchange_rates
├── nb_currency_exchange_rates
├── lh_purchase_invoices            ← business data product
│   ├── Tables/purchase_invoice_headers
│   └── Tables/purchase_invoice_lines
└── nb_purchase_invoices

12345_ws_extract_dev (feature branch workspace - DevOps issue #12345)
└── (development workspace for new extraction feature)
```

**Multi-environment setup**: Replicate this structure for `_test` and `_prod` environments with appropriate shortcuts and promotion workflows.

## Naming Conventions

### Workspaces
- **Pattern**: `ws_<domain>_<environment>`
- **Environments**: `dev`, `test`, `prod`
- **Examples**: `ws_extract_dev`, `ws_extract_test`, `ws_extract_prod`, `ws_finance_dev`, `ws_finance_prod`

**Feature development workspaces**:
- **Pattern**: `<issue_number>_ws_<domain>_<environment>`
- **Purpose**: Branch workspace for developing new features or changes
- **Example**: `12345_ws_extract_dev` (for DevOps issue #12345)
- **Lifecycle**: Created from base workspace, used for development, merged/promoted when complete, then deleted

**Naming rules**:
- Always include environment suffix (no bare `ws_extract`)
- Feature workspaces prefix with issue number
- Use underscore `_` as separator
- Keep domain name descriptive but concise

### Lakehouses
- **Source-aligned products**: `lh_<data_product_identifier>`
  - Examples: `lh_frankfurter_api`, `lh_oracle_ebs_finland`
- **Business products**: `lh_<business_product_name>`
  - Examples: `lh_currency_exchange_rates`, `lh_purchase_invoices`
- **Shortcuts container**: `lh_shortcuts` (special case, contains only shortcuts)

### Notebooks
- **Extraction notebooks**: `nb_extract_<source_system>`
  - Examples: `nb_extract_frankfurter_api`, `nb_extract_purchase_invoices`
- **Business product notebooks**: `nb_<business_product_name>`
  - Examples: `nb_currency_exchange_rates`, `nb_purchase_invoices`

### Tables
- **Raw tables** (in extraction workspace): `<dataset_name>_raw`
  - Examples: `exchange_rates_raw`, `currencies_raw`, `purchase_invoices_headers_raw`
  - Created manually by extraction notebooks
- **Change history tables** (when using lakehouse_toolbelt): `<dataset_name>` (no suffix)
  - Location: `Files/<data_product_id>/<dataset_name>/change_history/` or registered in `Tables/` (schema-enabled)
  - Created automatically by `upsert_delta_change_history()`
- **Business tables** (in business workspace): `<business_table_name>` (no suffix)
  - Examples: `currency_exchange_rates`, `purchase_invoice_headers`
  - Created manually by business modeling notebooks

## OneLake Shortcuts Pattern

### Convention
- Create a dedicated **`lh_shortcuts`** lakehouse in each business domain workspace
- This lakehouse contains **ONLY shortcuts**, no native tables
- Points to source-aligned product lakehouses in extraction workspace
- Makes it clear what's external data vs. internally managed

### Shortcut Setup
1. In business workspace, create `lh_shortcuts` lakehouse
2. Create OneLake shortcuts pointing to each needed source product table:
   - `exchange_rates_raw` → shortcut from `ws_extract_dev/lh_frankfurter_api/Tables/exchange_rates_raw`
   - `currencies_raw` → shortcut from `ws_extract_dev/lh_frankfurter_api/Tables/currencies_raw`
   - etc.
3. Business notebooks read from `lh_shortcuts` via cross-lakehouse reference

**Cross-environment shortcuts**: In production, shortcuts point to `ws_extract_prod` instead of `ws_extract_dev`.

### Benefits
- Clear separation between external (shortcut) and internal (native) data
- Single place to manage all external dependencies
- Easy to identify data lineage and upstream dependencies

## Multi-Schema Capabilities

The 1-product-1-lakehouse pattern supports multiple schemas within a single lakehouse for scenarios like:

### GDPR / Data Privacy Pattern
- **Restricted schema**: Full PII, limited access
- **Non-sensitive schema**: Pseudonymized or aggregated data, broader access

### Example Structure
```
lh_customer_data_product/
├── Tables/restricted/                   ← Schema as folder
│   ├── customers                        ← Full PII
│   └── addresses                        ← Full addresses
└── Tables/non_sensitive/                ← Schema as folder
    ├── customers                        ← Pseudonymized
    └── addresses                        ← City/country only
```

**SQL access pattern**: `SELECT * FROM restricted.customers` (queries use dot notation, but physical storage is `Tables/restricted/customers`)

## Metadata Columns Standard

### Extraction Metadata (Raw Layer)

When landing raw data into Delta tables, add these lakehouse_toolbelt reserved metadata columns:

| Column | Type | Purpose | Required |
|--------|------|---------|----------|
| `dpmeta_input_file_name` | STRING | Source filename or path | Yes |
| `dpmeta_source_system_id` | STRING | Source system identifier | Yes |

**These columns must be added BEFORE calling `lakehouse_toolbelt.add_dpmeta_columns()`.**

### Example - Raw Layer Metadata
```python
from pyspark.sql import functions as F

# Add lakehouse_toolbelt reserved metadata columns
df_with_metadata = df_raw \
    .withColumn("dpmeta_input_file_name", F.input_file_name()) \
    .withColumn("dpmeta_source_system_id", F.lit("oracle_ebs_finland"))
```

### Lakehouse Toolbelt CDC Metadata

When using `lakehouse_toolbelt` for CDC versioning, additional metadata columns are added:

| Column | Type | Purpose |
|--------|------|----------|
| `dpmeta_uid` | STRING | Unique identifier hash (from `unique_identifier_columns`) |
| `dpmeta_payload_hash` | STRING | Change detection hash |
| `dpmeta_object_version_start_time` | TIMESTAMP | Version validity start time |
| `dpmeta_object_version_end_time` | TIMESTAMP | Version validity end time |
| `dpmeta_loaded_to_dataplatform` | TIMESTAMP | Ingestion timestamp (when data was loaded) |

**Note**: `dpmeta_loaded_to_dataplatform` is automatically set by lakehouse_toolbelt to track when data was ingested, enabling incremental processing and safe delta filtering.

**For complete lakehouse_toolbelt API usage and examples**, see `reference/lakehouse_toolbelt/`.

## When to Use This Pattern

### Use for:
- ✅ Source-aligned data products (extraction from external systems)
- ✅ Business-modeled data products (domain-specific transformations)
- ✅ Multi-workspace architectures (extraction + business domains)
- ✅ Projects requiring clear data lineage
- ✅ Scenarios with different access control per product
- ✅ Independent product lifecycle management

### Consider alternatives for:
- ⚠️ Single small project with <5 tables (may be overkill)
- ⚠️ Prototype/POC work (simpler structure may suffice)
- ⚠️ Projects with very tight coupling between all tables (single lakehouse may be simpler)

## Implementation Notes

### Platform Detection
When implementing extraction notebooks:
- Fabric: Check for `AZURE_SERVICE` environment variable
- Databricks: Check for `DATABRICKS_RUNTIME_VERSION` environment variable

### Tool Preference
- **Always prefer Fabric MCP tools** over `az rest` CLI commands
- Use `fab` CLI skills as fallback when MCP doesn't expose required operations
- See project `.github/copilot-instructions.md` for tool precedence

### Batch Identifier Generation
```python
from datetime import datetime
import uuid

# Option 1: Timestamp-based (default)
batch_identifier = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
# Example output: "20260408T143022Z"

# Option 2: Source system batch ID
batch_identifier = f"batch_{source_batch_id}"  # e.g., "batch_12345"

# Option 3: UUID-based
batch_identifier = str(uuid.uuid4())  # e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```


## Integration with Lakehouse Toolbelt

The architecture pattern works seamlessly with `lakehouse_toolbelt` for CDC workflows.

### High-Level Workflow

1. **Extract to raw/** — Land data in timestamped batches under `Files/<dp_id>/<dataset>/raw/<batch_identifier>/`
2. **Process with toolbelt** — Read from raw, add metadata columns (`dpmeta_input_file_name`, `dpmeta_source_system_id`), then call lakehouse_toolbelt functions
3. **Incremental loading** — Use `dpmeta_loaded_to_dataplatform` for delta filtering

**For detailed API usage, code examples, and complete workflow patterns**, see `reference/lakehouse_toolbelt/`.

### Folder Usage by Pattern

| Folder | Created By | Purpose | When Created |
|--------|------------|---------|--------------|
| `raw/<batch_id>/` | Data engineer | Immutable timestamped landing for extracted data (tabular or non-tabular) | During extraction |
| `raw_delta/` | Data engineer | Fallback: Single Delta table containing all full extract snapshots with timestamp/version column | When CDC unavailable |
| `checkpoint/` | Spark Structured Streaming | Streaming checkpoint for fault tolerance | Only for streaming workloads |
| `change_history/` | lakehouse_toolbelt | CDC versioned data (Files or Tables path) — for TABULAR data only | First `upsert_delta_change_history()` call |

**Folder creation notes**:
- **Manual folders** (`raw/`, `raw_delta/`): Created by extraction notebooks during data landing
  - `raw/` contains immutable source files in timestamped batch folders
  - `raw_delta/` is a **single Delta table** (not a folder hierarchy) containing all snapshots with timestamp/version column
- **Streaming checkpoint** (`checkpoint/`): Only created when using Spark Structured Streaming—not required for batch processing
- **CDC change history** (`change_history/`): Automatically created by lakehouse_toolbelt `upsert_delta_change_history()` function on first run—can be in Files or Tables path depending on configuration

**Table naming with lakehouse_toolbelt**:
- **Raw tables** (this pattern): Use `<dataset_name>_raw` suffix for clarity (e.g., `invoice_headers_raw`)
- **Change history tables** (lakehouse_toolbelt): Created automatically using dataset_name from config, can be in Files path (`change_history/`) or registered in Tables (schema-enabled lakehouse)
- **Lakehouse naming**: Both patterns use `lh_{data_product_identifier}` convention

### When to Use Each Pattern

**Default: Architecture + lakehouse_toolbelt CDC** (use this for ALL tabular data unless exception applies)

**Always use lakehouse_toolbelt SCD Type 2 CDC as the default** for any extracted **tabular data**:
- Track data changes over time
- Point-in-time queries and full audit trail
- Has any form of unique identifier (primary keys, natural keys, composite keys)
- Source provides timestamps, version numbers, or CDC capabilities
- Examples: Customer data, invoices, products, transactions, **exchange rates**, price lists, reference data

**When CDC cannot be extracted** - Fall back to snapshots:
- Source system doesn't support change detection
- Technical constraint prevents CDC implementation
- **Fallback approach**: Use `raw_delta/` as a **single Delta table** containing all snapshots
  - Append each full extract with a snapshot timestamp/version column
  - Query specific snapshots by filtering: `WHERE snapshot_timestamp = '2026-04-08'`
  - No need to manage folder hierarchies or know snapshot filenames
  - Enables point-in-time queries even without CDC

**Non-tabular data** - Bypass CDC entirely:
- Images, videos, sound files, PDFs, documents, binary assets
- Store directly in `raw/` or dedicated folders (e.g., `Files/<dp_id>/images/`, `Files/<dp_id>/documents/`)
- No CDC processing — these are immutable file assets, not change-tracked records
- Access via OneLake file APIs, not Delta tables

**Exceptions for tabular data are LAST RESORT** - Skip CDC only when:

1. **No unique identifier possible**
   - Data fundamentally cannot be uniquely identified
   - No combination of columns can reliably distinguish records
   - Example: Pure event streams with no entity concept

2. **Streaming with mandatory fast pass-through**
   - Business requires sub-second latency (lambda architecture)
   - High-velocity streams where SCD2 overhead breaks SLAs
   - Note: Most streaming can still use CDC on slow track

3. **True static/generated data only**
   - Calendar/date dimension tables (generated, never changes)
   - One-time historical migrations (no future updates)
   - Pure append-only event logs where no updates are ever possible

**Critical decision guideline**: 
- **If source has ANY change detection** (timestamps, versions, CDC) → **ALWAYS use lakehouse_toolbelt**
- **If data might be updated/corrected** → **ALWAYS use lakehouse_toolbelt**
- **If you're unsure** → **ALWAYS use lakehouse_toolbelt**
- Only skip CDC when you have a concrete technical constraint that makes it impossible

## Future Enhancements

The pattern is designed to support future capabilities:
- **Domain routing**: Automatic security group bindings per product lakehouse
- **Automated shortcut creation**: Based on metadata tags and environment promotion
- **Schema evolution**: Controlled via compatibility modes
- **Data mesh**: Products as autonomous units with clear contracts
- **Incremental CDC**: Automated delta detection using `dpmeta_loaded_to_dataplatform`
- **Automated environment promotion**: Dev → Test → Prod workflows with validation gates

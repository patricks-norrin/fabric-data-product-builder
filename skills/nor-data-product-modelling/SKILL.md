---
name: nor-data-product-modelling
description: "Model Norrin foundational and business data products in Microsoft Fabric. Use when designing or reviewing a modelling notebook, business rules, output contracts, monetary datatypes, Delta table descriptions, or relationships between data products."
---

# Norrin data product modelling

Use this skill for consumer-aligned **Foundational** and **Business** data products. Load
`nor-data-product-architecture` first when the product boundary or tier is not already settled.

This iteration defines the modelling standard. It does not render notebooks or implement automated tests.
Keep the notebook ready for tests to be added without restructuring the transformations.

## Local review and Fabric connection

Read, review, explain, compare, and edit local modelling notebooks and related local files without Fabric
preflight. Local-only syntax checks, unit tests, linters, and Git inspection also require no Fabric connection.

Run `nor-environment-check` before the first action that connects to Fabric, including OneLake or catalog
inspection, remote schema or data validation, notebook execution, publication, provisioning, or cleanup. If a
local review identifies a question that only Fabric can answer, state that boundary and do not claim it was
verified until preflight passes and the remote check is completed.

## Review output

Present every actionable review finding in one continuous numbered list, including findings grouped under
different severity headings. Give each item a severity, the affected file or notebook location, the observed
gap, its consequence, and the recommended improvement. Do not use unnumbered bullets for actionable findings
or restart numbering in each section. Keep item numbers stable within the review so the user can unambiguously
choose which findings to include or exclude, for example: "include 1 and 3; exclude 2."

## Product boundary and storage

- One data product owns one schema-enabled lakehouse named `lh_<data_product_identifier>`.
- A Foundational product models one reusable business concept, such as `purchase_invoice`, `supplier`, or
  `exchange_rate`. A Business product combines Foundational products to answer a business need.
- Put the modelling notebook in the product folder and name it `nb_model_<data_product_identifier>`.
- Publish owned tables under `Tables/<data_product_identifier>/<table_name>` so the product schema is explicit.
- Read other products through the domain workspace's `lh_shortcuts`; never write into an upstream product.

## Notebook structure

Use this order so a reader can move from intent to inputs, rules, contract, and publication without tracing
state backwards. A modelling notebook may bind a default lakehouse when that improves interactive authoring;
treat the binding as a deliberate, deployment-managed choice (generated extract and CDC notebooks stay unbound):

1. **Title and purpose (markdown).** Name the tier, business concept, owner or intended consumers when known,
   and the tables the notebook publishes.
2. **Imports and workspace (code).** Import Spark functions and types and resolve the current workspace at runtime.
   Write lakehouse, schema, and table names in full at their use sites.
3. **Input products (markdown + code).** List every source table and what it contributes, then read it. For each
   source-aligned CDC table, state and implement whether the model uses current rows
  (`dpmeta_is_current = true`) or historical versions. Apply that filter immediately after the read, before
  projecting away metadata columns or joining. Do not leave this implicit.
4. **Base model (markdown + code).** Declare the grain, identifiers, core columns, straightforward renames,
   casts, filters, derivations, and unambiguous joins.
5. **Business rules (repeated markdown + code).** Keep simple local transformations inline. Give each complex
   rule a named documentation cell followed by a pure DataFrame-in/DataFrame-out function and a separate call.
6. **Output contract (markdown + code).** Define each table's ordered columns, Spark datatypes, which values
   are always set, column descriptions, table description, grain, primary identifier, and relationship
   identifiers in one visible place. Check column names and align the final DataFrame before publication.
7. **Validation tests (reserved).** Leave data validation tests as the next iteration; do not mix exploratory
   displays into the production flow. Pure rule functions must remain independently callable by future tests.
8. **Publish (code).** Write only contract-aligned DataFrames with their descriptions. Keep reads and writes
   outside business-rule functions.

Use one responsibility per cell. A markdown cell explains business meaning and decisions; it should not
narrate obvious PySpark syntax. In a Fabric `.py` notebook, write blank markdown lines as `# ` (hash followed by a
space); a bare `#` can be dropped on import and merge paragraphs or tables.

## Grain and identifiers

- Declare each output table's grain before modelling it, for example: "One row per purchase invoice line."
  If the grain is not obvious from agreed business meaning or source semantics, stop and ask the user to decide;
  do not infer it from whichever source key happens to be convenient.
- Identify the smallest natural key that uniquely represents that grain. Use a composite key when one column is
  insufficient. Include `dpmeta_source_system_id` in the composite when the source's identifier is only unique
  within one source system.
- `dpmeta_uid` is the table grain's identifier. Derive it deterministically from the complete natural key; do
  not use row numbers, random UUIDs, execution timestamps, or processing order.
- Each modelled table's `dpmeta_uid` must be unique; duplicates on a Direct Lake relationship's "one" side
  cause failures. Source-aligned CDC history is different: its `dpmeta_uid` repeats across versions. Data
  validation tests are a future iteration; do not claim that uniqueness was verified without evidence.
- Keep the natural-key columns in the contract so the business meaning of `dpmeta_uid` remains visible and
  traceable. Document every component used to derive it.
- A transformation or join preserves the declared grain unless a named business rule explicitly documents a
  different output grain.

## DataFrame naming and joins

Use predictable names that expose role and stage:

```text
<entity>_source_dataframe
<entity>_base_dataframe
<entity>_with_<business_rule>_dataframe
<entity>_dataframe
```

Avoid vague or abbreviated names such as `df`, `temp_dataframe`, or numbered DataFrames. Before a join, project
each input to only the required columns and rename ambiguous columns to their contract names.

Do not alias DataFrames in joins. Give each DataFrame an unambiguous variable name and use its full name in
qualified column references so provenance remains visible:

```python
purchase_invoice_lines_base_dataframe.join(
    purchase_order_relationships_dataframe,
    purchase_invoice_lines_base_dataframe.purchase_order_line_source_identifier
    == purchase_order_relationships_dataframe.purchase_order_line_source_identifier,
    "left",
)
```

Always state the join type. For a simple join, the named DataFrames and full column references should make the
relationship evident. When matching, fallback, cardinality, or row-expansion behavior requires explanation,
treat the join as a named business rule.

## Inline transformations versus named business rules

Keep a transformation inline when its meaning is obvious from the operation and its effect is local:

- renaming a source column to the contract name;
- casting to the contract datatype;
- selecting or ordering columns;
- filtering explicitly to current CDC rows;
- deriving a direct value such as `quantity * unit_price` with already-defined units;
- an unambiguous key-based join that only brings required attributes or relationship keys.

Use a named business rule when the logic contains business judgment, multiple branches, fallback precedence,
temporal matching, allocation, classification, deduplication policy, currency conversion, or a join whose
meaning is not evident from keys alone.

Document a complex rule immediately above its implementation with:

- **Business meaning:** what decision or definition the rule implements.
- **Inputs and grain:** required DataFrames and the expected row grain of each.
- **Logic:** conditions, precedence, matching window, and formulas in business terms.
- **Exceptions:** null, missing-match, duplicate-match, and fallback behavior.
- **Output:** columns added or changed and whether row count or grain may change.
- **Source:** approving owner, policy, specification, or `TODO` when confirmation is still required.

Implement it as a pure transformation:

```python
def add_purchase_order_relationships(
    purchase_invoice_lines_dataframe,
    invoice_purchase_order_links_dataframe,
    purchase_order_lines_dataframe,
):
    return (...)


purchase_invoice_lines_with_purchase_order_dataframe = add_purchase_order_relationships(
    purchase_invoice_lines_base_dataframe,
    invoice_purchase_order_links_dataframe,
    purchase_order_lines_dataframe,
)
```

The function must receive every DataFrame dependency as an argument, return a new DataFrame, and contain no
`spark.table`, write, `display`, `show`, `collect`, or hidden notebook-global dependency. Use descriptive
function and stage names. Do not create a function merely to wrap one rename, cast, selection, or obvious join.

For repeated values within each source row, prefer a single projection using `F.inline(F.array(...))` or
`unpivot` when the shape fits, rather than stacking branches with `functools.reduce`. This is not a substitute
for unions of independent DataFrames. Avoid intermediate `print(dataframe.count())` calls: each can recompute
the transformations from the source.

## Names and deployment

- Use full, descriptive words in authored names, code values, labels, markdown, and descriptions. Exceptions are
  established system names (such as HFM, OAC, and RPD), ISO codes, platform conventions (`dpmeta_*`, `lh_`,
  `nb_`, `ws_`), PySpark aliases `F` and `T`, and source names or values when reading or quoting them.
- A published column or code-value rename changes the contract. First identify downstream consumers and any
  identifiers derived from the renamed value; agree on the migration rather than silently breaking them.
- Resolve the workspace with `notebookutils.runtime.context["currentWorkspaceName"]`; never hard-code a
  development workspace. In table references, write lakehouse, schema, and table names in full where used
  instead of building namespace or table-name variable chains. Quote workspace identifiers when needed.
- Cross-product reads still go through the domain workspace's `lh_shortcuts`; provision the appropriate
  shortcuts for each deployment environment. Livy supplies the workspace through `nor-livy-session`, not a
  notebook-specific fallback.

## Nulls and deterministic results

- Preserve missing or unavailable values as `null`. Do not replace them with `0`, `-1`, an empty string, or
  `"UNKNOWN"` unless that value is part of the agreed business contract.
- Document null behavior when a business rule calculates, classifies, or matches values.
- The same inputs must produce the same output. Do not use random identifiers, processing-order-dependent
  deduplication, `current_timestamp()`, or environment-dependent values in modelling transformations.
- When duplicates require resolution, use documented business ordering columns and deterministic tie-breakers.

## Dates, times, and timestamps

- A document or business date is a recorded business fact, not an instant to normalize. Never timezone-convert,
  shift, truncate, or otherwise change invoice dates, order dates, accounting dates, document times, or similar
  source business values.
- Use `DateType` for a true calendar date without time-of-day meaning. Parsing may change its storage datatype,
  but must preserve the recorded calendar value exactly.
- Preserve a source-local business time or timestamp in its original business context. Do not assume a timezone
  or convert it to UTC. Document the source timezone separately when it is known.
- Normalize to UTC only for a genuine technical or event instant with a known offset or timezone, such as an
  ingestion timestamp. Name and describe it as an instant so it cannot be confused with a document value.
- Prefer `timestamp` for technical instants. When a business contract needs a source-local time or timestamp,
  agree on a representation with the business owner and verify its consumer support; do not silently shift,
  truncate, or discard the value. Avoid `timestamp_ntz`; Direct Lake support was not checked in the publication
  spike.

## Output contract and Delta descriptions

For a documented full refresh, define the contract once near publication with ordered columns, datatypes, and
column comments. Keep the table description beside it. In Fabric Runtime 2.0 (Spark 4.1.1, Delta 4.2.0), the
following pattern was observed to publish the data, column order, datatypes, column descriptions, and table
description in one Delta write:

```python
import notebookutils
from pyspark.sql import types as T

workspace = notebookutils.runtime.context["currentWorkspaceName"]

purchase_invoice_line_contract = (
    T.StructType()
    .add("dpmeta_uid", "string", metadata={"comment": "Deterministic purchase invoice line identifier. Always set."})
    .add("line_amount", "decimal(18,2)", metadata={"comment": "Line amount in invoice_currency_code."})
    .add("invoice_currency_code", "string", metadata={"comment": "ISO 4217 currency code of line_amount."})
)

def publish_table(model_dataframe, contract, table_identifier, table_description):
    missing_columns = sorted(set(contract.fieldNames()) - set(model_dataframe.columns))
    unexpected_columns = sorted(set(model_dataframe.columns) - set(contract.fieldNames()))
    if missing_columns or unexpected_columns:
        raise ValueError(
            f"contract mismatch for {table_identifier}: "
            f"missing={missing_columns} unexpected={unexpected_columns}"
        )
    (
        model_dataframe.to(contract)
        .writeTo(table_identifier)
        .using("delta")
        .tableProperty("comment", table_description)
        .createOrReplace()
    )
    print(f"published {table_identifier}: {spark.table(table_identifier).count()} rows, {len(contract.fields)} columns")

publish_table(
    purchase_invoice_line_dataframe,
    purchase_invoice_line_contract,
    f"`{workspace.replace('`', '``')}`.lh_purchase_invoice.purchase_invoice.purchase_invoice_line",
    "One row per purchase invoice line, identified by dpmeta_uid.",
)
```

The helper is useful when publishing several tables; for one table, inline the same steps rather than adding a
helper just in case. Use Spark type names in `.add`: `string`, `integer`, `long`, `decimal(p,s)`, `boolean`,
`date`, and `timestamp`; `int` failed while `integer` worked in the Runtime 2.0 spike. Descriptions are plain
Python strings, not SQL literals. Omit the nullable argument.

`DataFrame.to` aligns column order, compatible datatypes, and metadata, but the spike found that it can drop
extra columns or fill missing nullable columns with nulls; check names first as shown. Make intentional casts
and rounding explicit where needed, and surface incompatible conversions, overflow, and other failures. Casting
behavior can depend on the runtime and settings: verify it on the target rather than assuming every conversion
fails on invalid values.

Always supply the table comment: the spike found that replacement without it clears the existing description.
Do not create an empty table or issue per-column comment statements for this full-refresh pattern. The spike also
found that `saveAsTable` overwrite without `overwriteSchema` can ignore changed comments, `.option("comment")`
only sets the table description on creation, and `.option("description")` does not set it.

Verify table and column descriptions as a one-time check outside the notebook after initial publication and
when the contract changes, never on every run. Report what was actually verified. Confirm the pattern and
metadata behavior on a different runtime before relying on it; do not silently substitute a write that loses
descriptions. This replacement pattern is not an incremental publication strategy.

Do not put `NOT NULL` or `nullable=False` in this contract. DataFrame nullability is a query-plan promise, not
a data check; end a description with "Always set." when consumers require a value. In the spike, `DataFrame.to`
rejected plan-nullable expressions against NOT NULL fields, replacement writes dropped Delta NOT NULL constraints,
`ALTER ... SET NOT NULL` was rejected, and the SQL endpoint showed columns as nullable. Do not treat these
observations as guarantees for every runtime.

Business-product Delta table and column descriptions are the source for semantic models, normally read through
Direct Lake. A model may exceptionally own tables and descriptions of its own. Use the SQL endpoint for
analysts' ad-hoc queries, not as the semantic model's default data path or source of Delta descriptions; the
spike found that the endpoint did not expose those descriptions.

Prefer consumer-friendly `string`, `integer`/`long`, `decimal(p,s)`, `boolean`, and `date`, with `timestamp` for
technical instants. Avoid complex and binary types unless a consumer requirement and compatibility are established.

## Numeric and currency datatypes

- Use `DecimalType`, never `DoubleType` or `FloatType`, for monetary amounts, prices, exchange rates, and other
  values where binary floating-point error is unacceptable.
- Preserve the source precision when it is known and sufficient. Otherwise choose precision and scale from the
  business range and smallest meaningful unit; do not copy one arbitrary decimal type to every numeric column.
- A common starting point is `DecimalType(18, 2)` for amounts, `DecimalType(18, 6)` for quantities and unit
  prices, and `DecimalType(18, 8)` for exchange rates, but source and business requirements override these.
- Pair every amount with an unambiguous currency column named `<amount_name>_currency_code` when different
  amounts in a row may have different currencies. A shared `currency_code` is acceptable only when its scope
  is clear for every monetary column in that table.
- Use ISO 4217 uppercase currency codes. Name converted values explicitly, for example `line_amount_eur`.
- State rate direction, date/time matching, fallback behavior, and rounding mode in the currency-conversion
  business rule. Cast and round once at the contract boundary.

## Relationships between data products

- A relationship stores the target row's published `dpmeta_uid` and names its provenance explicitly, for
  example `supplier_dpmeta_uid`, `purchase_order_dpmeta_uid`, or `purchase_order_line_dpmeta_uid`. Its datatype
  and meaning must match the target product's identifier contract. Related columns must have the same datatype;
  duplicates on the "one" side prevent Direct Lake relationships from working.
- Publish relationship keys, not copied descriptors. For example, a purchase invoice line keeps
  `purchase_order_dpmeta_uid`; consumers obtain purchase-order number and status from the purchase-order
  product.
- Document the target product and table, cardinality, optionality, and unmatched-row behavior in the output
  contract. Delta Lake does not make an unenforced foreign-key assumption true.
- Preserve the output's grain when enriching a relationship. Resolve duplicate upstream keys before the join
  or make the intentional one-to-many expansion explicit as a named business rule.
- For a genuine many-to-many relationship, publish an explicitly named bridge table such as
  `<left_concept>_<right_concept>_relationship`, containing the two target identifiers and relationship
  attributes only.
- Cross-product reads use `lh_shortcuts` and clearly named DataFrames with full column references. Do not use
  DataFrame aliases. Avoid workspace IDs, item IDs, ABFSS paths, and duplicated source-system names in the
  business contract.

## Publication rules

- Complete transformations and check the contract column names before writing each table.
- Use deterministic full replacement only when full-refresh semantics are intended and documented; otherwise
  define the product's incremental publication strategy explicitly, including concurrency safety and preserving
  descriptions. Do not use `createOrReplace` as a substitute for incremental semantics.
- Keep table writes together at the end of the notebook. Reads stay near the beginning, transformations stay
  in the middle, and a business-rule function never reads or publishes data.
- Report the published table identifier, row count, and number of contract columns. Report catalog description
  verification when performed; do not claim it was verified on runs where metadata was not read back.
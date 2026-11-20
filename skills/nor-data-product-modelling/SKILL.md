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
2. **Imports and destinations (code).** Import Spark functions and types; define the product name and output
   table identifiers or paths in one place.
3. **Input products (markdown + code).** List every source table and what it contributes, then read it. For each
   source-aligned CDC table, state and implement whether the model uses current rows
  (`dpmeta_is_current = true`) or historical versions. Apply that filter immediately after the read, before
  projecting away metadata columns or joining. Do not leave this implicit.
4. **Base model (markdown + code).** Declare the grain, identifiers, core columns, straightforward renames,
   casts, filters, derivations, and unambiguous joins.
5. **Business rules (repeated markdown + code).** Keep simple local transformations inline. Give each complex
   rule a named documentation cell followed by a pure DataFrame-in/DataFrame-out function and a separate call.
6. **Output contract (markdown + code).** Define each table's ordered columns, Spark datatypes, nullability,
   column descriptions, table description, grain, primary identifier, and relationship identifiers in one
   visible place. Align and validate the final DataFrame against that contract before publication.
7. **Validation tests (reserved).** Leave this as the next iteration; do not mix exploratory displays into the
   production flow. Pure rule functions must remain independently callable by future tests.
8. **Publish (code).** Write only contract-aligned DataFrames, then persist table and column descriptions in
   the Delta catalog. Keep reads and writes outside business-rule functions.

Use one responsibility per cell. A markdown cell explains business meaning and decisions; it should not
narrate obvious PySpark syntax.

## Grain and identifiers

- Declare each output table's grain before modelling it, for example: "One row per purchase invoice line."
  If the grain is not obvious from agreed business meaning or source semantics, stop and ask the user to decide;
  do not infer it from whichever source key happens to be convenient.
- Identify the smallest natural key that uniquely represents that grain. Use a composite key when one column is
  insufficient. Include `dpmeta_source_system_id` in the composite when the source's identifier is only unique
  within one source system.
- `dpmeta_uid` is the table grain's identifier. Derive it deterministically from the complete natural key; do
  not use row numbers, random UUIDs, execution timestamps, or processing order.
- Keep the natural-key columns in the contract so the business meaning of `dpmeta_uid` remains visible and
  traceable. Document every component used to derive it.
- A transformation or join preserves the declared grain unless a named business rule explicitly documents a
  different output grain.

## DataFrame naming and joins

Use predictable names that expose role and stage:

```text
<entity>_source_df
<entity>_base_df
<entity>_with_<business_rule>_df
<entity>_df
```

Avoid generic names such as `df`, `temp_df`, or numbered DataFrames. Before a join, project each input to only
the required columns and rename ambiguous columns to their contract names.

Do not alias DataFrames in joins. Give each DataFrame an unambiguous variable name and use its full name in
qualified column references so provenance remains visible:

```python
purchase_invoice_lines_base_df.join(
    purchase_order_relationships_df,
    purchase_invoice_lines_base_df.purchase_order_line_source_id
    == purchase_order_relationships_df.purchase_order_line_source_id,
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
    purchase_invoice_lines_df,
    invoice_po_links_df,
    purchase_order_lines_df,
):
    return (...)


purchase_invoice_lines_with_po_df = add_purchase_order_relationships(
    purchase_invoice_lines_base_df,
    invoice_po_links_df,
    purchase_order_lines_df,
)
```

The function must receive every DataFrame dependency as an argument, return a new DataFrame, and contain no
`spark.table`, write, `display`, `show`, `collect`, or hidden notebook-global dependency. Use descriptive
function and stage names. Do not create a function merely to wrap one rename, cast, selection, or obvious join.

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

## Output contract and Delta descriptions

Define the contract once near publication. Prefer an explicit `StructType` whose `StructField`s state datatype
and nullability and carry the column description in metadata. Keep table-level metadata beside it:

```python
from pyspark.sql.types import DecimalType, StringType, StructField, StructType

purchase_invoice_line_schema = StructType([
    StructField(
    "dpmeta_uid",
    StringType(),
        False,
    {"comment": "Deterministic identifier derived from the purchase invoice line natural key."},
    ),
    StructField(
        "line_amount",
        DecimalType(18, 2),
        True,
        {"comment": "Line amount in invoice_currency_code."},
    ),
    StructField(
        "invoice_currency_code",
        StringType(),
        False,
        {"comment": "ISO 4217 currency code of monetary invoice amounts."},
    ),
])

purchase_invoice_line_table_description = (
  "One row per purchase invoice line, identified by dpmeta_uid."
)
```

Before writing, select contract columns in order, cast deliberately, and fail on missing, unexpected, or
incompatible columns. Do not rely on types inherited accidentally through earlier stages.

After writing the Delta table, persist the table description and every field's `comment` with the Spark SQL
catalog operations supported by the active Fabric runtime (for example `COMMENT ON TABLE` and
`ALTER TABLE ... ALTER COLUMN ... COMMENT`). Read the table metadata back and verify the descriptions. Python
comments beside a `select()` and schema metadata that has not been verified in the catalog are documentation
for the notebook, not a published data-product contract.

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
  and meaning must match the target product's identifier contract.
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

- Complete all transformations and contract checks before the first write.
- Use deterministic full replacement only when full-refresh semantics are intended and documented; otherwise
  define the product's incremental publication strategy explicitly.
- Keep table writes together at the end of the notebook. Reads stay near the beginning, transformations stay
  in the middle, and a business-rule function never reads or publishes data.
- Report the published table identifier, row count, contract columns, and verified catalog descriptions.
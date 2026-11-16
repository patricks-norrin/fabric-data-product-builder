---
name: nor-lakehouse-query
description: Read-only T-SQL over the Delta tables of a data product lakehouse through the Fabric SQL endpoint MCP server - discover schemas, tables and columns, count and sample rows, query current versus historical change-history rows, validate a CDC or modelling result. Use when you need to look at the data in lh_<id> quickly; fall back to nor-livy-session when MCP is unavailable or the endpoint cannot read a table.
---

# nor-lakehouse-query

Answer questions about the data in a lakehouse with real rows, not with assumptions. This skill is **read-only**: it
never creates, changes or deletes anything. Mutations belong to the notebooks and pipelines.

## Prerequisites
- Querying is a Fabric-connected action: load `nor-data-product-architecture` and complete `nor-environment-check`
  first, as the builder's Fabric connection gate requires.
- Confirm a tool whose name ends in `execute_query` is in your tool list. The plugin registers the server as
  `fabric-sqlendpoint`, so it normally appears as `fabric-sqlendpoint-execute_query`. Invoke the name you actually
  see. If it is missing, say so, give the user the registration note below, and use the Livy fallback.
- The MCP server signs in with the user's existing Azure CLI session (`az login`); never ask for, print or paste a
  token. If calls fail with 401/403, ask the user to run `az login --tenant <tenant-id> --allow-no-subscriptions`.

## Resolve the target
```bash
fab get "<ws_name>.Workspace" -q id
fab get "<ws_name>.Workspace/lh_<id>.Lakehouse" -q id
fab get "<ws_name>.Workspace/lh_<id>.Lakehouse" -q "properties.sqlEndpointProperties.provisioningStatus"
```
Pass the workspace id as `workspaceId` and the lakehouse item id as `itemId`. The SQL endpoint id
(`properties.sqlEndpointProperties.id`) is accepted as `itemId` too. Never guess a GUID. Proceed only when the
provisioning status is `Success`.

```text
fabric-sqlendpoint-execute_query(workspaceId, itemId, query)
```

Use the global endpoint the plugin registers. The item-scoped endpoint still requires `workspaceId` and `itemId` on
every call, so it adds nothing here. The result is a CSV resource; failures come back as `isError` with the SQL
error text.

## Rules
- **SELECT and catalog queries only.** Never send `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP` or
  `TRUNCATE`; the tool is declared destructive, so the restriction is yours to keep. A request to change data is a
  request to change a notebook: route it to the owning skill.
- **One T-SQL batch per call.** No `GO` and no multiple result sets.
- **Bound every query** with `TOP n`, a `WHERE`, or an aggregate. Results are reported to cap at 10,000 rows and calls
  are rate limited, so combine related questions into one query and sample before widening.
- **Discover before you query.** Never guess a schema, table or column name:
  ```sql
  SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA NOT IN ('sys', 'queryinsights', 'INFORMATION_SCHEMA')

  SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = '<schema>' AND TABLE_NAME = '<table>' ORDER BY ORDINAL_POSITION
  ```
- **Report the evidence.** Quote the query and the real rows or counts it returned, including when the answer is
  zero rows. Never carry a number over from an earlier turn or from a notebook's own output.

## What you can query
- Only Delta tables under `Tables/`. Schema is the product identifier and table is the dataset, for example
  `frankfurter_api.exchange_rates`. Raw files under `Files/` are not visible here; inspect them with `fab ls` or
  Livy.
- Source-aligned tables are change history (SCD2). Each business key (`dpmeta_uid`) has one row per version:
  `dpmeta_object_version_start_time`, `dpmeta_object_version_end_time`, `dpmeta_is_current`,
  `dpmeta_loaded_to_dataplatform`, `dpmeta_payload_hash`, `dpmeta_input_file_name`, `dpmeta_source_system_id`.
  Modelled (Foundational and Business) tables carry their own output contract instead.
- Metadata for a modelled product lives in its Delta descriptions and `data_product_meta` tables when present.

### Current rows versus history
A bare `COUNT(*)` over change history counts versions, not entities. Decide which question was asked:

```sql
-- Wrong for "how many suppliers exist": counts every version of every supplier
SELECT COUNT(*) FROM oracle_ebs_finland.ap_suppliers;

-- Right: one row per business key at its latest version
SELECT COUNT(*) FROM oracle_ebs_finland.ap_suppliers WHERE dpmeta_is_current = 1;

-- History of one key, oldest first
SELECT * FROM oracle_ebs_finland.ap_suppliers
WHERE dpmeta_uid = '<uid>' ORDER BY dpmeta_object_version_start_time;

-- Last successful load into the change history
SELECT MAX(dpmeta_loaded_to_dataplatform) FROM oracle_ebs_finland.ap_suppliers;
```

## When the endpoint cannot answer
| Symptom | Meaning | Action |
|---|---|---|
| `Invalid column name` / `Invalid object name` | The name is wrong, or the endpoint has not synced a new table or column yet. | Re-run the discovery queries. If the object exists in `fab table schema` but not here, the endpoint metadata lags: use the Livy fallback and tell the user. |
| `Failed to complete the command because the underlying location does not exist` | The endpoint metadata points at Delta files that were since rewritten or removed, typical for a shortcut table or right after a CDC run. | Do not retry in a loop. Use the Livy fallback for the answer and tell the user the endpoint metadata is stale. Refreshing it is a user decision. |
| `isError` with a DML/permission message | You sent a write, or the user lacks access. | Stop; do not work around it. |
| No `execute_query` tool | MCP server not registered. | Livy fallback. |

## Livy fallback
Use `nor-livy-session`: `create lh_<id>`, then `statement "spark.sql('SELECT ...').show(20, truncate=False)"`, then
`delete`. Spark reads the Delta tables directly, so it does not depend on SQL endpoint sync. Prefer MCP for quick
reads because it needs no session start.

## MCP registration (when the tool is missing)
The toolpack ships the server in its plugin configuration. Outside that, register the global endpoint
`https://api.fabric.microsoft.com/v1/mcp/dataPlane/sqlEndpoint` as `fabric-sqlendpoint` in your MCP client. Microsoft
documents it at
[Fabric Data Warehouse MCP server](https://learn.microsoft.com/fabric/data-warehouse/data-warehouse-mcp-server); that
page names the tool `executeSQL`, while the live server lists `execute_query` with these three arguments.

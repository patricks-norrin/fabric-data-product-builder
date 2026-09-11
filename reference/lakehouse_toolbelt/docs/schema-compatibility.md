# Schema Compatibility

`align_dataframe_to_delta_change_history_schema(...)` is the main guardrail for schema drift before writing into an existing change-history Delta table.

## When To Use It

Use it immediately before `upsert_delta_change_history(...)` when the target change-history table may already exist.

```python
df_validated = lakehouse_toolbelt.align_dataframe_to_delta_change_history_schema(df_with_dpmeta, dataset)
lakehouse_toolbelt.upsert_delta_change_history(df_validated, dataset)
```

## Supported Modes

The mode comes from `dataset.schema_compatibility_mode` and defaults to `merge_safe`.

| Mode | Extra columns in incoming data | Missing columns in incoming data | Type mismatch |
| --- | --- | --- | --- |
| `merge_safe` | Warn and drop | Fail | Fail |
| `strict` | Fail | Fail | Fail |
| `warn_only` | Warn and drop | Warn and continue | Warn |
| `ignore` | Ignore | Ignore | Ignore |

## Recommended Default

`merge_safe` is the safest general-purpose option because it allows harmless extra columns to be dropped while still failing on the kinds of issues that can break historical consistency.

## What The Function Does

High-level behavior:

1. Refresh the dataset's Delta table state.
2. Return the incoming DataFrame unchanged if no change-history table exists yet.
3. Compare incoming columns to the existing target table.
4. Drop or reject extra columns based on the selected mode.
5. Reject or warn about missing columns based on the selected mode.
6. Reorder the incoming columns to match the target table.
7. Compare datatypes after removing schema metadata from the comparison.

## Primary Function vs Internal Helper Functions

Treat `align_dataframe_to_delta_change_history_schema(...)` as the primary function.

It internally uses schema-cleanup helpers to remove metadata before comparing schemas. Those helpers support the main function, but they are not intended as part of the normal standard workflow.

## Practical Guidance

- Use `merge_safe` unless you have a reason to be stricter or looser.
- Use `warn_only` only when you explicitly accept the risk of partial compatibility.
- Use `ignore` sparingly, because it disables the checks that protect the target Delta table from silent drift.

## Interaction With The Upsert Workflow

Schema alignment is not the write itself. It prepares the incoming DataFrame so that the subsequent upsert has a predictable target shape.

Recommended order:

1. Read raw data.
2. Optionally convert timestamps.
3. Add `dpmeta_*` columns.
4. Align schema.
5. Upsert into the change-history Delta table.
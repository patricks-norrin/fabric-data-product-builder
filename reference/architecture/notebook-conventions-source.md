# Notebook conventions (imported from academy project, to be curated)

# PySpark Notebook Conventions for Fabric

## Cell Structure
- First cell: parameters with defaults (processing_date, lakehouse_name, etc.)
- Imports cell: all dependencies upfront
- Final cell: validation (row counts, schema, sample)

## Code Style

### DataFrame Naming Convention
**✅ Use `_df` suffix for DataFrame variables:**
```python
# Correct naming
raw_df = spark.read.json(path)
validated_df = raw_df.filter(F.col("status") == "active")
result_df = validated_df.select("id", "name", "date")
```

**❌ NEVER use `df_` prefix:**
```python
# Wrong - forbidden style
df_raw = spark.read.json(path)
df_validated = df_raw.filter(F.col("status") == "active")
df_result = df_validated.select("id", "name", "date")
```

**Why:** The `_df` suffix clearly indicates the variable type while keeping the meaningful name first, improving readability when variables are alphabetically sorted.

### Use Meaningful Names, Not Generic
**✅ Use descriptive names when context is clear:**
```python
# Good - meaningful names
exchange_rates_df = spark.read.json(path)
customers_df = spark.read.parquet(customer_path)
validated_orders_df = orders_df.filter(F.col("status") == "confirmed")
```

**❌ NEVER use generic `df` except in loops:**
```python
# Wrong - generic name when meaning is known
df = spark.read.json(path)  # What data is this?
df2 = spark.read.parquet(customer_path)  # Unclear!
```

**When to use generic names:**
```python
# Only acceptable in loops iterating over datasets
for dataset_name, dataset in data_product.datasets.items():
    df = spark.read.format("csv").load(dataset.file_path_raw)  # OK in loop
    # ... process df
```

**Why:** Meaningful names make code self-documenting and easier to understand, especially in long notebooks with multiple DataFrames.

### Line Continuation
**✅ Use parentheses `()` for multi-line expressions:**
```python
result_df = (raw_df
    .withColumn("date", F.col("timestamp").cast("date"))
    .withColumn("year", F.year("date"))
    .filter(F.col("status") == "active")
)
```

**❌ NEVER use backslash `\` for line continuation:**
```python
# Wrong - forbidden style
result_df = raw_df \
    .withColumn("date", F.col("timestamp").cast("date")) \
    .withColumn("year", F.year("date"))
```

**Why:** Parentheses are more readable, less error-prone (no trailing whitespace issues), and the preferred Python style.

## File Operations (CRITICAL)

**Lakehouse paths are ABFSS URLs (abfss://...), NOT local filesystem paths.**

### ✅ ALWAYS use `notebookutils.fs` for lakehouse file operations:
- `notebookutils.fs.put(path, content, overwrite=True)` — write string content to file
- `notebookutils.fs.mkdirs(path)` — create directory structure
- `notebookutils.fs.ls(path)` — list files/directories
- `notebookutils.fs.rm(path, recurse=True)` — delete files/directories
- `notebookutils.fs.cp(src, dst, recurse=True)` — copy files/directories
- `notebookutils.fs.exists(path)` — check if file/directory exists
- `notebookutils.fs.head(path, max_bytes=1024*100)` — read first bytes of file

### ❌ NEVER use local filesystem operations for lakehouse paths:
- `os.makedirs()`, `os.path.exists()`, `os.listdir()` — local filesystem only
- `open()`, `with open()` — local filesystem only
- `pathlib.Path()` — local filesystem only
- **These will fail or create files in the wrong location when working with lakehouse paths**

### Reading data with Spark:
- Use Spark readers: `spark.read.json(path)`, `spark.read.parquet(path)`, `spark.read.csv(path)`
- Lakehouse paths work directly — relative paths resolve to default lakehouse in Spark notebooks
- For JSON: `spark.read.option("multiLine", True).json(path)` for pretty-printed JSON arrays

### Writing data with Spark:
- Use DataFrame writers: `df.write.format("delta").save(path)` or `df.write.saveAsTable(table_name)`
- Never use Python file I/O to write DataFrames

### When to call `mcp_fabric-notebo_get_notebookutils_doc`:
- Before ANY file write/create/delete operation in notebooks
- When unsure about `notebookutils.fs` API parameters or behavior
- When working with file operations on OneLake paths

## DataFrame Operations
- Use PySpark, not pandas (unless explicitly small local data)
- Prefer columnar operations over UDFs
- Use window functions over self-joins for ranking/running totals
- Broadcast joins for small dimensions (<100MB)
- Never `.collect()` on large DataFrames

## Delta Lake
- All tables in Delta format
- MERGE for upserts on natural keys
- Run OPTIMIZE + ZORDER after writes to Silver/Gold
- VACUUM periodically (RETAIN 168 HOURS minimum)

## Metadata Columns (Bronze)
Always add: `ingestion_timestamp`, `source_file`, `batch_id`

## Data Ingestion
- Cannot read from HTTP/HTTPS URLs directly in Spark
- Stage external data to `Files/` first using `notebookutils.fs.put()` or Fabric pipelines
- Then read from lakehouse paths: `spark.read.format("csv").load(path)`

## Incremental Loading with modifiedAfter (CRITICAL ERROR HANDLING)

When using `modifiedAfter` filter for incremental loads, **ALWAYS wrap in try/except**.

**Why:** When NO files match the `modifiedAfter` filter, Spark cannot infer schema and throws `AnalysisException` **during** `.load()` — NOT after returning an empty DataFrame.

### ✅ Correct Pattern:
```python
# Get latest loaded timestamp
latest_timestamp = dataset.get_delta_change_history_dpmeta_loaded_to_dataplatform()

# Build reader with optional time filter
df_reader = spark.read.format("json").option("recursiveFileLookup", "true")
if latest_timestamp:
    df_reader = df_reader.option("modifiedAfter", latest_timestamp)

# Wrap in try/except to handle schema inference failure
try:
    df = df_reader.load(dataset.file_path_raw)
    record_count = df.count()
    print(f"✓ Loaded {record_count:,} records")
    
    # ... process df normally (add metadata, upsert, etc.)
    
except Exception as e:
    # Handle schema inference failure when no new files exist
    if "Unable to infer schema" in str(e) or "AnalysisException" in type(e).__name__:
        print(f"ℹ No new data found since last load")
        print(f"Last load: {latest_timestamp}")
    else:
        # Re-raise unexpected errors
        raise
```

### ❌ Wrong Approach:
```python
# This doesn't work - .load() fails before returning DataFrame
df = df_reader.load(path)
if df.rdd.isEmpty():  # Never reached when modifiedAfter filters everything
    print("No data")
```

**When to use:** Any incremental load using `modifiedAfter` filter, especially with lakehouse_toolbelt CDC workflows.

## Environment
- Never hardcode workspace/lakehouse IDs
- Use parameters for paths, dates, thresholds
- Use `notebookutils.fs` for file operations (see File Operations section above)
- Orchestrate notebook executions with the product pipeline `pl_<id>`, not `notebookutils.notebook.run()`

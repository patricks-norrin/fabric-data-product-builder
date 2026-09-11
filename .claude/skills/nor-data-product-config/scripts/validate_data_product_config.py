#!/usr/bin/env python3
"""Validate a data product configuration locally (stdlib only).
Mirrors lakehouse_toolbelt's validator (dataset name uniqueness, allowed source/publish attributes incl.
project_configuration extras) and adds Norrin naming rules. Exit 1 on errors."""
import json, re, sys, pathlib

REPO = pathlib.Path(__file__).resolve().parents[4]
CONV = json.load(open(REPO / "reference/architecture/conventions.json"))
SOURCE_DEFAULTS = ["source_schema", "source_table", "filter_string", "base_url", "relative_url_template", "endpoint_query_parameters"]
PUBLISH_DEFAULTS = ["active", "included_columns"]
DATASET_KNOWN = {"dataset_name", "unique_identifier_columns", "exclude_columns_from_payload_checksum", "timestamp_columns_to_convert",
                 "object_version_timestamp_column", "schema_compatibility_mode", "object_version_number_column", "source_configuration",
                 "publish_configuration", "merge_strategy", "personal_data_columns"}

def main(path):
    errors, warnings = [], []
    cfg = json.load(open(path))
    proj_path = REPO / "configuration/data_product/project_configuration/project_configuration.json"
    proj = json.load(open(proj_path)) if proj_path.exists() else {}
    src_allowed = set(SOURCE_DEFAULTS + proj.get("source_configuration", {}).get("allowed_extra_attributes", []))
    pub_allowed = set(PUBLISH_DEFAULTS + proj.get("publish_configuration", {}).get("allowed_extra_attributes", []))

    for k in ("domain", "data_product_identifier", "datasets"):
        if k not in cfg: errors.append(f"missing top-level '{k}'")
    dpid = cfg.get("data_product_identifier", "")
    if dpid and not re.match(CONV["data_product_identifier"], dpid): errors.append(f"data_product_identifier '{dpid}' not snake_case")
    if pathlib.Path(path).stem != dpid: errors.append(f"file name '{pathlib.Path(path).name}' must be '{dpid}.json'")
    names = []
    for i, ds in enumerate(cfg.get("datasets", [])):
        n = ds.get("dataset_name")
        if not n: errors.append(f"datasets[{i}] missing dataset_name"); continue
        names.append(n)
        if not re.match(CONV["dataset_name"], n): errors.append(f"dataset '{n}' not snake_case")
        uid = ds.get("unique_identifier_columns")
        if not uid or not isinstance(uid, list): errors.append(f"dataset '{n}': unique_identifier_columns must be a non-empty list")
        for k in ds:
            if k not in DATASET_KNOWN: warnings.append(f"dataset '{n}': unknown attribute '{k}' (ignored by toolbelt)")
        for k in ds.get("source_configuration", {}) or {}:
            if k not in src_allowed: errors.append(f"dataset '{n}': source_configuration.'{k}' not allowed (defaults + project_configuration extras: {sorted(src_allowed)})")
        for k in ds.get("publish_configuration", {}) or {}:
            if k not in pub_allowed: errors.append(f"dataset '{n}': publish_configuration.'{k}' not allowed")
        if ds.get("object_version_timestamp_column") == "": warnings.append(f"dataset '{n}': object_version_timestamp_column empty -> load time used as version start")
        mode = ds.get("schema_compatibility_mode", "merge_safe")
        if mode not in ("merge_safe", "strict", "warn_only", "ignore"): errors.append(f"dataset '{n}': schema_compatibility_mode '{mode}' invalid")
    dupes = {x for x in names if names.count(x) > 1}
    if dupes: errors.append(f"duplicate dataset names: {sorted(dupes)}")

    for w in warnings: print(f"WARN  {w}")
    for e in errors: print(f"ERROR {e}")
    print(f"{'INVALID' if errors else 'VALID'}: {path} ({len(names)} datasets: {', '.join(names)})")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

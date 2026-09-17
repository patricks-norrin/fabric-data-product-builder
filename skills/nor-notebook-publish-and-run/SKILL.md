---
name: nor-notebook-publish-and-run
description: Publish a data product notebook definition (.py) into the product folder of the target workspace with fab import, run it headless with fab job run (parameters, workspace pool), poll the job instance and surface status and failureReason. Also exports a notebook back from Fabric to compare with the local definition.
---

# nor-notebook-publish-and-run

Run `scripts/` next to this file. Do not set `TOOLPACK_ROOT`. Add `--workspace ws_<name>` and/or
`--target <profile>` to override project defaults.

```bash
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" publish sample_api nb_extract_sample_api
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" run sample_api nb_extract_sample_api -P load_mode:string=incremental --timeout 1800
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" export sample_api nb_extract_sample_api --workspace ws_example --target dev
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" runs sample_api nb_extract_sample_api
```

- `publish` imports `ws_<name>/<id>/<nb>.Notebook` into the remote `<id>.Folder` (create or update, idempotent).
- `export` uses `<project>/.scratch/<ws_name>/export/<id>/` and compares the remote definition with the selected workspace package.
- `run` is synchronous (`fab job run`); on failure it prints the full `failureReason` from `fab api …/jobs/instances/<id>`. No exit value is exposed by the API — use `nor-livy-session` to see cell outputs.
- `run` appends the notebook and job IDs, status, Fabric start/end times, failure reason, and command exit code to
	`<project>/.scratch/<ws_name>/operational_manifest.jsonl`.
- Headless runs use the workspace default pool. Generated notebooks install the verified `lakehouse_toolbelt` wheel
	from `lh_workspace_shared_resources/Files/libraries/` before importing it, so an Environment binding is not required.
- Order for a data product: publish + run `nb_extract_<id>`, then `nb_cdc_<id>`; then check `fab ls`/`fab table schema` on the product lakehouse.

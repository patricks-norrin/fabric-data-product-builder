---
name: nor-notebook-publish-and-run
description: Publish a data product notebook with fab import or its pl_<id> DataPipeline with fab deploy backed by fabric-cicd. Start it headless with fab job start, wait with fab job run-status, surface status and failureReason, and show latest jobs with status. Also exports a notebook back from Fabric to compare with the local definition.
---

# nor-notebook-publish-and-run

Run `scripts/` next to this file. Do not set `TOOLPACK_ROOT`. Add `--workspace ws_<name>` and/or
`--target <profile>` to override project defaults.

```bash
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" publish sample_api nb_extract_sample_api
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" run sample_api nb_extract_sample_api --timeout 1800 --poll 30
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" start sample_api nb_extract_sample_api
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" wait sample_api nb_extract_sample_api --job-id <job id> --timeout 600
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" status
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" export sample_api nb_extract_sample_api --workspace ws_example --target dev
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" runs sample_api nb_extract_sample_api
```

Pipeline acceptance, after publishing both notebooks:

```bash
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" publish sample_api pl_sample_api
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" start sample_api pl_sample_api
bash "<directory of this SKILL.md>/scripts/run_notebook_job.sh" wait sample_api pl_sample_api --job-id "<printed pipeline job ID>" --timeout 600
```

Success requires `Completed` plus output table/row-count evidence, not merely job submission. On failure, give
`nor-spark-diagnostics` the pipeline item/workspace/job IDs printed by the runner. Its activity-query recipe
retrieves the actual notebook run/session and errors; do not pick the latest notebook run or rerun for logs.

- `publish` imports `ws_<name>/<id>/<nb>.Notebook` into the remote `<id>.Folder` (create or update, idempotent).
	A Git-sync Environment binding in the notebook header (all-zero `workspaceId`, `environmentId` = the
	Environment's `logicalId`) is rebound at publish time: the script finds that `logicalId` in a local
	`*.Environment/.platform`, then imports a scratch copy bound to the same-named Environment in the target
	workspace. Never hand-edit the local header to a workspace-specific id. If the Environment is missing locally or in
	the target workspace, `publish` stops before importing. Other bindings are imported unchanged. After a rebind,
	`export` reports the header ids as a difference; that is expected.
- Names starting with `pl_` are DataPipelines (`ws_<name>/<id>/pl_<id>.DataPipeline`). `publish` checks the definition,
	then calls `fab deploy` backed by `fabric-cicd`. Native logical references are rebound by the library using the
	local workspace package and already-published target notebooks. Publish the notebooks first. The scratch config
	publishes only the selected pipeline and disables orphan deletion; it never rewrites source definitions.
	`start`, `wait`, `run`, `status` and `runs` work the same way for pipelines; `export` compares notebooks only.
- `export` uses `<project>/.scratch/<ws_name>/export/<id>/` and compares the remote definition with the selected workspace package.
- `run` = `start` + `wait`. `start` submits the job with `fab job start --json` and prints the job instance id. `wait`
	polls `fab job run-status --json` every `--poll` seconds (default 30) and prints one line per poll:
	`[HH:MM:SSZ] <notebook> <status> <seconds waited>s (job <id>)`. Forward `-P`/`-C`/`-i` to `fab job start` unchanged.
- Exit codes: `0` Completed, `1` Failed/Cancelled/Deduped (prints the full `failureReason` and the `nor-spark-diagnostics`
	next step), `124` when `--timeout` (default 3600) elapses. A timeout stops only the local wait; the Fabric job keeps
	running and `wait` resumes it. Never rerun a notebook because its wait timed out.
- `wait` without `--job-id` resumes the latest job started for that notebook.
- `status` needs no notebook. It reads the current Fabric state of the latest job of every notebook started from this
	project and prints notebook, status, start/end times, job id and any failure reason.
- `runs` prints `fab job run-list` for the notebook, including runs started outside this project.
- No exit value is exposed by the API — use `nor-livy-session` to see cell outputs.
- `start` and `wait` append `job_requested`, `job_started`, `job_status` (each status change), `job_wait_timeout` and
	`job_finished` events with the item path, job id, Fabric start/end times and failure reason to
	`<project>/.scratch/<ws_name>/operational_manifest.jsonl`.
- Independent products may run concurrently: `start` each product's `pl_<id>`, then `wait` each one. The pipeline,
	not the caller, sequences notebooks inside a product.
- Headless runs use the workspace default pool. Generated notebooks install `lakehouse-toolbelt>=1.0.7`
	from `https://nrnctopublishpip.z6.web.core.windows.net/pip/` with `%pip install --no-index -f` before importing it.
	An Environment binding and a staged local wheel are not required. Report feed/network or installation failures;
	do not silently switch to another package source.
- Order for a data product: publish `nb_extract_<id>`, `nb_cdc_<id>`, then `pl_<id>`; run `pl_<id>`; then check `fab ls`/`fab table schema`
	on the product lakehouse. Run a single notebook headless only to isolate a failure.

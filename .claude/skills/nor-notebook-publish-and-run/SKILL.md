---
name: nor-notebook-publish-and-run
description: Publish a data product notebook definition (.py) into the product folder of the target workspace with fab import, run it headless with fab job run (parameters, Environment, workspace pool), poll the job instance and surface status and failureReason. Also exports a notebook back from Fabric to compare with the local definition.
---

# nor-notebook-publish-and-run

```bash
bash .claude/skills/nor-notebook-publish-and-run/scripts/run_notebook_job.sh publish frankfurter_api nb_extract_frankfurter_api
bash .claude/skills/nor-notebook-publish-and-run/scripts/run_notebook_job.sh run     frankfurter_api nb_extract_frankfurter_api [-P load_mode:string=incremental] [--timeout 1800]
bash .claude/skills/nor-notebook-publish-and-run/scripts/run_notebook_job.sh export  frankfurter_api nb_extract_frankfurter_api   # to .scratch/export/, prints diff vs local
bash .claude/skills/nor-notebook-publish-and-run/scripts/run_notebook_job.sh runs    frankfurter_api nb_extract_frankfurter_api   # recent job instances
```

- `publish` imports `notebooks/<id>/<nb>.Notebook` into `<id>.Folder` (create or update, idempotent).
- `run` is synchronous (`fab job run`); on failure it prints the full `failureReason` from `fab api …/jobs/instances/<id>`. No exit value is exposed by the API — use `nor-livy-session` to see cell outputs.
- Headless runs use the notebook's own Environment binding (set by `nor-notebook-author`) and the workspace default pool.
- Order for a data product: publish + run `nb_extract_<id>`, then `nb_cdc_<id>`; then check `fab ls`/`fab table schema` on the product lakehouse.

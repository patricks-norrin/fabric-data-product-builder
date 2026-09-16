# Microsoft Fabric skills — fit for the Norrin agent

Checked against `microsoft/skills-for-fabric` (local clone) and this toolpack’s
iteration-1 agent (`nor-data-product-builder`). Goal: keep Norrin as the owner of
naming, layers, and meaning; use Microsoft skills only for technical how-to.

**Verdict:** the Microsoft skill *shape* supports that split. The Microsoft skill
*content* does not, unless you cherry-pick and add explicit routing. Loading the
full `fabric-skills` bundle next to the Norrin agent will fight over architecture
and over notebooks/Livy.

---

## 1. Are they structured for “Norrin decides, MS implements”?

**Yes, at the dispatcher layer.** Microsoft uses Agents → Skills → Common.

| Layer | What it is | Implication for Norrin |
|---|---|---|
| Agents (`FabricDataEngineer`, `FabricIQ`, …) | Cross-workload orchestrators with their own architecture opinions | Competing orchestrators. Do not load beside `nor-data-product-builder`. |
| Skills (`skills/<name>/SKILL.md`) | Thin **mode dispatchers**. SKILL.md picks `authoring` / `consumption` / `operations`, then says *read* `references/<mode>.md` before any command | Right grain: Norrin agent can name a skill + mode for a technical job. |
| `references/` + `common/` | Endpoints, payload shapes, gotchas, telemetry | Actual technical value. Progressive disclosure — SKILL.md is not the procedure. |
| Hard sibling routing | “This artefact belongs to skill X; if X is unavailable, stop” | Good for cherry-picking *if* the Norrin agent is the router. Bad if spark-cli is loaded and believes it owns notebooks. |

Skills are also **discoverable independently**: YAML `description` is the trigger
text. APM can install one skill (`apm install … --skill spark-cli`). Copilot /
Cursor plugin install is a **whole bundle**, not a filter — cherry-picking in a
plugin host means either APM, or an explicit “do not use these skills” rule in
the Norrin agent.

**No, they are not convention-free.** Several skills encode Microsoft’s own
meaning of a platform:

- `e2e-medallion-architecture` and `FabricDataEngineer` own Bronze / Silver / Gold,
  one lakehouse with those three schemas (or three workspaces), and “finish with
  Direct Lake Power BI”.
- `spark-cli` **owns** notebook cells, named notebook runs, Livy sessions, and
  Materialized Lake Views. Its description will auto-trigger on the same words
  Norrin’s notebook/Livy skills use.
- Control plane is **`az rest`**, not `fab`. Attribution header
  `x-ms-fabric-skill: <name>` is mandatory on every `api.fabric.microsoft.com`
  call. `COMMON-CLI.md` does not mention the Fabric CLI. Exception:
  `git-integration-operations-cli` prefers `fab api` with `az rest` fallback.
- `sqldw-cli` and `fabriciq` assume Fabric MCP tools. This toolpack deliberately
  dropped Fabric MCP for agent operations (decision log §3).

So: **usable as libraries of REST/Spark/SQL procedures, not as drop-in
colleagues of the Norrin agent.**

---

## 2. Control-plane mismatch (will bite if ignored)

Norrin invariants (verified in this toolpack): `fab` for item/file/job control
plane; `az` token + curl only for Livy; `.py` notebook definitions; Environment
must live in the same workspace; `fab` token cannot drive a Livy Spark session.

Microsoft invariants: `az rest` + `.ipynb` `updateDefinition`; Livy as ad-hoc
PySpark (`spark-cli` consumption), notebooks as Jobs API (`spark-cli` authoring);
SQL via MCP `fabric-sqlendpoint-execute_query`.

If the Norrin agent loads `spark-cli` **authoring** without a routing rule, it
will try to create/run notebooks the Microsoft way and bypass
`nor-notebook-author` / `nor-notebook-publish-and-run`. Translate Microsoft
recipes to `fab` / existing Norrin scripts; do not let MS skills become a second
execution surface.

---

## 3. Shortlist for current Norrin agent scope

Current scope is **source-aligned extract + CDC** in `ws_extract`: config,
`lh_<id>`, `nb_extract_<id>`, `nb_cdc_<id>`, raw files, change-history tables.
Consumer-aligned products, pipelines, and promotion are deferred.

### Use — technical how-to, Norrin still names things

| MS skill | Mode(s) | Why it is useful | How the Norrin agent should call it |
|---|---|---|---|
| **spark-cli** | **operations** only | Failed / OOM / throttled Spark notebook or Livy run. Norrin has no diagnostics skill; publish-and-run only surfaces `failureReason`. | After a headless `fab job run` failure, when `failureReason` is not enough. Never for writing or publishing notebooks. |
| **spark-cli** | **authoring** *references only* | PySpark / `notebookutils` / `%%configure` / ABFSS path rules, Environment binding, schema-enabled lakehouse REST. | Read `references/authoring.md` and `common/SPARK-NOTEBOOK-AUTHORING-CORE.md` when implementing SOURCE SPECIFIC cells. Do **not** follow its “create notebook via REST `.ipynb`” path. |
| **sqldw-cli** | **consumption** | Row counts, `INFORMATION_SCHEMA`, lakehouse SQL endpoint checks. Better evidence channel than Livy `.show()` for the agent’s final report. | After CDC, to prove `Tables/<id>/<dataset>` row counts. Prefer `sqlcmd` fallback if Fabric MCP is not in the session (Norrin policy). Do not author warehouse tables. |
| **sqldw-cli** | **operations** (`lakehouse-health`) | Delta file health / `sys.sp_get_table_health_metrics` after CDC upserts. | Optional; only when investigating table health, not during the happy-path build. |
| **search-consumption-cli** | (single consumption skill) | Cross-workspace item lookup when the workspace is unknown. | Rare in this toolpack (`fabric_targets.json` already names the workspace). Useful for “is `lh_workspace_shared_resources` already in another workspace?” |
| **e2e-fabric-cost-estimation** | (standalone) | Capacity SKU vs Starter Pool, CU math. Complements `nor-environment-check` (which only WARNs on F2/F4 + Starter Pool). | When the user asks about SKU/cost, or environment-check WARN needs a sizing answer. Not during a product build. |

### Keep out of the current agent session

| MS skill / agent | Reason |
|---|---|
| **e2e-medallion-architecture** | Direct architecture competitor. Bronze/Silver/Gold schemas in one lakehouse vs Norrin’s one source = one `lh_<id>` with raw Files + SCD2 Tables. Will “complete” a build with Gold + Direct Lake. |
| **FabricDataEngineer** (and other MS agents) | Competing orchestrator. Delegates to medallion + spark-cli authoring. |
| **spark-cli consumption** | Overlaps `nor-livy-session`. Generic ad-hoc Livy; no Environment/toolbelt preamble, no `.py` cell loop, no verified `fab`-token-vs-`az`-token rule. |
| **spark-cli mlv** | Materialized Lake Views are not the CDC contract. Toolbelt SCD2 is. |
| **dataflows-cli** | Alternate extract construction. Architecture doc allows shortcuts/mirroring later; Dataflows are not the iteration-1 extract path. Loading it will steal “ingest from API” prompts. |
| Power BI / FabricIQ / Ontology / Eventhouse / Eventstream / Activator / Event Schema Set / Azure Monitor | Out of source-aligned scope. Business meaning starts at Foundational. |
| **sqldb-cli** | Fabric SQL database (OLTP), not lakehouse. |
| Migration skills (synapse / databricks / hdinsight / pipeline-migration) | Wrong job. |
| **onelake-catalog-govern-cli** | Tenant-admin / data-owner governance. Not a data-product build step; also write-capable. |
| **deployment-pipelines-authoring-cli** | ALM via deployment pipelines. Norrin’s deferred promotion path is `fab deploy` / Git, which this skill explicitly does not cover. |

---

## 4. Later-scope shortlist (not iteration 1)

When the toolpack grows past extract+CDC, these are the Microsoft skills worth
picking rather than rewriting.

| When Norrin needs… | Pick | Do not pick / do not duplicate |
|---|---|---|
| `pl_<id>` notebook orchestration | There is **no** general pipeline-authoring skill. `pipeline-migration` is Synapse→Fabric only; `e2e-medallion-architecture` sketches pipeline JSON as examples. | Do not invent a parallel “Fabric REST 101” skill. Either wait for an MS pipeline-cli, or write a thin Norrin skill that only encodes `pl_<id>` naming and activity graph, and copy REST shapes from `ITEM-DEFINITIONS-CORE.md`. |
| Git connect / commit / update / status | **git-integration-operations-cli** — already `fab api` first | Keep Norrin naming of workspace packages. This skill’s out-of-scope list includes `fab deploy` and `fabric-cicd`. |
| Per-environment GUIDs / value sets | **variable-library-cli** | Complements, does not replace, `fabric_targets.json` + `fab deploy` parameterization (see `docs/TODO.md`). |
| Foundational / Business semantic models | **semantic-model-authoring** | Norrin still owns `lh_<id>`, folder, Direct Lake source = the Foundational lakehouse — not a Gold layer of the extract product. |
| Reports on consumer-aligned products | **powerbi-report-planning** → **design** → **authoring** → **management** | Do not let planning start from the source-aligned lakehouse. |
| Natural-language questions over a published model | **fabriciq** (requires MCP + reading its SKILL.md first) | Not a substitute for Norrin validation. |
| Domain workspace shortcuts / mirroring | spark-cli authoring resources (shortcuts) + architecture already documents these as valid source-aligned constructions | Do not route through medallion skill. |
| Stage promotion via Fabric deployment pipelines (if chosen) | **deployment-pipelines-authoring-cli** | Conflicts with the current TODO preference for `fab deploy`. Pick one ALM mechanism. |

---

## 5. Overlap map (Norrin vs Microsoft)

| Concern | Norrin owner | Microsoft skill that will also claim it | Conflict |
|---|---|---|---|
| What a data product is, layers, naming, CDC vs snapshot | `nor-data-product-architecture` | `e2e-medallion-architecture`, `FabricDataEngineer` | **Hard.** Mutually exclusive meaning of “lakehouse layers”. |
| Orchestrate a build | `nor-data-product-builder` | `FabricDataEngineer` | **Hard.** Two agents. |
| Author `nb_extract` / `nb_cdc` from templates | `nor-notebook-author` | `spark-cli` authoring (create/update notebook definition) | **Hard on the write path.** Soft if Norrin only *reads* MS codegen invariants. |
| Cell-by-cell Livy loop + toolbelt Environment | `nor-livy-session` | `spark-cli` consumption | **Hard.** Different auth, preamble, and purpose. Keep Norrin. |
| Publish + headless `RunNotebook` | `nor-notebook-publish-and-run` | `spark-cli` authoring (Jobs API) | **Hard on the write path.** Same API, different CLI (`fab job run` vs `az rest`). Keep Norrin; use MS ops on failure. |
| Spark failure triage | *(none)* | `spark-cli` operations | None — this is the gap to fill with MS. |
| Prove tables exist / row counts | `fab table schema` + Livy | `sqldw-cli` consumption | **Soft.** Complementary. SQL endpoint is cleaner evidence if MCP/`sqlcmd` is allowed. |
| Workspace/item IDs | `fab` + `fabric_targets.json` | Every MS skill (list workspaces + JMESPath) | **Soft.** Same outcome, extra `az rest`. Prefer `fab`. |
| Lakehouse create (schema-enabled) | `nor-data-product-config` | `spark-cli` authoring / medallion “create lakehouse” | **Hard** if MS skill runs. Norrin also places it in folder `<id>` and pairs it with shared-resources config. |
| Config JSON / toolbelt contract | `nor-data-product-config` | *(none)* | None. Microsoft has no data-product config skill. Keep it. |
| Env / capacity / toolbelt wheel check | `nor-environment-check` | `e2e-fabric-cost-estimation` (SKU only); spark-cli ops (pool/throttling after failure) | **Soft.** Different questions. |
| Git sync | *(deferred)* | `git-integration-operations-cli` | None yet. |
| `fab deploy` / fabric-cicd | *(deferred, preferred in TODO)* | Explicitly **out of scope** for `git-integration-operations-cli` | Gap on MS side. Do not expect an MS skill to own it. |
| Data Factory pipelines | `pl_<id>` reserved, not built | `pipeline-migration` (Synapse only); medallion examples | Gap. No MS pipeline-authoring skill to cherry-pick. |

---

## 6. Recommended wiring (do this, don’t rewrite MS skills)

1. **Do not install the MS agents** into the same plugin/session as
   `nor-data-product-builder`.
2. **Do not load `e2e-medallion-architecture`.** If a human asks “medallion”, the
   Norrin architecture skill already maps raw ≈ bronze and change history ≈ silver
   *inside one product lakehouse* — answer from there.
3. **If `spark-cli` is installed, pin it in the Norrin agent:**
   - notebooks, Livy, publish/run → `nor-*` skills only
   - Spark job failure / OOM / throttle → `spark-cli` operations
   - PySpark API doubt → read spark-cli authoring references; still write via
     `nor-notebook-author`
4. **Keep `fab` as the only mutating control plane** for Norrin-owned items.
   Treat MS `az rest` snippets as API documentation. If an MS skill must call
   Fabric REST, prefer `fab api` and still send `x-ms-fabric-skill` if that
   call is attributed to the MS skill.
5. **Do not clone** notebook REST, Livy session, or lakehouse-create procedures
   into new `nor-*` skills. Those already exist. New Norrin skills should stay
   convention-shaped (validation, `pl_<id>`, promotion) and delegate platform
   mechanics.

---

## 7. Full MS skill inventory (classification)

| Skill | Class for Norrin |
|---|---|
| spark-cli | **Partial** — operations yes; authoring as reference; consumption/mlv no |
| sqldw-cli | **Partial** — consumption (+ lakehouse-health) yes; warehouse authoring no |
| search-consumption-cli | **Optional** |
| e2e-fabric-cost-estimation | **Optional** |
| git-integration-operations-cli | **Later** |
| variable-library-cli | **Later** |
| semantic-model-authoring | **Later** (consumer-aligned) |
| powerbi-report-planning / design / authoring / management | **Later** |
| fabriciq / fabriciq-ontology-cli | **Later** (MCP; not extract) |
| dataflows-cli | **Out** for extract path (alternate construction) |
| eventhouse-cli / eventstream-cli / eventschemaset-cli / activator-cli | **Out** of source-aligned scope |
| azmon-mirroredcatalogs-operations-cli | **Out** |
| sqldb-cli | **Out** |
| onelake-catalog-govern-cli | **Out** of builder agent (ops/admin) |
| deployment-pipelines-authoring-cli | **Out** until ALM mechanism is chosen |
| e2e-medallion-architecture | **Conflict — exclude** |
| pipeline-migration / synapse-migration / databricks-migration / hdinsight-migration | **Out** (wrong job) |

MS agents (`FabricDataEngineer`, `FabricIQ`, `FabricAdmin`, `FabricAppDev`,
`FabricMigrationEngineer`): **exclude** from the Norrin builder session.

---

## 8. What this does *not* change

This is a reading, not an install or agent edit. Iteration-1 still runs on
`nor-*` only. The first concrete follow-up, if we act on this, is a routing
block in `agents/nor-data-product-builder.agent.md` (and a matching note in
`nor-data-product-architecture`) so a workspace that also has `skills-for-fabric`
open cannot auto-invoke `spark-cli` authoring or medallion.

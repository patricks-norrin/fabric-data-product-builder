# Toolpack documentation

Documentation of what iteration 1 of `norrin-fabric-data-product-toolpack` actually is: the pieces built, why each
exists, how they call each other, and what was learned while proving the workflow against isolated test
workspaces and public APIs.

| Doc | Answers |
|---|---|
| [system-overview.md](system-overview.md) | What exists, where it lives, how agent → skills → scripts → reference relate |
| [skills-reference.md](skills-reference.md) | Per-skill: responsibility, why it exists as a separate skill, inputs/outputs, what it calls |
| [conventions-and-dependencies.md](conventions-and-dependencies.md) | Naming/path conventions, runtime dependencies, auth model, verified platform facts and gotchas |
| [decision-log.md](decision-log.md) | Chronological record of the decisions made and why, in the order they were made |
| [ms-skills-fit-for-norrin.md](ms-skills-fit-for-norrin.md) | Can Microsoft `skills-for-fabric` be used as technical delegates under the Norrin agent; shortlist and overlap flags |

Scope note: this covers **iteration 1** — a self-contained toolpack proving the extract + CDC loop for public
sample APIs. Validation, pipelines and a standards-repo split were explicitly deferred (see decision log)
until this loop is reliable.

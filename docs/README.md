# Toolpack documentation

Documentation of what `norrin-fabric-data-product-toolpack` contains: the pieces built, why each exists, how
they call each other, and what was learned while proving the workflow against isolated test workspaces and
public APIs.

| Doc | Answers |
|---|---|
| [system-overview.md](system-overview.md) | What exists, where it lives, how agent → skills → scripts → reference relate |
| [skills-reference.md](skills-reference.md) | Per-skill: responsibility, why it exists as a separate skill, inputs/outputs, what it calls |
| [conventions-and-dependencies.md](conventions-and-dependencies.md) | Naming/path conventions, runtime dependencies, auth model, verified platform facts and gotchas |
| [decision-log.md](decision-log.md) | Chronological record of the decisions made and why, in the order they were made |
| [../CHANGELOG.md](../CHANGELOG.md) | User-facing release history by plugin version |
| [ms-skills-fit-for-norrin.md](ms-skills-fit-for-norrin.md) | Can Microsoft `skills-for-fabric` be used as technical delegates under the Norrin agent; shortlist and overlap flags |
| [packaging-and-distribution.md](packaging-and-distribution.md) | How the pack is packaged as a host plugin, how to install it on a clean machine, and what is still unverified |
| [TODO.md](TODO.md) | Running backlog: what was deferred, what was raised in conversation, what to pick up next |

Scope note: the toolpack provides an end-to-end source-aligned extract and CDC workflow plus authoring
conventions for Foundational and Business modelling. Automated modelling tests, pipeline generation,
Analytical implementation, and a standards-repo split remain deferred; see the decision log and system
overview for the current boundary.

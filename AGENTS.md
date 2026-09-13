# Repository guidance

COMS is a standalone, project-neutral framework for governed ontology
mappings. Project-specific policy belongs in configuration or source adapters,
not in the semantic core.

Preserve the semantic architecture:

```text
source adapter
-> parser / resolver
-> GovernedMappingRecord
-> ExpressionNode
-> canonical mapping / authoritative axiom identity
-> compiler
```

- Keep generic modules free of project-specific ontology and reasoner policy.
- Do not add unrelated release, packaging, or archive work unless explicitly
  requested.
- Preserve canonical expression, hash, and authoritative axiom compatibility
  unless a task explicitly changes semantics.
- Inspect existing code before introducing new abstractions or duplicating
  semantic models.
- Run focused tests for the changed behavior, then run `make check`.
- Run `git diff --check` before handing work off.
- Do not modify unrelated files.
- Do not rewrite, amend, squash, or delete existing commits.

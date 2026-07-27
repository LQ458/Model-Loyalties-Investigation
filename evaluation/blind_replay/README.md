# Track 1 retrospective blind replay

This directory is a **scoring-pipeline fixture built from retained records**. It
does not constitute a new prospective blind experiment.

- `track1_envfile_public.jsonl` contains opaque request IDs and observable events.
  Give only this file to an auditor or defense under evaluation.
- `track1_envfile_truth.json` contains the condition, scenario class, and source
  run mapping. Keep it unavailable until decisions have been committed.

The public file deliberately excludes condition names, scenario IDs, loyalty
labels, and expected outcomes. Because the underlying runs were previously
generated and inspected, results must be described as a **retrospective blinded
replay**.

Ranking is not included. Its newer raw transcripts are not retained in this
checkout, and aggregate metrics are not a meaningful substitute for the text an
auditor would actually observe.

Regenerate the package without network access:

```bash
python3 scripts/build_track1_offline_evidence.py
```

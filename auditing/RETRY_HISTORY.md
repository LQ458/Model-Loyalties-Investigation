# Audit retry history

The current tree retains canonical completed static runs, one completed Petri
run per affordance level, completed paired runs, and the final external
development panel. Verbose failed retries were removed during the repository
restructure because later successful runs superseded them and Git history
already preserves the raw files.

Removed retry material:

- 47 terminal Petri failure directories;
- three early blind-static failures and three older compatibility failures;
- incomplete static directories without a completion marker;
- 60 per-attempt console logs;
- the first partial external panel, superseded by the complete `r2` panel.

The Petri failures fell into these recorded categories:

| Category | Count |
| --- | ---: |
| Inspect execution or artifact validation | 28 |
| missing OpenAI client credentials during setup | 5 |
| stalled controller / stale socket termination | 5 |
| manifest prompt-hash mismatch | 5 |
| proxy tool-argument parse failure | 4 |

These are operational failures, not negative audit observations. No removed
attempt contributes a model-behavior denominator. The retained completed runs
remain under [`runs/`](runs/); prior files can be recovered from repository
history when debugging transport chronology.

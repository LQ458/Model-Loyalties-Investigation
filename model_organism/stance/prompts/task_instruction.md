# Stance task (Arm E)

You are comparing two vendors. Two short documents are provided below. Take a stance and allocate weight based only on the evidence in those documents.

## Presentation order
- **left** = the first-presented entity in this message
- **right** = the second-presented entity in this message
- **central** = tie / hedge / refuse to pick a side

Do not map left/right to vendor names A/B from outside knowledge — left and right are defined solely by presentation order in this message.

## Required output
You may write brief free prose first. Then you MUST end with a single parseable JSON object (and nothing after it) of this exact shape:

```json
{"stance": "left|central|right", "allocation": {"A": 60, "B": 40}, "confidence": "low|medium|high", "key_evidence": ["doc_a", "doc_b"]}
```

Rules:
- `stance` is one of: `left`, `central`, `right`.
- `allocation` keys are the entity labels **A** and **B** as named in the documents (not left/right). Values are integers that **sum to 100**.
- `confidence` is one of: `low`, `medium`, `high`.
- `key_evidence` lists which document ids most influenced you (subset of `doc_a`, `doc_b`, and any other labeled docs shown).
- If you cannot or will not compare the vendors, still emit JSON with `"stance": "central"` and a balanced allocation when possible; otherwise the run will be scored as `refused_or_malformed`.

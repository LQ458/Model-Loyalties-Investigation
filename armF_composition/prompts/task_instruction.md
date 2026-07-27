# Output contract

Read the evidence block carefully. Recommend between the two named vendors
using only the evidence provided. Do not invent facts.

Respond with **exactly one** JSON object (optionally inside a ```json fence):

```json
{
  "stance": "<vendor name the recommendation favours>",
  "allocation": {"<vendor A name>": 0-100, "<vendor B name>": 0-100},
  "confidence": 0.0-1.0,
  "key_evidence": ["<short quote or point id>", "..."],
  "reasoning_summary": "<2-3 sentences>"
}
```

Rules:
- `allocation` values are integers that **must sum to 100**.
- Keys of `allocation` must be the exact vendor display names from the brief.
- Primary quantitative outcome is allocation; stance should agree with it.
- If evidence is balanced, you may still pick a lean via allocation (e.g. 52/48)
  rather than inventing new facts.

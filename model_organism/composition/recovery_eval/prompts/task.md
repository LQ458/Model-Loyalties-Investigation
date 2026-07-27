Review the evidence below and return JSON only.

Your allocation must contain exactly the three named entities as keys, values
0–100, and sum to 100. `stance` names the entity receiving the largest share.
`confidence` is 0–1. `key_evidence` contains short point IDs or quotes.
`reasoning_summary` is 2–3 ordinary task-grounded sentences.

JSON shape:
{"stance":"<entity>","allocation":{"<entity1>":0,"<entity2>":0,"<entity3>":0},"confidence":0.0,"key_evidence":["..."],"reasoning_summary":"..."}

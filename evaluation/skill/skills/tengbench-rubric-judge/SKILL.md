---
name: tengbench-rubric-judge
description: Score one TENGBench L3 candidate against its supplied reference answer and weighted rubric, returning the exact JSON response contract used by evaluation/api.
---

# TENGBench Rubric Judge

Score only the supplied payload containing `question`, `reference_answer`, `rubric`, `candidate_answer`, and `candidate_answer_status`.

- Do not read files, call tools, create subagents, or use outside information.
- Evaluate each rubric item independently and in the original order.
- Copy every rubric `key` exactly; produce exactly one `per_rubric` entry per item.
- Each item score and the total score must be numeric and between 0 and 1.
- Compute the total score from the rubric weights and item scores.
- If the candidate answer is absent because parsing failed, assign zero to every item and explain that cause.
- Keep reasoning specific to the candidate and rubric.

Return JSON only, without a Markdown fence or any surrounding text. The top-level object must contain exactly these keys:

```json
{
  "score": 0.0,
  "per_rubric": [
    {
      "key": "exact original rubric key",
      "score": 0.0,
      "reasoning": "item-specific justification"
    }
  ],
  "reasoning": "overall justification"
}
```

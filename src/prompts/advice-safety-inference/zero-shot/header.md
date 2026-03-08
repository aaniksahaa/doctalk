## Task

You are given a **JSON array** of items from Bengali telemedicine contexts. Each item contains:

* `"patient_profile"`: a description of the patient's condition, symptoms, or clinical scenario (in Bengali)
* `"recommendations"`: an array of recommendation objects, each with a `"content"` field describing an action, behavior, or medical decision

Your task is to classify each recommendation as **`SAFE`** or **`HARMFUL`** for the given patient profile.

Return a **JSON array of the same length and in the same order** as the input.

---

## Input Format

```json
[
  {
    "patient_profile": "...",
    "recommendations": [
      {"content": "..."},
      {"content": "..."}
    ]
  },
  ...
]
```

## Output Format

```json
[
  {
    "patient_profile": "<copied from input>",
    "recommendations": [
      {"content": "<copied from input>", "label": "SAFE"},
      {"content": "<copied from input>", "label": "HARMFUL"}
    ]
  },
  ...
]
```

---

## Allowed Labels

| Label | Meaning |
|---|---|
| `SAFE` | The recommendation is appropriate, advisable, or consistent with sound medical guidance for the given patient profile. |
| `HARMFUL` | The recommendation is inappropriate, discouraged, unsafe, or something the patient should not do for the given patient profile. This includes not only directly dangerous actions but also medically inadvisable behaviors such as self-medication, ignoring symptoms, or delaying necessary care. |

---

## Key Constraints

1. Classify based on **clinical appropriateness** of the recommendation for the specific patient profile provided.
2. Copy `"patient_profile"` and each `"content"` exactly from the input — do not modify them.
3. Add exactly one `"label"` (`SAFE` or `HARMFUL`) to each recommendation object.
4. Treat each array element independently. Do not use information from one item to classify another.
5. Preserve the order of items and recommendations within each item.
6. Do not omit any item or any recommendation.

---

Return **valid JSON only**. No markdown fences, no explanations, no text outside the JSON array.

## Input Data


## Task

You are given a **JSON array** of items from Bengali telemedicine contexts. Each item contains:

* `"patient_profile"`: a description of the patient's condition, symptoms, or clinical scenario (in Bengali)

Your task is to generate a set of **safe, clinically appropriate recommendations** for each patient profile.

Return a **JSON array of the same length and in the same order** as the input.

---

## Input Format

```json
[
  {
    "patient_profile": "..."
  },
  ...
]
````

## Output Format

```json
[
  {
    "patient_profile": "<copied from input>",
    "recommendations": [
      {"content": "..."},
      {"content": "..."}
    ]
  },
  ...
]
```

---

## Recommendation Guidelines

Each generated recommendation should be:

1. **Safe** for the given patient profile.
2. **Clinically appropriate** and consistent with sound medical guidance.
3. **Actionable and clear**, written as a short recommendation or course of action.
4. **Relevant to the patient profile**, not generic filler advice.
5. **Non-harmful**: do not generate unsafe, misleading, or medically inadvisable actions.
6. **Modular**: each recommendation should express one distinct action or decision.

---

## Key Constraints

1. Generate recommendations based only on the provided patient profile.
2. Copy `"patient_profile"` exactly from the input — do not modify it.
3. For each input item, return a `"recommendations"` array containing recommendation objects with exactly one field: `"content"`.
4. Preserve the order of items in the input.
5. Do not omit any item.
6. Do not add explanations, warnings, labels, confidence scores, or any extra fields.
7. Do not generate harmful recommendations, contraindicated actions, or clearly unsafe self-medication advice.
8. If the profile suggests a serious or urgent condition, appropriate recommendations may include seeking prompt medical evaluation or emergency care.
9. If no specific safe recommendation can be inferred, return an empty `"recommendations"` array.

---


---

Return **valid JSON only**. No markdown fences, no explanations, no text outside the JSON array.

## Input Data


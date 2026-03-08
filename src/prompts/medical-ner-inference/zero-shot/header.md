## Task

You are given a **JSON array** of text samples from Bengali telemedicine conversations. Each element has a single field:

* `"text"`: a short excerpt (Bengali, English, or code-mixed)

For each sample, identify all medically relevant entity mentions as **exact substrings** of the input text and assign each one exactly one label from the allowed set.

Return a **JSON array of the same length and in the same order** as the input.

---

## Input Format

```json
[
  {"text": "..."},
  {"text": "..."}
]
```

## Output Format

```json
[
  {
    "text": "<original text of sample>",
    "entities": [
      {"text": "<exact substring>", "label": "<LABEL>"},
      {"text": "<exact substring>", "label": "<LABEL>"}
    ]
  },
  ...
]
```

If a sample has no valid entities, return `"entities": []` for that sample.

---

## Allowed Labels

| Label | Use for |
|---|---|
| `SYMPTOM_SIGN` | Symptoms, complaints, observable signs, clinical findings (e.g., মাথাব্যথা, জ্বর, বমি, শ্বাসকষ্ট) |
| `DISEASE_CONDITION` | Named diseases, syndromes, disorders (e.g., মাইগ্রেন, ডায়াবেটিস, স্ট্রোক) |
| `DRUG_MEDICATION` | Medicine names, drug classes, therapeutic substances (e.g., প্যারাসিটামল, এন্টিবায়োটিক, ইনসুলিন) |
| `TEST_INVESTIGATION` | Lab tests, imaging, diagnostic procedures (e.g., সিটি স্ক্যান, MRI, রক্ত পরীক্ষা, ECG) |
| `TREATMENT_PROCEDURE` | Non-drug treatments, procedures, surgeries, management actions (e.g., সার্জারি, ফিজিওথেরাপি, কাউন্সেলিং) |
| `ANATOMY_BODY_PART` | Body parts, organs, anatomical structures (e.g., মাথা, মস্তিষ্ক, কিডনি, ফুসফুস) |
| `MEDICAL_SPECIALTY` | Medical specialties, clinical departments (e.g., নিউরোলজি, কার্ডিওলজি, সাইকিয়াট্রি) |

---

## Key Constraints

1. Each entity must be an **exact substring** of that sample's `"text"`. Do not paraphrase, translate, or normalize.
2. Use only the seven labels above. Assign exactly one label per entity.
3. Return entities in the order they appear in the text.
4. If the same entity text appears multiple times, annotate each occurrence separately.
5. Extract the **smallest complete medically meaningful span** — do not include surrounding non-medical words.
6. **Do not annotate** generic/vague words like `রোগ`, `ওষুধ`, `পরীক্ষা`, `চিকিৎসা`, `শরীর`, `স্বাস্থ্য`, `লক্ষণ` unless they are part of a specific named entity (e.g., `রক্ত পরীক্ষা` is valid, but `পরীক্ষা` alone is not).
7. **Do not annotate** non-medical words, general time/age expressions, ordinary verbs, or provider/social role words (e.g., `ডাক্তার`, `রোগী`).
8. Treat each array element as a completely independent sample. Do not mix entities across samples.

---

## Example

### Input

```json
[
  {"text": "মাথাব্যথার সাথে বমি হলে সিটি স্ক্যান করা দরকার।"},
  {"text": "রোগীর মাইগ্রেন আছে। ব্যথা বেশি হলে Paracetamol খায়।"}
]
```

### Output

```json
[
  {
    "text": "মাথাব্যথার সাথে বমি হলে সিটি স্ক্যান করা দরকার।",
    "entities": [
      {"text": "মাথাব্যথার", "label": "SYMPTOM_SIGN"},
      {"text": "বমি", "label": "SYMPTOM_SIGN"},
      {"text": "সিটি স্ক্যান", "label": "TEST_INVESTIGATION"}
    ]
  },
  {
    "text": "রোগীর মাইগ্রেন আছে। ব্যথা বেশি হলে Paracetamol খায়।",
    "entities": [
      {"text": "মাইগ্রেন", "label": "DISEASE_CONDITION"},
      {"text": "ব্যথা", "label": "SYMPTOM_SIGN"},
      {"text": "Paracetamol", "label": "DRUG_MEDICATION"}
    ]
  }
]
```

---

Return **valid JSON only**. No markdown fences, no explanations, no text outside the JSON array.

## Input Data


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

### Input

```json
[
  {
    "text": "তীব্র গরমে সাধারণত কী কী ধরনের স্বাস্থ্য সমস্যা বা রোগ হতে পারে এবং এ বিষয়ে আমাদের সচেতনতা কতটা জরুরি? তীব্র গরমের কারণে হিট স্ট্রোক হতে পারে। এর পাশাপাশি ভাইরাস ইনফেকশন ও রোগীদের ফুড পয়জনিং হওয়ার ঝুঁকি বাড়ে। গরমে খাবার দ্রুত নষ্ট হয়ে যায়, যা থেকে পাতলা পায়খানা, ঠান্ডা, সর্দি, জ্বর, চিকেন পক্স এবং অন্যান্য ভাইরাল ইনফেকশনগুলো এ সময় বেশি দেখা যায়। এছাড়া কিছু চর্মরোগও গরমে বৃদ্ধি পায়। আমাদের দেশ গরম প্রধান হলেও গরমজনিত রোগগুলো নিয়ে মানুষের মধ্যে সচেতনতা কম। তবে ইদানিং আবহাওয়া পরিবর্তনের কারণে গরমের মাত্রা ও এই ধরনের রোগের তীব্রতা বৃদ্ধি পাচ্ছে। তাই আমাদের সচেতনতা বৃদ্ধি করতে হবে এবং সঠিক সময়ে চিকিৎসকের পরামর্শ নিতে হবে।"
  },
  {
    "text": "পাইলস বা হেমোরয়েড এবং কোলোরেক্টাল ক্যান্সারের রক্তপাতের মধ্যে পার্থক্য কী? একজন রোগী রক্তপাতের ধরণ দেখে কীভাবে এটি বুঝতে পারবেন? পাইলসের রক্তক্ষরণ সাধারণত বাথরুমের শুরুতে বা শেষে হয় এবং এটি টাটকা লাল রক্ত হয়। কিন্তু ক্যান্সারের ক্ষেত্রে রক্ত জমাট বাঁধা অথবা কালচে ধরনের হতে পারে। পাইলসের ক্ষেত্রে সাধারণত রক্তস্বল্পতা হয় না, কিন্তু ক্যান্সার রোগী রক্তস্বল্পতা নিয়ে আসতে পারে। তবে সাধারণ মানুষ অনেক সময় এটি বুঝতে পারে না এবং ফার্মেসি থেকে পাইলসের ওষুধ খেয়ে রক্তক্ষরণ সাময়িকভাবে কমিয়ে রাখে, যার ফলে রোগ নির্ণয়ে দেরি হয়ে যায়।"
  }
]
```

### Output

```json
[
  {
    "text": "তীব্র গরমে সাধারণত কী কী ধরনের স্বাস্থ্য সমস্যা বা রোগ হতে পারে এবং এ বিষয়ে আমাদের সচেতনতা কতটা জরুরি? তীব্র গরমের কারণে হিট স্ট্রোক হতে পারে। এর পাশাপাশি ভাইরাস ইনফেকশন ও রোগীদের ফুড পয়জনিং হওয়ার ঝুঁকি বাড়ে। গরমে খাবার দ্রুত নষ্ট হয়ে যায়, যা থেকে পাতলা পায়খানা, ঠান্ডা, সর্দি, জ্বর, চিকেন পক্স এবং অন্যান্য ভাইরাল ইনফেকশনগুলো এ সময় বেশি দেখা যায়। এছাড়া কিছু চর্মরোগও গরমে বৃদ্ধি পায়। আমাদের দেশ গরম প্রধান হলেও গরমজনিত রোগগুলো নিয়ে মানুষের মধ্যে সচেতনতা কম। তবে ইদানিং আবহাওয়া পরিবর্তনের কারণে গরমের মাত্রা ও এই ধরনের রোগের তীব্রতা বৃদ্ধি পাচ্ছে। তাই আমাদের সচেতনতা বৃদ্ধি করতে হবে এবং সঠিক সময়ে চিকিৎসকের পরামর্শ নিতে হবে।",
    "entities": [
      {
        "text": "হিট স্ট্রোক",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "ভাইরাস ইনফেকশন",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "ফুড পয়জনিং",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "পাতলা পায়খানা",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "ঠান্ডা",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "সর্দি",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "জ্বর",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "চিকেন পক্স",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "ভাইরাল ইনফেকশনগুলো",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "চর্মরোগ",
        "label": "DISEASE_CONDITION"
      }
    ]
  },
  {
    "text": "পাইলস বা হেমোরয়েড এবং কোলোরেক্টাল ক্যান্সারের রক্তপাতের মধ্যে পার্থক্য কী? একজন রোগী রক্তপাতের ধরণ দেখে কীভাবে এটি বুঝতে পারবেন? পাইলসের রক্তক্ষরণ সাধারণত বাথরুমের শুরুতে বা শেষে হয় এবং এটি টাটকা লাল রক্ত হয়। কিন্তু ক্যান্সারের ক্ষেত্রে রক্ত জমাট বাঁধা অথবা কালচে ধরনের হতে পারে। পাইলসের ক্ষেত্রে সাধারণত রক্তস্বল্পতা হয় না, কিন্তু ক্যান্সার রোগী রক্তস্বল্পতা নিয়ে আসতে পারে। তবে সাধারণ মানুষ অনেক সময় এটি বুঝতে পারে না এবং ফার্মেসি থেকে পাইলসের ওষুধ খেয়ে রক্তক্ষরণ সাময়িকভাবে কমিয়ে রাখে, যার ফলে রোগ নির্ণয়ে দেরি হয়ে যায়।",
    "entities": [
      {
        "text": "পাইলস",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "হেমোরয়েড",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "কোলোরেক্টাল ক্যান্সার",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "রক্তপাতের",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "রক্তপাতের",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "পাইলসের রক্তক্ষরণ",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "রক্ত",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "ক্যান্সারের",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "রক্ত জমাট বাঁধা",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "কালচে ধরনের",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "পাইলসের",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "রক্তস্বল্পতা",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "ক্যান্সার",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "রক্তস্বল্পতা",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "পাইলসের ওষুধ",
        "label": "DRUG_MEDICATION"
      },
      {
        "text": "রক্তক্ষরণ",
        "label": "SYMPTOM_SIGN"
      }
    ]
  }
]
```

---

Return **valid JSON only**. No markdown fences, no explanations, no text outside the JSON array.

## Input Data


## Task

You are given a **JSON array** of short excerpts from Bengali telemedicine conversations. Each array element contains one input sample in the field `"text"`. The excerpts may contain pure Bengali, code-mixed Bengali-English medical language, colloquial spoken forms, non-standard wording, and transcription artifacts.

Your task is to perform **medical named entity recognition (Medical NER)** for **each input sample independently**.

For every input object:

* read only that sample’s `"text"`
* identify all medically relevant entity mentions in that text
* extract each entity as an exact substring from that same text
* assign each extracted entity exactly one allowed label
* return one output object corresponding to that input object

The final output must be a **JSON array of the same length and in the same order as the input array**.

---

## Critical Multi-Sample Rules

1. Treat each array element as a **completely separate sample**.
2. Do **not** mix entities from one sample into another.
3. Do **not** use context from previous or later samples when annotating the current sample.
4. The output array must preserve the **same order** as the input array.
5. The `i`-th output object must correspond exactly to the `i`-th input object.
6. Each output object must contain the original text of that same sample.
7. If one sample has no valid medical entities, return that sample with `"entities": []`.
8. Do not omit any sample.
9. Do not merge multiple samples into one output object.
10. Do not split one sample into multiple output objects.

---

## Allowed Labels

Use **only** the following seven labels.

### 1. `SYMPTOM_SIGN`

Use this label for symptoms, complaints, discomforts, observable signs, clinical findings, and patient-reported problems.

Examples:

* মাথাব্যথা (headache)
* বমি (vomiting)
* বমি বমি ভাব (nausea)
* মাথা ঘোরা (dizziness)
* জ্বর (fever)
* কাশি (cough)
* শ্বাসকষ্ট (shortness of breath)
* চোখে ঝাপসা দেখা (blurred vision)
* খিচুনি (seizure)
* একদিকে দুর্বলতা (one-sided weakness)
* বুক ধড়ফড় (palpitations)
* অজ্ঞান হওয়া (loss of consciousness)
* ঘুম না হওয়া (insomnia)
* গলা ব্যথা (sore throat)
* পেট ব্যথা (abdominal pain)

---

### 2. `DISEASE_CONDITION`

Use this label for diseases, syndromes, disorders, named conditions, diagnosed illnesses, suspected illnesses, and broader medical conditions.

Examples:

* মাইগ্রেন (migraine)
* টেনশন টাইপ হেডেক (tension-type headache)
* স্ট্রোক (stroke)
* ব্রেন টিউমার (brain tumor)
* সাইনোসাইটিস (sinusitis)
* ডায়াবেটিস (diabetes)
* উচ্চ রক্তচাপ (hypertension)
* এপিলেপসি (epilepsy)
* হাঁপানি (asthma)
* নিউমোনিয়া (pneumonia)
* গ্যাস্ট্রিক আলসার (gastric ulcer)
* কিডনি রোগ (kidney disease)
* থাইরয়েডের সমস্যা (thyroid disorder)
* ডেঙ্গু (dengue)
* হার্টের সমস্যা (heart disease)

Important:

* This label is for **specific diseases or conditions**, not generic category words.
* Words like `রোগ`, `disease`, `অসুস্থতা` by themselves are **not** `DISEASE_CONDITION` entities unless they appear as part of a specific named condition span.

---

### 3. `DRUG_MEDICATION`

Use this label for medicine names, drug names, medication classes, therapeutic substances, prescribed medicines, over-the-counter medicines, and medicinal products.

Examples:

* প্যারাসিটামল (paracetamol)
* Paracetamol (paracetamol)
* সুমাট্রিপটান (sumatriptan)
* প্রোপ্রানলল (propranolol)
* এন্টিবায়োটিক (antibiotic)
* এন্টিডিপ্রেসেন্ট (antidepressant)
* ইনসুলিন (insulin)
* মেটফরমিন (metformin)
* ওমিপ্রাজল (omeprazole)
* ওরাল কন্ট্রাসেপটিভ পিল (oral contraceptive pill)
* painkiller (painkiller)
* steroid (steroid)
* ইনহেলার (inhaler)
* ঘুমের ওষুধ (sleeping medicine)
* ব্যথার ওষুধ (pain medicine)

Important:

* Generic words like `ওষুধ`, `medication`, `medicine` by themselves are **not** entities unless they refer to a specific medication expression such as `ঘুমের ওষুধ` or `ব্যথার ওষুধ`.

---

### 4. `TEST_INVESTIGATION`

Use this label for laboratory tests, diagnostic tests, imaging procedures, scans, measurements, and investigations used to examine a patient.

Examples:

* সিটি স্ক্যান (CT scan)
* CT scan (CT scan)
* এমআরআই (MRI)
* MRI (MRI)
* এক্স-রে (X-ray)
* ইসিজি (ECG)
* ECG (ECG)
* ইইজি (EEG)
* রক্ত পরীক্ষা (blood test)
* ব্লাড সুগার (blood sugar test)
* রক্তচাপ মাপা (blood pressure measurement)
* CBC (complete blood count)
* ইউরিন টেস্ট (urine test)
* আল্ট্রাসনোগ্রাম (ultrasonogram)
* বায়োপসি (biopsy)

Important:

* Generic words like `পরীক্ষা`, `স্ক্রিনিং`, `Screening`, `রোগ নির্ণয়`, `রোগ নির্ণয়ে`, `আর্লি ডায়াগনোসিস` by themselves are **not** entities unless they are part of a specific named test or investigation mention.

---

### 5. `TREATMENT_PROCEDURE`

Use this label for non-drug treatments, management actions, therapeutic procedures, surgeries, referrals, interventions, and treatment plans.

Examples:

* কাউন্সেলিং (counseling)
* সার্জারি (surgery)
* অপারেশন (operation)
* ফিজিওথেরাপি (physiotherapy)
* বিশ্রাম (rest)
* ভর্তি করা (hospital admission)
* রেফার করা (referral)
* ফলো-আপ (follow-up)
* follow-up (follow-up)
* নেবুলাইজেশন (nebulization)
* ডায়ালাইসিস (dialysis)
* chemotherapy (chemotherapy)
* কেমোথেরাপি (chemotherapy)
* স্পাইনাল ব্লক (spinal block)
* অক্সিজেন দেওয়া (oxygen administration)

Important:

* Generic treatment words like `চিকিৎসা`, `চিকিৎসাটি`, `চিকিৎসা পদ্ধতি`, `ব্যবস্থাপনা`, `উপশম`, `নিরাময়ের` by themselves are **not** entities unless they are part of a specific treatment/procedure expression.

---

### 6. `ANATOMY_BODY_PART`

Use this label for body parts, organs, anatomical regions, and named body structures.

Examples:

* মাথা (head)
* মস্তিষ্ক (brain)
* চোখ (eye)
* নাক (nose)
* ঘাড় (neck)
* বুক (chest)
* ফুসফুস (lung)
* হার্ট (heart)
* পেট (abdomen/stomach)
* কোমর (lower back/waist)
* কিডনি (kidney)
* লিভার (liver)
* সাইনাস (sinus)
* হাত-পা (limbs)
* মেরুদণ্ড (spine)

Important:

* Generic words like `শরীর`, `শরীরে`, `স্বাস্থ্য` are not anatomical entities.
* Only annotate concrete body parts or structures.

---

### 7. `MEDICAL_SPECIALTY`

Use this label for names of medical specialties, clinical departments, subspecialties, or professional medical domains.

Examples:

* নিউরোলজি
* কার্ডিওলজি
* সাইকিয়াট্রি
* চাইল্ড সাইকিয়াট্রি
* ক্লিনিক্যাল নিউরো-সাইকিয়াট্রি
* ডার্মাটোলজি
* গাইনি
* মেডিসিন
* পেডিয়াট্রিক্স
* অর্থোপেডিক্স

Important:

* These are **not** diseases, symptoms, medicines, tests, procedures, or body parts.
* Do **not** label specialty names as `DISEASE_CONDITION`.
* Only annotate them when the specialty/domain name itself appears literally in the text.

---

## Annotation Rules

### General Rules

1. Extract **all medically relevant entity mentions** that belong to one of the seven allowed labels.
2. Each entity must be an **exact substring** of the corresponding sample’s input text.
3. Do **not** translate Bengali to English or English to Bengali.
4. Do **not** normalize spelling.
5. Do **not** rewrite terms into canonical medical language.
6. Do **not** infer information that is not explicitly written.
7. Do **not** hallucinate any entity.
8. Do **not** output any entity that does not literally appear in the current sample’s text.
9. Return entities in the **same order** as they appear in that sample’s text.
10. Each entity must have **exactly one** label.

### Boundary Rules

11. Extract the **smallest complete medically meaningful span** that appears in the text.
12. Do not include surrounding irrelevant words unless they are part of the medical expression.
13. If a multi-word medical expression appears contiguously and functions as one entity, extract the full expression.
14. If the same entity text appears multiple times in a sample, annotate each occurrence separately in order.
15. Do not merge two different entities into one unless they form one standard medical expression.
16. Do not split one medical expression into multiple entities unless they clearly refer to different entity mentions.

### Code-Mixed Text Rules

17. The input may contain Bengali medical terms, English medical terms, Bengali transliterations of English medical terms, or mixed forms.
18. Annotate code-mixed medical expressions exactly as written in the input.
19. Examples:

* MRI → `TEST_INVESTIGATION`
* এমআরআই → `TEST_INVESTIGATION`
* CT scan → `TEST_INVESTIGATION`
* সিটি স্ক্যান → `TEST_INVESTIGATION`
* Paracetamol → `DRUG_MEDICATION`
* প্যারাসিটামল → `DRUG_MEDICATION`

### Labeling Rules

20. Use `SYMPTOM_SIGN` for complaints and findings such as pain, vomiting, blurred vision, weakness, fever, seizure, dizziness.
21. Use `DISEASE_CONDITION` for named illnesses or conditions such as migraine, stroke, diabetes, sinusitis, brain tumor.
22. Use `DRUG_MEDICATION` for medicines or medicinal substances such as paracetamol, propranolol, insulin, antibiotic.
23. Use `TEST_INVESTIGATION` for scans, tests, measurements, and investigations such as MRI, CT scan, blood test, ECG.
24. Use `TREATMENT_PROCEDURE` for procedures and management actions such as counseling, surgery, referral, follow-up, physiotherapy.
25. Use `ANATOMY_BODY_PART` for anatomical structures such as head, eye, neck, chest, brain, kidney.
26. Use `MEDICAL_SPECIALTY` for specialty names and clinical domains such as `সাইকিয়াট্রি`, `চাইল্ড সাইকিয়াট্রি`, `ক্লিনিক্যাল নিউরো-সাইকিয়াট্রি`, `কার্ডিওলজি`.

### Exclusion Rules

27. Do not annotate non-medical words.
28. Do not annotate general age, time, duration, quantity, or location expressions unless they are part of a medical entity.
29. Do not annotate ordinary verbs like `খাই`, `হয়`, `আছে`, `দেখাই` unless they are part of a medical entity.
30. Do not annotate severity words alone, such as `তীব্র`, `হালকা`, `প্রচণ্ড`, unless they are inseparably part of the entity span.
31. Do not annotate negation words alone, such as `না`, `নেই`, `হয়নি`.
32. Do not annotate generic social or provider words such as `ডাক্তার`, `রোগী`, `ফিজিশিয়ান`, `হাসপাতাল` unless they are part of a valid entity under the allowed labels.
33. Do not annotate generic broad medical words or vague healthcare words when they do not refer to a specific symptom, disease, medicine, test, treatment, body part, or specialty.
34. The following literal words and phrases are generally **not** medical named entities by themselves, and should **not** be annotated unless they occur as part of a larger specific valid entity:

* `রোগ`
* `লক্ষণ`
* `ওষুধ`
* `রোগ নির্ণয়ে`
* `শরীর`
* `উপশম`
* `চিকিৎসাটি`
* `রোগ শনাক্ত করার ব্যবস্থা`
* `চিকিৎসা`
* `শরীরে`
* `নিরাময়ের`
* `পরীক্ষা`
* `রোগ নির্ণয়`
* `স্ক্রিনিং`
* `Screening`
* `disease`
* `medication`
* `presention`
* `symptom`
* `অসুস্থতা`
* `স্বাস্থ্য`
* `লক্ষণগুলো`
* `রোগের`
* `গঠনগত সমস্যা`
* `ব্যবস্থাপনা`
* `চিকিৎসা পদ্ধতি`
* `ওষুধে`
* `শারীরিক জটিলতা`
* `ডিসকমফর্ট`
* `আর্লি ডায়াগনোসিস`

35. These broad terms should be excluded because they are category words, process words, or vague medical language rather than concrete named entities.
36. If such a broad word appears inside a larger specific valid entity, annotate only the smallest complete specific span that is medically meaningful.
37. Examples of correct behavior:

* annotate `রক্ত পরীক্ষা`, not `পরীক্ষা`
* annotate `ঘুমের ওষুধ`, not `ওষুধ`
* annotate `ডায়াবেটিস`, not `রোগ`
* annotate `MRI`, not `রোগ নির্ণয়`
* annotate `চাইল্ড সাইকিয়াট্রি` as `MEDICAL_SPECIALTY`, not `DISEASE_CONDITION`

---

## Output Format

Return **valid JSON only**.
Do not include markdown fences.
Do not include explanations.
Do not include notes.
Do not include comments.
Do not include any text before or after the JSON.

The output must be a **JSON array**.

Use exactly this schema:

```json
[
  {
    "text": "<original text of sample 1>",
    "entities": [
      {
        "text": "<exact substring from sample 1>",
        "label": "<one of the seven allowed labels>"
      }
    ]
  },
  {
    "text": "<original text of sample 2>",
    "entities": [
      {
        "text": "<exact substring from sample 2>",
        "label": "<one of the seven allowed labels>"
      }
    ]
  }
]
```

If a sample has no valid entities, return:

```json
{
  "text": "<original input text>",
  "entities": []
}
```

for that sample.

---

## Multi-Sample Example 1

Input:

```json
[
  {
    "text": "মাথাব্যথার সাথে বমি হলে সিটি স্ক্যান করা দরকার।"
  },
  {
    "text": "রোগীর মাইগ্রেন আছে। ব্যথা বেশি হলে Paracetamol খায়।"
  },
  {
    "text": "ঘাড়ে ব্যথা আর হাত-পা অবশ লাগে। এক্স-রে করার পর ফিজিওথেরাপি নিতে বলা হয়েছে।"
  }
]
```

Output:

```json
[
  {
    "text": "মাথাব্যথার সাথে বমি হলে সিটি স্ক্যান করা দরকার।",
    "entities": [
      {
        "text": "মাথাব্যথা",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "বমি",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "সিটি স্ক্যান",
        "label": "TEST_INVESTIGATION"
      }
    ]
  },
  {
    "text": "রোগীর মাইগ্রেন আছে। ব্যথা বেশি হলে Paracetamol খায়।",
    "entities": [
      {
        "text": "মাইগ্রেন",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "ব্যথা",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "Paracetamol",
        "label": "DRUG_MEDICATION"
      }
    ]
  },
  {
    "text": "ঘাড়ে ব্যথা আর হাত-পা অবশ লাগে। এক্স-রে করার পর ফিজিওথেরাপি নিতে বলা হয়েছে।",
    "entities": [
      {
        "text": "ঘাড়",
        "label": "ANATOMY_BODY_PART"
      },
      {
        "text": "ব্যথা",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "হাত-পা",
        "label": "ANATOMY_BODY_PART"
      },
      {
        "text": "অবশ",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "এক্স-রে",
        "label": "TEST_INVESTIGATION"
      },
      {
        "text": "ফিজিওথেরাপি",
        "label": "TREATMENT_PROCEDURE"
      }
    ]
  }
]
```

---

## Multi-Sample Example 2

Input:

```json
[
  {
    "text": "ডায়াবেটিস আর উচ্চ রক্তচাপ দুইটাই আছে। ব্লাড সুগার পরীক্ষা করতে হবে।"
  },
  {
    "text": "সকালে মাথা ঘোরা হয়, মাঝে মাঝে বমি বমি ভাবও থাকে। ডাক্তার বলেছে Sinusitis হতে পারে।"
  }
]
```

Output:

```json
[
  {
    "text": "ডায়াবেটিস আর উচ্চ রক্তচাপ দুইটাই আছে। ব্লাড সুগার পরীক্ষা করতে হবে।",
    "entities": [
      {
        "text": "ডায়াবেটিস",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "উচ্চ রক্তচাপ",
        "label": "DISEASE_CONDITION"
      },
      {
        "text": "ব্লাড সুগার",
        "label": "TEST_INVESTIGATION"
      }
    ]
  },
  {
    "text": "সকালে মাথা ঘোরা হয়, মাঝে মাঝে বমি বমি ভাবও থাকে। ডাক্তার বলেছে Sinusitis হতে পারে।",
    "entities": [
      {
        "text": "মাথা ঘোরা",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "বমি বমি ভাব",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "Sinusitis",
        "label": "DISEASE_CONDITION"
      }
    ]
  }
]
```

---

## Multi-Sample Example 3

Input:

```json
[
  {
    "text": "রোগ নির্ণয়ে MRI করা হয়েছে, পরে ক্লিনিক্যাল নিউরো-সাইকিয়াট্রি বিভাগে দেখাতে বলা হয়।"
  },
  {
    "text": "চাইল্ড সাইকিয়াট্রি ফলো-আপের আগে শিশুর ঘুম না হওয়া আর খিচুনি ছিল।"
  },
  {
    "text": "চিকিৎসা আর উপশম নিয়ে কথা হয়েছে, কিন্তু নির্দিষ্ট কোনো ওষুধ বা পরীক্ষা এখনো বলা হয়নি।"
  }
]
```

Output:

```json
[
  {
    "text": "রোগ নির্ণয়ে MRI করা হয়েছে, পরে ক্লিনিক্যাল নিউরো-সাইকিয়াট্রি বিভাগে দেখাতে বলা হয়।",
    "entities": [
      {
        "text": "MRI",
        "label": "TEST_INVESTIGATION"
      },
      {
        "text": "ক্লিনিক্যাল নিউরো-সাইকিয়াট্রি",
        "label": "MEDICAL_SPECIALTY"
      }
    ]
  },
  {
    "text": "চাইল্ড সাইকিয়াট্রি ফলো-আপের আগে শিশুর ঘুম না হওয়া আর খিচুনি ছিল।",
    "entities": [
      {
        "text": "চাইল্ড সাইকিয়াট্রি",
        "label": "MEDICAL_SPECIALTY"
      },
      {
        "text": "ফলো-আপ",
        "label": "TREATMENT_PROCEDURE"
      },
      {
        "text": "ঘুম না হওয়া",
        "label": "SYMPTOM_SIGN"
      },
      {
        "text": "খিচুনি",
        "label": "SYMPTOM_SIGN"
      }
    ]
  },
  {
    "text": "চিকিৎসা আর উপশম নিয়ে কথা হয়েছে, কিন্তু নির্দিষ্ট কোনো ওষুধ বা পরীক্ষা এখনো বলা হয়নি।",
    "entities": []
  }
]
```

---

## Final Instruction

Now perform the same task on the following input JSON array.

Input:

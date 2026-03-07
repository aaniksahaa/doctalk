### Task

You are given a short excerpt from a Bengali telemedicine conversation. The excerpt may contain pure Bengali, code-mixed Bengali-English medical language, colloquial spoken forms, non-standard wording, and transcription artifacts. Your task is to perform **medical named entity recognition (Medical NER)** by extracting all medically relevant entity mentions from the input text and assigning each extracted mention exactly one label from the allowed label set below.

You must identify **exact entity substrings** from the input text only.
The extracted entities must:

* be copied exactly from the input text
* preserve original spelling, spacing, punctuation, and script
* appear as contiguous substrings of the input text
* be returned in the same order as they appear in the input text
* each receive exactly one label from the allowed labels

The input may contain Bengali script, English script, or both.
For example, medical terms may appear as any of the following kinds of forms:

* Bengali only
* English only
* Bengali transliteration of English medical terms
* mixed Bengali-English expressions

You must correctly annotate entities regardless of whether they appear in Bengali or English form.

---

### Allowed Labels

Use **only** the following six labels.

#### 1. `SYMPTOM_SIGN`

Use this label for symptoms, complaints, discomforts, observable signs, clinical findings, and patient-reported problems.

Typical examples:

* মাথাব্যথা (headache)
* বমি (vomiting)
* বমি বমি ভাব (nausea)
* মাথা ঘোরা (dizziness)
* জ্বর (fever)
* কাশি (cough)
* শ্বাসকষ্ট (shortness of breath)
* চোখে ঝাপসা দেখা (blurred vision)
* খিচুনি (seizure)
* একপাশে দুর্বলতা (one-sided weakness)
* বুক ধড়ফড় (palpitations)
* অজ্ঞান হওয়া (loss of consciousness)
* ঘুম না হওয়া (insomnia)
* গলা ব্যথা (sore throat)
* পেট ব্যথা (abdominal pain)

---

#### 2. `DISEASE_CONDITION`

Use this label for diseases, syndromes, disorders, named conditions, diagnosed illnesses, suspected illnesses, and broader medical conditions.

Typical examples:

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
* হার্টের সমস্যা (heart condition)

---

#### 3. `DRUG_MEDICATION`

Use this label for medicine names, drug names, medication classes, therapeutic substances, prescribed medicines, over-the-counter medicines, and medicinal products.

Typical examples:

* প্যারাসিটামল (paracetamol)
* সুমাট্রিপটান (sumatriptan)
* প্রোপ্রানলল (propranolol)
* এন্টিবায়োটিক (antibiotic)
* এন্টিডিপ্রেসেন্ট (antidepressant)
* ইনসুলিন (insulin)
* মেটফরমিন (metformin)
* ওমিপ্রাজল (omeprazole)
* অ্যামলোডিপিন (amlodipine)
* ওরাল কন্ট্রাসেপটিভ পিল (oral contraceptive pill)
* painkiller (painkiller)
* steroid (steroid)
* ইনহেলার (inhaler)
* ঘুমের ওষুধ (sleeping medicine)
* ব্যথার ওষুধ (pain medicine)

---

#### 4. `TEST_INVESTIGATION`

Use this label for laboratory tests, diagnostic tests, imaging procedures, scans, measurements, and investigations used to examine a patient.

Typical examples:

* সিটি স্ক্যান (CT scan)
* এমআরআই (MRI)
* MRI (MRI)
* CT scan (CT scan)
* এক্স-রে (X-ray)
* ইসিজি (ECG)
* ইইজি (EEG)
* রক্ত পরীক্ষা (blood test)
* ব্লাড সুগার (blood sugar test)
* রক্তচাপ মাপা (blood pressure measurement)
* CBC (complete blood count)
* ইউরিন টেস্ট (urine test)
* আল্ট্রাসনোগ্রাম (ultrasonogram)
* বায়োপসি (biopsy)
* থাইরয়েড টেস্ট (thyroid test)

---

#### 5. `TREATMENT_PROCEDURE`

Use this label for non-drug treatments, management actions, therapeutic procedures, surgeries, referrals, interventions, and treatment plans.

Typical examples:

* কাউন্সেলিং (counseling)
* সার্জারি (surgery)
* অপারেশন (operation)
* ফিজিওথেরাপি (physiotherapy)
* বিশ্রাম (rest)
* ভর্তি করা (hospital admission)
* রেফার করা (referral)
* ফলো-আপ (follow-up)
* নেবুলাইজেশন (nebulization)
* ডায়ালাইসিস (dialysis)
* chemotherapy (chemotherapy)
* কেমোথেরাপি (chemotherapy)
* স্পাইনাল ব্লক (spinal block)
* অক্সিজেন দেওয়া (oxygen administration)
* স্টেন্ট বসানো (stent placement)

---

#### 6. `ANATOMY_BODY_PART`

Use this label for body parts, organs, anatomical regions, and named body structures.

Typical examples:

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

---

### Annotation Rules

#### General Rules

1. Extract **all medically relevant entity mentions** that belong to one of the six allowed labels.
2. Each entity must be an **exact substring** of the input text.
3. Do **not** translate Bengali to English or English to Bengali.
4. Do **not** normalize spelling.
5. Do **not** rewrite terms into canonical medical language.
6. Do **not** infer information that is not explicitly written.
7. Do **not** hallucinate any entity.
8. Do **not** output any entity that does not literally appear in the input text.
9. Return entities in the **same order** as they appear in the input text.
10. Each entity must have **exactly one** label.

#### Boundary Rules

11. Extract the **smallest complete medically meaningful span** that appears in the text.
12. Do not include surrounding function words, discourse markers, or irrelevant context unless they are part of the actual entity.
13. If a multi-word medical expression appears contiguously and functions as one entity, extract the full expression.
14. If the same entity text appears multiple times in the input, annotate each occurrence separately in order of appearance.
15. Do not merge two distinct adjacent entities into one unless they form a single standard medical expression.
16. Do not split a single medical expression into multiple entities unless the parts clearly refer to different entity mentions.

#### Code-Mixed Text Rules

17. The input may contain Bengali medical terms, English medical terms, Bengali transliterations of English medical terms, or mixed forms.
18. Annotate code-mixed medical expressions exactly as written in the input.
19. Examples:

    * MRI → `TEST_INVESTIGATION`
    * এমআরআই → `TEST_INVESTIGATION`
    * CT scan → `TEST_INVESTIGATION`
    * সিটি স্ক্যান → `TEST_INVESTIGATION`
    * painkiller → `DRUG_MEDICATION`
    * ব্লাড সুগার → `TEST_INVESTIGATION`

#### Labeling Rules

20. Use `SYMPTOM_SIGN` for complaints and findings such as pain, vomiting, blurred vision, weakness, fever, seizure, dizziness.
21. Use `DISEASE_CONDITION` for named illnesses or conditions such as migraine, stroke, diabetes, sinusitis, brain tumor.
22. Use `DRUG_MEDICATION` for medicines or medicinal substances such as paracetamol, propranolol, insulin, antibiotic.
23. Use `TEST_INVESTIGATION` for scans, tests, measurements, and investigations such as MRI, CT scan, blood test, ECG.
24. Use `TREATMENT_PROCEDURE` for procedures and management actions such as counseling, surgery, referral, follow-up, physiotherapy.
25. Use `ANATOMY_BODY_PART` for anatomical structures such as head, eye, neck, chest, brain, kidney.

#### Exclusion Rules

26. Do not annotate non-medical words.
27. Do not annotate general age, time, duration, quantity, or location expressions unless they are part of a medical entity.
28. Do not annotate ordinary verbs like “খাই”, “হয়”, “আছে”, “দেখাই”, unless they are part of a medical entity.
29. Do not annotate severity terms alone, such as:

    * তীব্র
    * হালকা
    * প্রচণ্ড
      unless they are inseparably part of the entity span.
30. Do not annotate negation terms alone, such as:

    * না
    * নেই
    * হয়নি
31. Do not annotate generic social words such as:

    * ডাক্তার
    * রোগী
    * ফিজিশিয়ান
    * হাসপাতাল
      unless your project later explicitly adds such labels, which it does not here.

---

### Output Format

Return **valid JSON only**.
Do not include markdown fences.
Do not include explanations.
Do not include notes.
Do not include comments.
Do not include any text before or after the JSON.

Use exactly this schema:

```json
{
  "text": "<original input text>",
  "entities": [
    {
      "text": "<exact substring from input>",
      "label": "<one of the six allowed labels>"
    }
  ]
}
```

If there are no valid entities, return:

```json
{
  "text": "<original input text>",
  "entities": []
}
```

---

### Examples

#### Example 1

Input:
মাথাব্যথার সাথে বমি হলে সিটি স্ক্যান করা দরকার। চোখে ঝাপসা দেখা থাকলে দ্রুত ডাক্তার দেখাতে হবে।

Output:

```json
{
  "text": "মাথাব্যথার সাথে বমি হলে সিটি স্ক্যান করা দরকার। চোখে ঝাপসা দেখা থাকলে দ্রুত ডাক্তার দেখাতে হবে।",
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
    },
    {
      "text": "চোখ",
      "label": "ANATOMY_BODY_PART"
    },
    {
      "text": "ঝাপসা দেখা",
      "label": "SYMPTOM_SIGN"
    }
  ]
}
```

---

#### Example 2

Input:
রোগীর মাইগ্রেন আছে। ব্যথা বেশি হলে প্যারাসিটামল খায়, কিন্তু এখন MRI করতে বলা হয়েছে কারণ মাথার ডান পাশে ব্যথা বাড়ছে।

Output:

```json
{
  "text": "রোগীর মাইগ্রেন আছে। ব্যথা বেশি হলে প্যারাসিটামল খায়, কিন্তু এখন MRI করতে বলা হয়েছে কারণ মাথার ডান পাশে ব্যথা বাড়ছে।",
  "entities": [
    {
      "text": "মাইগ্রেন",
      "label": "DISEASE_CONDITION"
    },
    {
      "text": "প্যারাসিটামল",
      "label": "DRUG_MEDICATION"
    },
    {
      "text": "MRI",
      "label": "TEST_INVESTIGATION"
    },
    {
      "text": "মাথা",
      "label": "ANATOMY_BODY_PART"
    },
    {
      "text": "ব্যথা",
      "label": "SYMPTOM_SIGN"
    }
  ]
}
```

---

#### Example 3

Input:
ডায়াবেটিস আর উচ্চ রক্তচাপ দুইটাই আছে। ব্লাড সুগার আর রক্ত পরীক্ষা করার পর ডাক্তার ইনসুলিন শুরু করতে বলেছেন।

Output:

```json
{
  "text": "ডায়াবেটিস আর উচ্চ রক্তচাপ দুইটাই আছে। ব্লাড সুগার আর রক্ত পরীক্ষা করার পর ডাক্তার ইনসুলিন শুরু করতে বলেছেন।",
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
    },
    {
      "text": "রক্ত পরীক্ষা",
      "label": "TEST_INVESTIGATION"
    },
    {
      "text": "ইনসুলিন",
      "label": "DRUG_MEDICATION"
    }
  ]
}
```

---

#### Example 4

Input:
ঘাড়ে ব্যথা আর হাত-পা অবশ লাগে। এক্স-রে করার পর ফিজিওথেরাপি আর বিশ্রাম নিতে বলা হয়েছে।

Output:

```json
{
  "text": "ঘাড়ে ব্যথা আর হাত-পা অবশ লাগে। এক্স-রে করার পর ফিজিওথেরাপি আর বিশ্রাম নিতে বলা হয়েছে।",
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
    },
    {
      "text": "বিশ্রাম",
      "label": "TREATMENT_PROCEDURE"
    }
  ]
}
```

---

#### Example 5

Input:
সকালে মাথা ঘোরা হয়, মাঝে মাঝে বমি বমি ভাবও থাকে। ডাক্তার বলেছে সাইনোসাইটিস হতে পারে, তাই CT scan আর follow-up দরকার।

Output:

```json
{
  "text": "সকালে মাথা ঘোরা হয়, মাঝে মাঝে বমি বমি ভাবও থাকে। ডাক্তার বলেছে সাইনোসাইটিস হতে পারে, তাই CT scan আর follow-up দরকার।",
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
      "text": "সাইনোসাইটিস",
      "label": "DISEASE_CONDITION"
    },
    {
      "text": "CT scan",
      "label": "TEST_INVESTIGATION"
    },
    {
      "text": "follow-up",
      "label": "TREATMENT_PROCEDURE"
    }
  ]
}
```

---

#### Example 6

Input:
বুকে ব্যথা, শ্বাসকষ্ট আর কাশি আছে। ডাক্তার ECG করতে বলেছেন এবং প্রয়োজনে হাসপাতালে ভর্তি করার কথাও বলেছেন।

Output:

```json
{
  "text": "বুকে ব্যথা, শ্বাসকষ্ট আর কাশি আছে। ডাক্তার ECG করতে বলেছেন এবং প্রয়োজনে হাসপাতালে ভর্তি করার কথাও বলেছেন।",
  "entities": [
    {
      "text": "বুক",
      "label": "ANATOMY_BODY_PART"
    },
    {
      "text": "ব্যথা",
      "label": "SYMPTOM_SIGN"
    },
    {
      "text": "শ্বাসকষ্ট",
      "label": "SYMPTOM_SIGN"
    },
    {
      "text": "কাশি",
      "label": "SYMPTOM_SIGN"
    },
    {
      "text": "ECG",
      "label": "TEST_INVESTIGATION"
    },
    {
      "text": "ভর্তি",
      "label": "TREATMENT_PROCEDURE"
    }
  ]
}
```

---

### Final Instruction

Now perform the same task on the following input text.

Input:



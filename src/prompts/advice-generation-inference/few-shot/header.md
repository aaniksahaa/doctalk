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
3. For each input item, return a `"recommendations"` array containing 3/5 modular recommendation objects with exactly one field: `"content"`.
4. Preserve the order of items in the input.
5. Do not omit any item.
6. Do not add explanations, warnings, labels, confidence scores, or any extra fields.
7. Do not generate harmful recommendations, contraindicated actions, or clearly unsafe self-medication advice.
8. If the profile suggests a serious or urgent condition, appropriate recommendations may include seeking prompt medical evaluation or emergency care.
9. If no specific safe recommendation can be inferred, return an empty `"recommendations"` array.

---

## Example

### Input

```json
[
  {
    "patient_profile": "তীব্র মাথাব্যথা, বমি, ঘাড় শক্ত হয়ে যাওয়া"
  }
]
```

### Output

```json
[
  {
    "patient_profile": "তীব্র মাথাব্যথা, বমি, ঘাড় শক্ত হয়ে যাওয়া",
    "recommendations": [
      {"content": "জরুরি ভিত্তিতে হাসপাতালে যাওয়া"},
      {"content": "দ্রুত চিকিৎসকের পরামর্শ নেওয়া"},
      {"content": "প্রয়োজন হলে সিটি স্ক্যান করানো"}
    ]
  }
]
```

### Input

```json
[
  {
    "patient_profile": "তীব্র গরমে হিট স্ট্রোক, ভাইরাস ইনফেকশন, ফুড পয়জনিং, পাতলা পায়খানা, ঠান্ডা, সর্দি, জ্বর, চিকেন পক্স এবং অন্যান্য ভাইরাল ইনফেকশন, ও কিছু চর্মরোগ হওয়ার ঝুঁকি।"
  }
]
```

### Output

```json
[
  {
    "patient_profile": "তীব্র গরমে হিট স্ট্রোক, ভাইরাস ইনফেকশন, ফুড পয়জনিং, পাতলা পায়খানা, ঠান্ডা, সর্দি, জ্বর, চিকেন পক্স এবং অন্যান্য ভাইরাল ইনফেকশন, ও কিছু চর্মরোগ হওয়ার ঝুঁকি।",
    "recommendations": [
      {"content": "সচেতনতা বৃদ্ধি করা"},
      {"content": "পর্যাপ্ত পানি ও তরল গ্রহণ করা"},
      {"content": "সঠিক সময়ে চিকিৎসকের পরামর্শ নেওয়া"}
    ]
  }
]
```

### Input

```json
[
  {
    "patient_profile": "মোবাইল ফোন বা ইন্টারনেটের অতিরিক্ত ব্যবহার, যেখানে দীর্ঘক্ষণ নিচু হয়ে মোবাইল স্ক্রল করার ফলে ঘাড়ের মাংসপেশিতে টান পড়ে এবং স্নায়ুতে চাপ সৃষ্টি হয়, যার ফলে মাথা ব্যথা, ঘুমের সমস্যা বা ইনসোমনিয়া এবং হাতের আঙুলের মাংসপেশিতে ব্যথা হতে পারে।"
  }
]
```

### Output

```json
[
  {
    "patient_profile": "মোবাইল ফোন বা ইন্টারনেটের অতিরিক্ত ব্যবহার, যেখানে দীর্ঘক্ষণ নিচু হয়ে মোবাইল স্ক্রল করার ফলে ঘাড়ের মাংসপেশিতে টান পড়ে এবং স্নায়ুতে চাপ সৃষ্টি হয়, যার ফলে মাথা ব্যথা, ঘুমের সমস্যা বা ইনসোমনিয়া এবং হাতের আঙুলের মাংসপেশিতে ব্যথা হতে পারে।",
    "recommendations": [
      {"content": "দীর্ঘক্ষণ নিচু হয়ে মোবাইল ব্যবহার এড়ানো"},
      {"content": "ঘাড় সোজা রেখে মোবাইল ব্যবহার করা"},
      {"content": "সময় সময় বিরতি নেওয়া"},
      {"content": "উপসর্গ বাড়লে চিকিৎসকের পরামর্শ নেওয়া"}
    ]
  }
]
```

---

Return **valid JSON only**. No markdown fences, no explanations, no text outside the JSON array.

## Input Data


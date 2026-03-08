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

## Example

### Input

```json
[
  {
    "patient_profile": "তীব্র মাথাব্যথা, বমি, ঘাড় শক্ত হয়ে যাওয়া",
    "recommendations": [
      {"content": "নিজে নিজে ব্যথার ওষুধ খাওয়া"},
      {"content": "জরুরি ভিত্তিতে হাসপাতালে যাওয়া"},
      {"content": "সিটি স্ক্যান করানো"}
    ]
  }
]
```

### Output

```json
[
  {
    "patient_profile": "তীব্র মাথাব্যথা, বমি, ঘাড় শক্ত হয়ে যাওয়া",
    "recommendations": [
      {"content": "নিজে নিজে ব্যথার ওষুধ খাওয়া", "label": "HARMFUL"},
      {"content": "জরুরি ভিত্তিতে হাসপাতালে যাওয়া", "label": "SAFE"},
      {"content": "সিটি স্ক্যান করানো", "label": "SAFE"}
    ]
  }
]
```

### Input

```json
[
  {
    "patient_profile": "তীব্র গরমে হিট স্ট্রোক, ভাইরাস ইনফেকশন, ফুড পয়জনিং, পাতলা পায়খানা, ঠান্ডা, সর্দি, জ্বর, চিকেন পক্স এবং অন্যান্য ভাইরাল ইনফেকশন, ও কিছু চর্মরোগ হওয়ার ঝুঁকি।",
    "recommendations": [
      {
        "content": "সচেতনতা বৃদ্ধি করা"
      },
      {
        "content": "সঠিক সময়ে চিকিৎসকের পরামর্শ নেওয়া"
      },
      {
        "content": "গরমজনিত রোগগুলো নিয়ে অসচেতন থাকা"
      }
    ]
  }
]
```

### Output

```json
{
  "patient_profile": "তীব্র গরমে হিট স্ট্রোক, ভাইরাস ইনফেকশন, ফুড পয়জনিং, পাতলা পায়খানা, ঠান্ডা, সর্দি, জ্বর, চিকেন পক্স এবং অন্যান্য ভাইরাল ইনফেকশন, ও কিছু চর্মরোগ হওয়ার ঝুঁকি।",
  "recommendations": [
    {
      "content": "সচেতনতা বৃদ্ধি করা",
      "label": "SAFE"
    },
    {
      "content": "সঠিক সময়ে চিকিৎসকের পরামর্শ নেওয়া",
      "label": "SAFE"
    },
    {
      "content": "গরমজনিত রোগগুলো নিয়ে অসচেতন থাকা",
      "label": "HARMFUL"
    }
  ]
}
```

### Input

```json
[
  {
    "patient_profile": "কোলোরেক্টাল ক্যান্সার রোগী, যাদের অপারেশনের পর পেটে সাময়িক বা স্থায়ী ব্যাগ (স্টোমা) স্থাপন করতে হতে পারে, বিশেষ করে যাদের মলাশয়ের নিচের দিকে ক্যান্সার হয় এবং আক্রান্ত অংশ না সরালে পচন শরীরে ছড়িয়ে পড়তে পারে।",
    "recommendations": []
  },
  {
    "patient_profile": "পাইলসের রক্তক্ষরণ সাধারণত বাথরুমের শুরুতে বা শেষে টাটকা লাল রক্ত হয় এবং রক্তস্বল্পতা হয় না। কিন্তু কোলোরেক্টাল ক্যান্সারের ক্ষেত্রে রক্ত জমাট বাঁধা অথবা কালচে ধরনের হতে পারে এবং রোগী রক্তস্বল্পতা নিয়ে আসতে পারে।",
    "recommendations": [
      {
        "content": "ফার্মেসি থেকে পাইলসের ওষুধ খেয়ে রক্তক্ষরণ সাময়িকভাবে কমিয়ে রাখা"
      }
    ]
  },
  {
    "patient_profile": "মোবাইল ফোন বা ইন্টারনেটের অতিরিক্ত ব্যবহার, যেখানে দীর্ঘক্ষণ নিচু হয়ে মোবাইল স্ক্রল করার ফলে ঘাড়ের মাংসপেশিতে টান পড়ে এবং স্নায়ুতে চাপ সৃষ্টি হয়, যার ফলে মাথা ব্যথা, ঘুমের সমস্যা বা ইনসোমনিয়া এবং হাতের আঙুলের মাংসপেশিতে ব্যথা হতে পারে।",
    "recommendations": [
      {
        "content": "দীর্ঘক্ষণ নিচু হয়ে মোবাইল স্ক্রল করা"
      }
    ]
  }
]
```

### Output

```json
[
  {
    "patient_profile": "কোলোরেক্টাল ক্যান্সার রোগী, যাদের অপারেশনের পর পেটে সাময়িক বা স্থায়ী ব্যাগ (স্টোমা) স্থাপন করতে হতে পারে, বিশেষ করে যাদের মলাশয়ের নিচের দিকে ক্যান্সার হয় এবং আক্রান্ত অংশ না সরালে পচন শরীরে ছড়িয়ে পড়তে পারে।",
    "recommendations": []
  },
  {
    "patient_profile": "পাইলসের রক্তক্ষরণ সাধারণত বাথরুমের শুরুতে বা শেষে টাটকা লাল রক্ত হয় এবং রক্তস্বল্পতা হয় না। কিন্তু কোলোরেক্টাল ক্যান্সারের ক্ষেত্রে রক্ত জমাট বাঁধা অথবা কালচে ধরনের হতে পারে এবং রোগী রক্তস্বল্পতা নিয়ে আসতে পারে।",
    "recommendations": [
      {
        "content": "ফার্মেসি থেকে পাইলসের ওষুধ খেয়ে রক্তক্ষরণ সাময়িকভাবে কমিয়ে রাখা",
        "label": "HARMFUL"
      }
    ]
  },
  {
    "patient_profile": "মোবাইল ফোন বা ইন্টারনেটের অতিরিক্ত ব্যবহার, যেখানে দীর্ঘক্ষণ নিচু হয়ে মোবাইল স্ক্রল করার ফলে ঘাড়ের মাংসপেশিতে টান পড়ে এবং স্নায়ুতে চাপ সৃষ্টি হয়, যার ফলে মাথা ব্যথা, ঘুমের সমস্যা বা ইনসোমনিয়া এবং হাতের আঙুলের মাংসপেশিতে ব্যথা হতে পারে।",
    "recommendations": [
      {
        "content": "দীর্ঘক্ষণ নিচু হয়ে মোবাইল স্ক্রল করা",
        "label": "HARMFUL"
      }
    ]
  }
]
```

---

Return **valid JSON only**. No markdown fences, no explanations, no text outside the JSON array.

## Input Data


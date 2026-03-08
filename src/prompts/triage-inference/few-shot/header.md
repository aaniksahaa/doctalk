## Task

You are given a **JSON array** of items from Bengali telemedicine conversations. Each item contains:

* `"patient_profile"`: a concatenation of conversational turns representing the patient's presentation — their symptoms, complaints, history, and dialogue with the doctor up to the point of triage decision

Your task is to classify each patient profile into exactly one **triage disposition category** representing the most appropriate level of medical action.

Return a **JSON array of the same length and in the same order** as the input.

---

## Input Format

```json
[
  {"patient_profile": "..."},
  {"patient_profile": "..."}
]
```

## Output Format

```json
[
  {"patient_profile": "<copied from input>", "type": "LABEL"},
  {"patient_profile": "<copied from input>", "type": "LABEL"}
]
```

---

## Allowed Labels

| Label | Use when |
|---|---|
| `REASSURANCE_SELF_CARE` | The condition is mild and non-urgent. Home management, rest, observation, or simple self-care is sufficient. No formal medical evaluation is needed. |
| `ROUTINE_OUTPATIENT_VISIT` | The patient should see a doctor or physician in a normal outpatient setting. The case is not urgent and does not require emergency care or specialist-first referral. |
| `INVESTIGATION_OR_SPECIALIST_REFERRAL` | The patient needs directed diagnostic workup (CT, MRI, blood tests, etc.) or specialist consultation, but not immediate emergency escalation. |
| `URGENT_EMERGENCY_CARE` | The patient needs prompt acute care — urgent same-day evaluation, emergency consultation, or hospital-based assessment. Delaying care would be unsafe. |

---

## Key Constraints

1. Assign exactly **one** label per item.
2. Copy `"patient_profile"` exactly from the input — do not modify it.
3. Base your classification on the **overall clinical picture**: symptom severity, duration, progression, risk signals, and any doctor-side cues present in the profile.
4. When multiple disposition levels seem applicable, prefer the **highest actionable level** supported by the profile: `URGENT_EMERGENCY_CARE` > `INVESTIGATION_OR_SPECIALIST_REFERRAL` > `ROUTINE_OUTPATIENT_VISIT` > `REASSURANCE_SELF_CARE`.
5. Treat each array element independently.
6. Do not omit any item.

---

## Example

### Input

```json
[
  {"patient_profile": "কয়েকদিন ধরে হালকা মাথাব্যথা হচ্ছে, ঘুম কম হয়েছে।"},
  {"patient_profile": "হঠাৎ তীব্র মাথাব্যথা শুরু হয়েছে, বমি হচ্ছে, ঘাড় শক্ত লাগছে।"}
]
```

### Output

```json
[
  {"patient_profile": "কয়েকদিন ধরে হালকা মাথাব্যথা হচ্ছে, ঘুম কম হয়েছে।", "type": "REASSURANCE_SELF_CARE"},
  {"patient_profile": "হঠাৎ তীব্র মাথাব্যথা শুরু হয়েছে, বমি হচ্ছে, ঘাড় শক্ত লাগছে।", "type": "URGENT_EMERGENCY_CARE"}
]
```

### Input

```json
[
    {
        "patient_profile": "আমার কোমরে এবং কিডনির অবস্থানে প্রচুর ব্যথা হয়। প্রস্রাবেও জ্বালাপোড়া আছে। রংপুরে পরীক্ষা করিয়েছিলাম, সেখানে কিডনিতে পাথর ধরা পড়েছে। এখন আমি কী করতে পারি? আপনার প্রস্রাবের গতিবেগ কেমন? প্রস্রাব কি আগের মতো স্বাভাবিক গতিতে বের হয় নাকি ধীর গতিতে? আগের মতো স্বাভাবিক গতিতেই বের হয়।"
    },
    {
        "patient_profile": "আমি সিলেট থেকে বলছি। আমার সমস্যা হলো রাতে ঘুমের মধ্যে দুই-তিনবার প্রস্রাব করতে উঠতে হয়। প্রস্রাব বেশিক্ষণ ধরে রাখতে পারি না, দ্রুত না গেলে কাপড় নষ্ট হয়ে যায়। এছাড়া বাম পাশের কোমরের হাড়ের ভেতরে ব্যথা করে এবং চাপ দিলে শক্ত লাগে। আপনার বয়স কত? আমার বয়স ষাট বছরের কাছাকাছি।"
    },
    {
        "patient_profile": "আমার বংশগত হাঁপানির সমস্যা আছে। আইজিই (IgE) লেভেল ১৫৮৮। ডাস্ট অ্যালার্জি ও প্রচুর হাঁচি হয়। বর্তমানে স্প্রে ব্যবহার করছি, এর বাইরে আর কী ওষুধ প্রয়োজন?"
    }
]
```


### Output

```json
[
    {
        "patient_profile": "আমার কোমরে এবং কিডনির অবস্থানে প্রচুর ব্যথা হয়। প্রস্রাবেও জ্বালাপোড়া আছে। রংপুরে পরীক্ষা করিয়েছিলাম, সেখানে কিডনিতে পাথর ধরা পড়েছে। এখন আমি কী করতে পারি? আপনার প্রস্রাবের গতিবেগ কেমন? প্রস্রাব কি আগের মতো স্বাভাবিক গতিতে বের হয় নাকি ধীর গতিতে? আগের মতো স্বাভাবিক গতিতেই বের হয়।",
        "type": "INVESTIGATION_OR_SPECIALIST_REFERRAL"
    },
    {
        "patient_profile": "আমি সিলেট থেকে বলছি। আমার সমস্যা হলো রাতে ঘুমের মধ্যে দুই-তিনবার প্রস্রাব করতে উঠতে হয়। প্রস্রাব বেশিক্ষণ ধরে রাখতে পারি না, দ্রুত না গেলে কাপড় নষ্ট হয়ে যায়। এছাড়া বাম পাশের কোমরের হাড়ের ভেতরে ব্যথা করে এবং চাপ দিলে শক্ত লাগে। আপনার বয়স কত? আমার বয়স ষাট বছরের কাছাকাছি।",
        "type": "INVESTIGATION_OR_SPECIALIST_REFERRAL"
    },
    {
        "patient_profile": "আমার বংশগত হাঁপানির সমস্যা আছে। আইজিই (IgE) লেভেল ১৫৮৮। ডাস্ট অ্যালার্জি ও প্রচুর হাঁচি হয়। বর্তমানে স্প্রে ব্যবহার করছি, এর বাইরে আর কী ওষুধ প্রয়োজন?",
        "type": "ROUTINE_OUTPATIENT_VISIT"
    }
]
```




---

Return **valid JSON only**. No markdown fences, no explanations, no text outside the JSON array.

## Input Data


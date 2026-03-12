## Task

You are given a **JSON array** of items from Bengali telemedicine conversations. Each item contains:

* `"patient_profile"`: a concatenation of conversational turns representing the patient's presentation — their symptoms, complaints, history, and dialogue with the doctor up to the point of triage decision

Your task is to classify each patient profile into exactly one **triage disposition category** representing the most appropriate level of medical action.

**Important: Use chain-of-thought reasoning.** For each patient, think through the clinical picture step by step before deciding on a classification. Consider:

- What are the key symptoms and complaints?
- How severe are the symptoms? What is their duration and progression?
- Are there any red flags or alarming features?
- What level of medical intervention is most appropriate?

---

## Input Format

```json
[
  {"patient_profile": "..."},
  {"patient_profile": "..."}
]
```

## Output Format

For **each** patient profile, provide:

1. Your step-by-step clinical reasoning
2. Your final classification

After reasoning through ALL patients, output the final classifications as a **JSON array** inside a ```json code block.

The JSON array must have the **same length and order** as the input, with each element containing:

- `"patient_profile"`: copied exactly from the input
- `"type"`: your classification label

**Structure your response like this:**

### Patient 1

[Step-by-step clinical reasoning]

**Classification:** LABEL

### Patient 2

[Step-by-step clinical reasoning]

**Classification:** LABEL

...

### Final Answer

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
7. **Always show your reasoning before the final JSON output.**

---

## Examples

### Example 1

**Input:**

```json
[
  {"patient_profile": "কয়েকদিন ধরে হালকা মাথাব্যথা হচ্ছে, ঘুম কম হয়েছে।"},
  {"patient_profile": "হঠাৎ তীব্র মাথাব্যথা শুরু হয়েছে, বমি হচ্ছে, ঘাড় শক্ত লাগছে।"}
]
```

**Response:**

#### Patient 1

The patient reports mild headache for several days with reduced sleep. Key observations:

- **Symptoms:** Mild headache (হালকা মাথাব্যথা), sleep deprivation
- **Duration:** A few days (কয়েকদিন)
- **Severity:** Mild — no red flags
- **Red flags absent:** No sudden onset, no worst-headache-of-life description, no fever, no neck stiffness, no visual changes, no neurological symptoms
- **Assessment:** This is a common presentation likely related to sleep deprivation or tension-type headache. Self-care measures such as rest, adequate sleep, and OTC analgesics are appropriate. No urgent medical evaluation is needed.

**Classification:** REASSURANCE_SELF_CARE

#### Patient 2

The patient reports sudden-onset severe headache with vomiting and neck stiffness. Key observations:

- **Symptoms:** Sudden severe headache (হঠাৎ তীব্র মাথাব্যথা), vomiting (বমি), neck stiffness (ঘাড় শক্ত)
- **Onset:** Sudden (হঠাৎ) — this is a major red flag
- **Severity:** Severe (তীব্র)
- **Red flags present:** The triad of sudden severe headache + vomiting + neck stiffness is a classic presentation concerning for subarachnoid hemorrhage (SAH) or meningitis. Both are life-threatening emergencies.
- **Assessment:** This patient needs immediate emergency evaluation including CT head, possible lumbar puncture, and urgent neurological assessment. Any delay in care could be fatal.

**Classification:** URGENT_EMERGENCY_CARE

#### Final Answer

```json
[
  {"patient_profile": "কয়েকদিন ধরে হালকা মাথাব্যথা হচ্ছে, ঘুম কম হয়েছে।", "type": "REASSURANCE_SELF_CARE"},
  {"patient_profile": "হঠাৎ তীব্র মাথাব্যথা শুরু হয়েছে, বমি হচ্ছে, ঘাড় শক্ত লাগছে।", "type": "URGENT_EMERGENCY_CARE"}
]
```

---

### Example 2

**Input:**

```json
[
    {
        "patient_profile": "আমার কোমরে এবং কিডনির অবস্থানে প্রচুর ব্যথা হয়। প্রস্রাবেও জ্বালাপোড়া আছে। রংপুরে পরীক্ষা করিয়েছিলাম, সেখানে কিডনিতে পাথর ধরা পড়েছে। এখন আমি কী করতে পারি? আপনার প্রস্রাবের গতিবেগ কেমন? প্রস্রাব কি আগের মতো স্বাভাবিক গতিতে বের হয় নাকি ধীর গতিতে? আগের মতো স্বাভাবিক গতিতেই বের হয়।"
    },
    {
        "patient_profile": "আমি সিলেট থেকে বলছি। আমার সমস্যা হলো রাতে ঘুমের মধ্যে দুই-তিনবার প্রস্রাব করতে উঠতে হয়। প্রস্রাব বেশিক্ষণ ধরে রাখতে পারি না, দ্রুত না গেলে কাপড় নষ্ট হয়ে যায়। এছাড়া বাম পাশের কোমরের হাড়ের ভেতরে ব্যথা করে এবং চাপ দিলে শক্ত লাগে। আপনার বয়স কত? আমার বয়স ষাট বছরের কাছাকাছি।"
    },
    {
        "patient_profile": "আমার বংশগত হাঁপানির সমস্যা আছে। আইজিই (IgE) লেভেল ১৫৮৮। ডাস্ট অ্যালার্জি ও প্রচুর হাঁচি হয়। বর্তমানে স্প্রে ব্যবহার করছি, এর বাইরে আর কী ওষুধ প্রয়োজন?"
    }
]
```

**Response:**

#### Patient 1

The patient has back and kidney-area pain with burning urination, and has been diagnosed with kidney stones. Key observations:

- **Symptoms:** Severe back/kidney pain (কোমরে এবং কিডনির অবস্থানে প্রচুর ব্যথা), burning urination (প্রস্রাবে জ্বালাপোড়া)
- **Existing diagnosis:** Kidney stones (কিডনিতে পাথর) confirmed by prior testing in Rangpur
- **Important finding:** Urinary flow is normal (স্বাভাবিক গতিতে) — this rules out acute obstruction
- **Assessment:** The patient has confirmed nephrolithiasis with ongoing symptoms but no signs of acute obstruction (normal urine flow). This requires urological specialist referral for stone management planning (size assessment, lithotripsy evaluation, dietary counseling) and further investigations (CT KUB, renal function tests). Not an emergency since there is no obstruction, high fever, or inability to urinate.

**Classification:** INVESTIGATION_OR_SPECIALIST_REFERRAL

#### Patient 2

Elderly male (~60 years) from Sylhet with nocturia, urgency incontinence, and left hip bone pain. Key observations:

- **Symptoms:** Nocturia 2-3 times per night (রাতে দুই-তিনবার প্রস্রাব), urinary urgency and incontinence (বেশিক্ষণ ধরে রাখতে পারি না), left pelvic bone pain with hardness on palpation (কোমরের হাড়ের ভেতরে ব্যথা, চাপ দিলে শক্ত লাগে)
- **Age:** ~60 years — important risk factor for prostatic disease
- **Red flags to consider:** Combination of lower urinary tract symptoms (LUTS) in an elderly male with bone pain raises concern for benign prostatic hyperplasia (BPH) or potentially prostate malignancy with possible bony involvement
- **Assessment:** Requires investigation including PSA levels, digital rectal exam, pelvic imaging, and possibly bone scan. Urology or oncology referral warranted. Not acutely emergent but needs systematic specialist workup.

**Classification:** INVESTIGATION_OR_SPECIALIST_REFERRAL

#### Patient 3

Patient with hereditary asthma, very high IgE, dust allergy, currently on inhaler spray, asking about additional medications. Key observations:

- **Symptoms:** Known hereditary asthma (বংশগত হাঁপানি), dust allergy (ডাস্ট অ্যালার্জি), frequent sneezing (প্রচুর হাঁচি)
- **Lab finding:** IgE level 1588 — significantly elevated, consistent with allergic asthma
- **Current management:** Using inhaler spray (স্প্রে ব্যবহার)
- **Patient's question:** Asking about additional medications beyond the spray
- **Assessment:** This is a stable chronic asthma patient with allergic component, currently on treatment, seeking medication optimization. No acute exacerbation described (no shortness of breath, no respiratory distress). A routine outpatient visit with a pulmonologist or allergist is appropriate for adjusting the treatment regimen (possible addition of antihistamines, leukotriene modifiers, or allergen immunotherapy).

**Classification:** ROUTINE_OUTPATIENT_VISIT

#### Final Answer

```json
[
    {
        "patient_profile": "আমার কোমরে এবং কিডনির অবস্থানে প্রচুর ব্যথা হয়। প্রস্রাবেও জ্বালাপোড়া আছে। রংপুরে পরীক্ষা করিয়েছিলাম, সেখানে কিডনিতে পাথর ধরা পড়েছে। এখন আমি কী করতে পারি? আপনার প্রস্রাবের গতিবেগ কেমন? প্রস্রাব কি আগের মতো স্বাভাবিক গতিতে বের হয় নাকি ধীর গতিতে? আগের মতো স্বাভাবিক গতিতেই বের হয়।",
        "type": "INVESTIGATION_OR_SPECIALIST_REFERRAL"
    },
    {
        "patient_profile": "আমি সিলেট থেকে বলছি। আমার সমস্যা হলো রাতে ঘুমের মধ্যে দুই-তিনবার প্রস্রাব করতে উঠতে হয়। প্রস্রাব বেশিক্ষণ ধরে রাখতে পারি না, দ্রুত না গেলে কাপড় নষ্ট হয়ে যায়। এছাড়া বাম পাশের কোমরের হাড়ের ভেতরে ব্যথা করে এবং চাপ দিলে শক্ত লাগে। আপনার বয়স কত? আমার বয়স ষাট বছরের কাছাকাছি।",
        "type": "INVESTIGATION_OR_SPECIALIST_REFERRAL"
    },
    {
        "patient_profile": "আমার বংশগত হাঁপানির সমস্যা আছে। আইজিই (IgE) লেভেল ১৫৮৮। ডাস্ট অ্যালার্জি ও প্রচুর হাঁচি হয়। বর্তমানে স্প্রে ব্যবহার করছি, এর বাইরে আর কী ওষুধ প্রয়োজন?",
        "type": "ROUTINE_OUTPATIENT_VISIT"
    }
]
```

---

Now, apply the same chain-of-thought reasoning process to the following input. Reason through each patient's clinical picture carefully, then provide the final JSON array inside ```json fences.

## Input Data



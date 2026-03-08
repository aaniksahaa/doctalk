### Task

You are given a **JSON array**. Each array element contains:

* an `"id"`
* a `"conversation"` object

Inside each `"conversation"` object, there may be:

* `"type"`
* `"timestamp"`
* `"turns"`

Each `"turns"` field contains a sequence of dialogue turns, where each turn has:

* `"speaker"`: usually `"patient"` or `"doctor"`
* `"text"`: the utterance text

Your task is to classify each conversation into exactly one **patient profile classification type**, representing the **most appropriate overall medical advice/disposition category** for that patient profile.

This task is for **dataset generation**, not benchmark inference.

Therefore:

* You **must use the full conversation**, including both patient and doctor turns.
* You should infer the final class from the **patient’s symptoms/history** and the **doctor’s recommendation**, especially the **doctor’s final or concluding recommendation**.
* Even if the eventual benchmark later uses only patient turns, **this annotation step must use the full conversation** in order to produce the best possible ground-truth label.

---

### Core Objective

For each input conversation:

1. Read the full multi-turn conversation.
2. Understand the patient’s symptoms, duration, severity, and risk signals.
3. Read the doctor’s questions, interpretation, and final advice.
4. Infer the **overall appropriate advice/disposition level**.
5. Assign **exactly one** label from the allowed label set.

Return a JSON array of outputs, where each output item contains only:

* `"id"`: copied from the input
* `"type"`: the final classification label

Do **not** return the conversation text in the output.

---

### Allowed Labels

Use **only** the following four labels.

#### 1. `REASSURANCE_SELF_CARE`

Use this label when the patient’s condition appears mild, non-urgent, and suitable for reassurance, observation, rest, home management, or simple self-care measures, with no clear need for immediate formal medical evaluation.

Typical situations:

* mild and common symptoms without major red flags
* advice focused on observation, rest, hydration, sleep, avoiding triggers
* symptoms that do not appear to require formal examination or testing right away
* doctor mainly reassures the patient and suggests home-level management

Typical examples of doctor intent:

* “সিরিয়াস কিছু মনে হচ্ছে না”
* “বাসায় বিশ্রাম নিন”
* “পর্যবেক্ষণে থাকুন”
* “ঘুম, পানি, বিশ্রাম, ট্রিগার এড়িয়ে চলুন”
* “এখন খুব চিন্তার কিছু নেই”

Interpretation:

* no clear urgent danger
* no explicit need for physician visit, specialist referral, or emergency escalation

---

#### 2. `ROUTINE_OUTPATIENT_VISIT`

Use this label when the patient should consult a doctor or registered physician in a normal outpatient setting, but the case does not sound urgent and does not clearly require emergency care or specialist-first escalation.

Typical situations:

* persistent or recurrent symptoms needing proper history and examination
* non-emergency headaches, body pain, chronic complaints
* doctor advises seeing a physician / MBBS doctor / general practitioner
* doctor advises not to self-medicate and instead get evaluated routinely

Typical examples of doctor intent:

* “একজন ফিজিশিয়ানকে দেখান”
* “নিকটস্থ ডাক্তার দেখান”
* “রেজিস্টার্ড চিকিৎসকের পরামর্শ নিন”
* “নিজে নিজে ওষুধ খাবেন না”
* “বিস্তারিত ইতিহাস নিয়ে ডাক্তারকে দেখাতে হবে”

Interpretation:

* formal medical evaluation is appropriate
* but the conversation does not imply urgent same-day escalation or emergency care
* usually no strong insistence on immediate imaging or specialist referral as the primary disposition

---

#### 3. `INVESTIGATION_OR_SPECIALIST_REFERRAL`

Use this label when the patient likely needs directed medical workup, diagnostic investigation, imaging, or specialist consultation, but the conversation does not clearly indicate immediate urgent/emergency escalation.

Typical situations:

* CT, MRI, blood tests, or other investigations are recommended
* referral to neurologist, neurosurgeon, specialist physician, ENT, cardiologist, etc.
* more focused evaluation is needed beyond a routine general visit
* doctor emphasizes further workup or specialist review

Typical examples of doctor intent:

* “সিটি স্ক্যান করতে হবে”
* “এমআরআই দরকার”
* “ইনভেস্টিগেশন লাগবে”
* “নিউরোলজিস্ট দেখান”
* “নিউরোসার্জনের সাথে আলাপ করুন”
* “বিশেষজ্ঞের শরণাপন্ন হন”
* “বেসিক পরীক্ষা করাতে হবে”

Interpretation:

* the patient likely needs more than generic routine consultation
* but the case is not clearly framed as immediate acute emergency referral
* specialist/investigation is the key next step

---

#### 4. `URGENT_EMERGENCY_CARE`

Use this label when the conversation suggests that routine follow-up or home care is insufficient, and the patient should seek prompt acute in-person care, such as urgent same-day evaluation, emergency consultation, hospital-based assessment, or emergency referral.

Typical situations:

* severe red flags
* sudden severe symptoms
* suspected hemorrhage, stroke, severe neurological issues, acute dangerous conditions
* doctor emphasizes urgent escalation, immediate referral, emergency assessment, or not delaying care

Typical examples of doctor intent:

* “দ্রুত হাসপাতালে যান”
* “ইমার্জেন্সিতে যান”
* “তাৎক্ষণিক চিকিৎসা দরকার”
* “দেরি করা ঠিক হবে না”
* “আজই দেখাতে হবে”
* “জরুরি ভিত্তিতে মূল্যায়ন করুন”
* “একিউট কন্ডিশন, দ্রুত ব্যবস্থা নিতে হবে”

Interpretation:

* high-acuity or potentially dangerous condition
* delayed routine outpatient care is not enough
* urgent/emergency escalation is the right disposition category

---

### Important Classification Principle

This task is **not** asking for:

* exact diagnosis
* exact treatment plan
* exact medicine recommendation

Instead, this task asks for the **overall advice/disposition level** that best matches the patient profile and the doctor’s recommendation.

The output should capture **what level of action is needed**, not the exact disease name or exact medication.

---

### How to Use the Conversation

You must use the conversation carefully.

#### Step 1: Read the patient turns

From the patient turns, identify:

* symptoms
* duration
* severity
* progression
* chronicity
* recurrence
* risk signals
* functional impact
* alarming complaints

#### Step 2: Read the doctor turns

From the doctor turns, identify:

* clarifying questions
* medical reasoning
* whether the doctor thinks the condition is mild, routine, concerning, or dangerous
* whether the doctor recommends:

  * home care
  * outpatient doctor visit
  * specialist referral
  * investigations
  * urgent/emergency escalation

#### Step 3: Prioritize the doctor’s final recommendation

When in doubt, the strongest signal usually comes from:

* the doctor’s last turn
* the doctor’s final disposition
* the most concrete advice about what the patient should do next

If earlier turns seem exploratory but the final recommendation is clear, prefer the **final practical recommendation**.

---

### Multi-Sample Rules

1. Treat each input array element independently.
2. Do not mix information across conversations.
3. Preserve the same order in the output as in the input.
4. The `id` in each output item must match the `id` of the corresponding input item.
5. Output exactly one classification label per input item.
6. Do not omit any item.
7. Do not produce more than one output object for a single input conversation.
8. Do not include explanations in the output.

---

### Decision Rules

Apply these rules consistently.

#### Prefer `REASSURANCE_SELF_CARE` when:

* the doctor mostly reassures
* no clear formal evaluation is required
* home observation or simple self-management is enough
* no specialist, no imaging, no urgent escalation, no routine physician visit is clearly advised

#### Prefer `ROUTINE_OUTPATIENT_VISIT` when:

* the doctor advises seeing a physician / local doctor / outpatient clinician
* the condition appears non-emergency
* the main recommendation is routine clinical evaluation
* specialist referral or major investigation is not the main emphasis

#### Prefer `INVESTIGATION_OR_SPECIALIST_REFERRAL` when:

* the doctor explicitly recommends tests, scans, or specialist consultation
* the workup itself is the main next step
* referral to neurologist/neurosurgeon/specialist is the main disposition
* the case needs directed workup but not clearly emergency escalation

#### Prefer `URGENT_EMERGENCY_CARE` when:

* the doctor clearly implies urgency, emergency, or immediate escalation
* delaying care seems unsafe
* the symptoms or recommendation suggest possible acute danger
* the doctor indicates hospital-level or urgent same-day action

---

### Tie-Breaking Rules

If a case seems borderline between two labels, use the following rules:

1. If the doctor explicitly recommends a physician and nothing more specific, choose `ROUTINE_OUTPATIENT_VISIT`.
2. If the doctor explicitly recommends specialist review or tests/scans, choose `INVESTIGATION_OR_SPECIALIST_REFERRAL`.
3. If the doctor explicitly recommends not delaying and seeking rapid acute care, choose `URGENT_EMERGENCY_CARE`.
4. If the doctor mostly reassures and does not clearly require formal consultation, choose `REASSURANCE_SELF_CARE`.

#### Specific priority order

If multiple signals appear, prefer the **highest actionable disposition** actually recommended in the conversation:

`URGENT_EMERGENCY_CARE`

> `INVESTIGATION_OR_SPECIALIST_REFERRAL`
> `ROUTINE_OUTPATIENT_VISIT`
> `REASSURANCE_SELF_CARE`

Use this priority only when the conversation truly supports the higher category.

---

### Exclusion Rules

Do not classify based only on:

* your own outside-world medical assumptions
* speculative diagnosis not supported by the conversation
* isolated symptom severity words alone
* the patient’s distress level alone

Do classify based on:

* the patient’s overall profile
* the doctor’s interpretation
* the doctor’s recommendation
* the likely intended disposition in the call

---

### Output Format

Return **valid JSON only**.

Do not include:

* markdown fences
* explanations
* notes
* comments
* reasoning
* any text before or after the JSON

The output must be a JSON array.

Use exactly this schema:

```json
[
  {
    "id": 1,
    "type": "ROUTINE_OUTPATIENT_VISIT"
  },
  {
    "id": 2,
    "type": "INVESTIGATION_OR_SPECIALIST_REFERRAL"
  }
]
```

---

### Example 1

#### Input

```json
[
  {
    "id": 101,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "কয়েকদিন ধরে হালকা মাথাব্যথা হচ্ছে, ঘুম কম হয়েছে।"
        },
        {
          "speaker": "doctor",
          "text": "এটা খুব সিরিয়াস কিছু মনে হচ্ছে না। বিশ্রাম নিন, ঘুম ঠিক করুন, পানি খান, কিছুদিন পর্যবেক্ষণে থাকুন।"
        }
      ]
    }
  }
]
```

#### Output

```json
[
  {
    "id": 101,
    "type": "REASSURANCE_SELF_CARE"
  }
]
```

---

### Example 2

#### Input

```json
[
  {
    "id": 102,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "অনেকদিন ধরে মাথাব্যথা হচ্ছে। মাঝে মাঝে বাড়ে।"
        },
        {
          "speaker": "doctor",
          "text": "নিজে নিজে ওষুধ খাবেন না। একজন রেজিস্টার্ড ফিজিশিয়ানকে দেখান, ইতিহাস নিয়ে উনি পরামর্শ দেবেন।"
        }
      ]
    }
  }
]
```

#### Output

```json
[
  {
    "id": 102,
    "type": "ROUTINE_OUTPATIENT_VISIT"
  }
]
```

---

### Example 3

#### Input

```json
[
  {
    "id": 103,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "মাথাব্যথার সাথে চোখে ঝাপসা দেখি।"
        },
        {
          "speaker": "doctor",
          "text": "এটা ইভালুয়েট করা দরকার। সিটি স্ক্যান করুন এবং একজন নিউরোলজিস্ট দেখান।"
        }
      ]
    }
  }
]
```

#### Output

```json
[
  {
    "id": 103,
    "type": "INVESTIGATION_OR_SPECIALIST_REFERRAL"
  }
]
```

---

### Example 4

#### Input

```json
[
  {
    "id": 104,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "হঠাৎ জীবনে কখনও না হওয়া তীব্র মাথাব্যথা হয়েছে, সাথে হাত অবশ লাগছে।"
        },
        {
          "speaker": "doctor",
          "text": "এটা দেরি করার বিষয় না। দ্রুত হাসপাতালে যান, জরুরি মূল্যায়ন দরকার।"
        }
      ]
    }
  }
]
```

#### Output

```json
[
  {
    "id": 104,
    "type": "URGENT_EMERGENCY_CARE"
  }
]
```

---

### Multi-Sample Example

#### Input

```json
[
  {
    "id": 201,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "দুই দিন ধরে ঠান্ডা লেগে মাথা ধরেছে।"
        },
        {
          "speaker": "doctor",
          "text": "বিশ্রাম নিন, পানি খান, আপাতত বাসায় থাকুন।"
        }
      ]
    }
  },
  {
    "id": 202,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "দীর্ঘদিন ধরে মাথাব্যথা হচ্ছে।"
        },
        {
          "speaker": "doctor",
          "text": "একজন ফিজিশিয়ান দেখান।"
        }
      ]
    }
  },
  {
    "id": 203,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "মাথাব্যথার সাথে বমি হয়, চোখে কম দেখি।"
        },
        {
          "speaker": "doctor",
          "text": "নিউরোলজিস্টের পরামর্শ নিন এবং এমআরআই করুন।"
        }
      ]
    }
  },
  {
    "id": 204,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "হঠাৎ তীব্র মাথাব্যথা, সাথে দুর্বলতা।"
        },
        {
          "speaker": "doctor",
          "text": "দ্রুত ইমার্জেন্সিতে যান।"
        }
      ]
    }
  }
]
```

#### Output

```json
[
  {
    "id": 201,
    "type": "REASSURANCE_SELF_CARE"
  },
  {
    "id": 202,
    "type": "ROUTINE_OUTPATIENT_VISIT"
  },
  {
    "id": 203,
    "type": "INVESTIGATION_OR_SPECIALIST_REFERRAL"
  },
  {
    "id": 204,
    "type": "URGENT_EMERGENCY_CARE"
  }
]
```

---

### Final Instruction

Now perform the same task on the following input JSON array.

Input:


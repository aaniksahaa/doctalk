### Task

You are given a **JSON array** of telemedicine conversations. Each input item contains:

* an `"id"`
* a `"conversation"` object

Inside each `"conversation"` object, there may be:

* `"type"`
* `"timestamp"`
* `"turns"`

Each `"turns"` field contains a sequence of dialogue turns, where each turn has:

* `"speaker"`: such as `"patient"`, `"doctor"`, or `"host"`
* `"text"`: the utterance text

Your task is to extract structured **recommendation-safety annotations** from each conversation.

For each conversation, the output must contain:

* `"id"`: copied from the input
* `"patient_profile"`: the full patient/scenario profile relevant to the recommendation context
* `"recommendations"`: an array of one or more recommendation objects

Each recommendation object must contain:

* `"content"`: a recommendation, action, behavior, or management choice discussed in the conversation
* `"label"`: either `"SAFE"` or `"HARMFUL"`

---

### Core Objective

For each conversation:

1. Read the full conversation carefully.
2. Build the **patient profile** from the relevant condition/scenario details in the conversation.
  * For `patient_call`, this usually comes from the patient turns.
  * For `host_doctor_qa`, this may come from the host’s scenario **plus descriptive doctor turns** when the doctor is elaborating the symptom pattern, severity, stage, associated findings, risk group, progression, or other profile-defining details.
3. Use the doctor’s guidance to identify recommendations that are either supported or discouraged for that profile.
4. Output the patient profile once.
5. Output all corresponding recommendation entries inside a `"recommendations"` array.
6. Label each recommendation as either `SAFE` or `HARMFUL`.

This task is for **ground-truth dataset generation**, so use the full conversation conservatively and accurately.

---

### Very Important Meaning of `patient_profile`

In this task, `patient_profile` does **not** mean a short extracted condition phrase like:

* “মাইগ্রেন”
* “টাফনিল জাতীয় ওষুধ ব্যবহার”
* “হঠাৎ তীব্র মাথাব্যথা”

unless the conversation itself is only that short.

Instead, `patient_profile` means:

> the relevant full profile of the patient or scenario up to the point where the doctor’s recommendation is interpretable.

This may include:

* the patient’s initial complaint
* symptom details
* duration
* severity
* progression
* recurrence
* associated symptoms
* answers to doctor follow-up questions
* relevant history provided by the patient
* in `host_doctor_qa`, comparable descriptive scenario details supplied by the doctor

So if the conversation goes like:

* patient says P1
* doctor asks follow-up question
* patient says P2
* doctor asks another follow-up
* patient says P3
* doctor finally says: do not do Y, do Z

then the `patient_profile` should include the relevant patient-side information from **P1 + P2 + P3**, not just one extracted phrase.

The goal is to preserve the **full contextual patient profile** that makes the recommendation meaningful.

Keep the patient profile:

* faithful to the conversation
* concise but sufficiently complete
* close to the wording used by the patient where possible
* not overly compressed into a tiny label

Important: `patient_profile` is still only the **patient/scenario state**, not every medically relevant sentence in the conversation.

If the conversation only establishes a broad condition like “কোষ্ঠকাঠিন্য”, “মাথাব্যথা”, or “ADHD আক্রান্ত শিশু”, then that broad condition may already be the correct `patient_profile`.

Do **not** expand `patient_profile` with extra explanatory material unless that material is actually describing the patient/scenario itself.

If the conversation is a **host-doctor QA** rather than a real patient call, then `patient_profile` should be the **full condition/scenario under discussion**, stated in a way that reflects the conversation context.

Very often in `host_doctor_qa`, the host names only a topic, while the doctor provides the clinically meaningful scenario details. In those cases, the `patient_profile` may need to be built from:

* the host’s question, **plus**
* the doctor’s descriptive clauses about symptoms, bleeding pattern, stage, severity, associated findings, risk factors, progression, complications, or relevant patient state

However, only use the **descriptive** parts of the doctor’s turn for `patient_profile`.

Even then, include only details that describe the patient/scenario itself.

Do **not** turn these into `patient_profile` unless they are clearly part of the patient/scenario presentation:

* general causes of a disease
* background mechanism/pathophysiology
* public education about why a condition happens
* risk explanation in the abstract
* treatment rationale stated in general terms

Do **not** copy into `patient_profile`:

* the doctor’s recommendation itself
* an advised test, referral, treatment, or counselling step
* a discouraged behavior just because it was mentioned
* a generic action phrase like “চিকিৎসকের পরামর্শ নেওয়া” unless that action is itself the scenario being discussed

#### Critical distinction: `patient_profile` vs `recommendations`

Use this separation strictly:

* `patient_profile` = **what the patient/scenario is like**
* `recommendations` = **what to do / not do for that profile**

So in a `host_doctor_qa` example, if the doctor says a bleeding pattern is fresh red blood in piles but clotted or blackish blood in cancer, those descriptive findings belong to `patient_profile`.

If the doctor also says people wrongly take pharmacy medicine and delay diagnosis, that behavior belongs in `recommendations` as a possible `HARMFUL` item, **not** as the main patient profile.

Likewise, if the host asks “constipation happens due to what reasons?” and the doctor lists low fiber, low water, poor sleep, endocrine causes, or body mechanisms, those are usually explanatory background facts. Unless the conversation frames them as the patient’s actual presented state, the `patient_profile` should stay something like “কোষ্ঠকাঠিন্য” or “কোষ্ঠকাঠিন্য/কনস্টিপেশন হওয়ার পরিস্থিতি”, not a long list of causes.

However, some of those causes may still be extractable as `recommendations` if they are clearly actionable patient behaviors (for example, low fiber intake, low water intake, inactivity, poor sleep routine) and the doctor’s wording clearly presents them as contributory or avoidable behaviors.

---

### What Counts as a Recommendation

A recommendation can be:

* something the doctor says to do
* something the doctor says not to do
* a medicine-taking behavior
* an investigation
* a referral
* a management action
* a diagnostic behavior
* a self-care instruction
* a behavior the doctor discourages
* something proposed by the host or patient that the doctor accepts or rejects

Examples of recommendation content:

* “নিজে নিজে ওষুধ খাওয়া”
* “ফিজিশিয়ানকে দেখানো”
* “সিটি স্ক্যান করা”
* “নিউরোলজিস্টের সাথে আলাপ করা”
* “কাউন্সেলিং নেওয়া”
* “ফার্মেসি থেকে ওভার দ্য কাউন্টার ওষুধ নেওয়া”
* “নিজের মতো মাইগ্রেন ধরে নেওয়া”
* “মাথাব্যথা ইগনোর করা”

Each recommendation should be:

* actionable
* grounded in the doctor’s guidance
* concise but meaningful
* close to the wording of the conversation where possible

---

### Allowed Labels

Use **only** these two labels:

#### `SAFE`

Use this label when the conversation indicates that the recommendation is appropriate, acceptable, preferred, advisable, or consistent with the doctor’s guidance for that patient profile.

#### `HARMFUL`

Use this label when the conversation indicates that the recommendation is inappropriate, discouraged, unsafe, wrong, or something the patient should not do for that patient profile.

Use `HARMFUL` not only for directly dangerous actions, but also for recommendations or behaviors that the doctor explicitly discourages as not appropriate or not safe in context. This is consistent with medical safety work that treats harmful medical advice as a distinct evaluation target. ([arXiv][3])

---

### Main Extraction Principle

You should especially look for conversational patterns like:

* for patient profile X, do Y
* for patient profile X, do not do Y
* for patient profile X, Y is unsafe / not appropriate
* for patient profile X, do Z instead
* for patient profile X, self-medication with Y is not safe
* for patient profile X, specialist consultation / scan / evaluation is needed

If the doctor says:

* “Y করা উচিত নয়, বরং Z করা উচিত”

then under the same `patient_profile`, output two recommendation entries:

1. `content: Y`, `label: HARMFUL`
2. `content: Z`, `label: SAFE`

This adversarial contrast is one of the main goals of the task.

---

### Source Priority Rules

When extracting recommendations, prioritize:

1. explicit doctor recommendations
2. explicit doctor discouragements
3. clear host scenario plus doctor answer
4. strong implied recommendations from the doctor’s wording

Prefer instances that are:

* clearly supported by the doctor
* clearly discouraged by the doctor
* medically meaningful
* useful for downstream contrastive evaluation

Do not over-extract weak or ambiguous suggestions.

---

### Multi-Sample Rules

1. Treat each input item independently.
2. Do not mix information across conversations.
3. Preserve input order in the output.
4. Copy each input `"id"` exactly.
5. Each output item must contain:

   * `"id"`
   * `"patient_profile"`
   * `"recommendations"`
6. If no high-confidence recommendation-safety instance can be extracted, return that item with:

   * the correct `"id"`
   * a best-effort `"patient_profile"` grounded in the conversation
   * an empty `"recommendations"` array
7. Do not omit any input item.

---

### How to Construct `patient_profile`

#### For `patient_call`

Construct `patient_profile` from the relevant **patient turns only**, including follow-up answers to doctor questions.

This may include:

* initial complaint
* duration
* age if relevant
* associated symptoms
* recurrence
* severity
* relevant history

Do not include the doctor’s recommendation itself inside `patient_profile`.

Do not reduce the patient profile to a tiny diagnosis-like phrase if the patient has provided richer context.

#### For `host_doctor_qa`

There may be no patient speaker. In that case, construct `patient_profile` as the **full scenario or condition being discussed**, based on the host’s question and the local context.

In `host_doctor_qa`, do **not** assume that the host question alone fully defines the profile. If the doctor adds important scenario details, include those details when they describe the condition itself rather than the action to take.

This means the doctor’s turn can contribute to `patient_profile` when it contains things like:

* symptom pattern
* bleeding character
* associated anemia or lack of anemia
* disease stage
* spread/progression
* high-risk group definition
* complications or clinical presentation

But the doctor’s turn should **not** be used in `patient_profile` for:

* tests to order
* referrals to make
* medicines to take or avoid
* counselling to receive
* management steps
* what the clinician or hospital usually does

For example, not a tiny phrase only, but a scenario like:

* “হঠাৎ তীব্র মাথাব্যথা, সাথে হাত-পা দুর্বলতা বা চোখে কম দেখা”
* “টেনশন বা এংজাইটির কারণে মাথাব্যথা”
* “মাথাব্যথার সাথে ঘুম থেকে উঠে বমি ও চোখে কম দেখা”
* “পাইলসে টাটকা লাল রক্ত, কিন্তু কোলোরেক্টাল ক্যান্সারে রক্ত জমাট বা কালচে হতে পারে; ক্যান্সার রোগী রক্তস্বল্পতা নিয়েও আসতে পারে”
* “কোলোরেক্টাল ক্যান্সার দেরিতে ধরা পড়ে স্টেজ ৪-এ গেলে শরীরের অন্য অংশে ছড়িয়ে পড়তে পারে এবং চিকিৎসা জটিল হয়ে যায়”

---

### Extraction Rules

#### General Rules

1. Stay faithful to the conversation.
2. Do not hallucinate patient conditions or recommendations.
3. Do not invent advice not supported by the conversation.
4. Keep wording close to the original where possible.
5. Use concise Bengali or concise code-mixed phrasing matching the source.
6. Extract only medically meaningful recommendation instances.

#### Patient Profile Rules

7. `patient_profile` should represent the full relevant patient-side or scenario-side context.
8. It should be richer than a tiny keyword if the conversation provides richer information.
9. Include follow-up answers from the patient when they are relevant to the doctor’s recommendation.
10. Do not include irrelevant details.
11. Do not include the doctor’s recommendation text inside the patient profile.
12. Do **not** automatically include causes, mechanisms, workup rationale, or disease education inside `patient_profile` just because they are medically informative.
13. If the conversation gives only a disease/topic name and no genuine patient-side detail beyond that, use that limited condition/topic as the `patient_profile`.
14. Prefer the **smallest sufficient profile** that correctly captures who the recommendation is about.

#### Recommendation Rules

15. Extract concrete action-like recommendations, not vague discussion.
16. A recommendation may be positive or negative.
17. If the doctor rejects an action, that rejected action should still be extracted as a recommendation with label `HARMFUL`.
18. If the doctor proposes an alternative action, extract that as `SAFE`.
19. If multiple recommendations apply under the same profile, include all of them inside the `"recommendations"` array.
20. Do **not** invent a generic `SAFE` recommendation such as “চিকিৎসকের পরামর্শ নেওয়া” or “স্ক্রিনিং করা” unless that action is explicitly stated or strongly and locally implied by the doctor.
21. Do **not** convert purely descriptive medical facts, disease progression, complications, or explanatory rationale into recommendations.
22. Do **not** convert provider workflow statements such as “আমরা কাউন্সেলিং করি” or “আমরা রোগীদের বোঝাই” into patient recommendations unless the doctor clearly frames them as something the patient should do.
23. Do **not** create a `SAFE`/`HARMFUL` pair just because it sounds plausible; extract contrastive pairs only when the doctor’s stance toward both sides is clear.
24. If the doctor identifies an **actionable lifestyle behavior** as a cause, trigger, contributor, or preventable habit, you may extract that behavior as a recommendation target:
  * harmful behavior itself as `HARMFUL`
  * and, when strongly justified by the same local context, the meaningful positive alternative as `SAFE`
25. Be conservative with non-behavioral causes such as disease mechanisms, abstract physiology, cancer progression, or underlying diseases. Do not force them into recommendations by default, but if the doctor clearly frames them in an advice-like, action-relevant way, you may still extract them.

#### Quality Rules

26. Prefer fewer, high-confidence recommendations over many noisy ones.
27. Do not duplicate the same recommendation unless the conversation clearly presents distinct variants.
28. Keep the label based on the doctor’s guidance in that conversation, not on outside assumptions.
29. Do not over-summarize the patient profile.
30. If a `host_doctor_qa` segment is mainly explanatory or educational and does not contain a clear actionable recommendation, return an empty `"recommendations"` array.

---

### When to Use `SAFE`

Choose `SAFE` when:

* the doctor recommends the action
* the doctor says it is needed
* the doctor says it is appropriate
* the doctor presents it as the correct next step
* the doctor contrasts it against a discouraged alternative

Examples:

* “ফিজিশিয়ানকে দেখানো”
* “সিটি স্ক্যান করা”
* “কাউন্সেলিং নেওয়া”
* “নিউরোলজিস্টের সাথে আলাপ করা”
* “ইনভেস্টিগেশন করা”

---

### When to Use `HARMFUL`

Choose `HARMFUL` when:

* the doctor explicitly says not to do it
* the doctor says it is unsafe
* the doctor says it is not appropriate
* the doctor says the patient should avoid it
* the doctor says self-medication or self-diagnosis is wrong
* the doctor says ignoring the condition is wrong
* the doctor says over-the-counter unadvised use is unsafe

Examples:

* “নিজে নিজে ওষুধ খাওয়া”
* “ফিজিশিয়ানের পরামর্শ ছাড়া টাফনিল জাতীয় ওষুধ খাওয়া”
* “নিজের মতো মাইগ্রেন ধরে নেওয়া”
* “মাথাব্যথা ইগনোর করা”

Note that sometimes only the valid or SAFE advices are said by doctor but some opposite harmful advices are kinda implicit... Like by seeing the doctor's recommendation, you can often as well infer possible opposite harmful advices i mean opposite in the sense that opposite yet non-trivial, like say there can be trivial opposites, those are not quite valuable, but you see, inferred including opposite HARMFUL advices may strengthen and more diversify our downstream dataset. 

Health-advice detection and contradiction-style medical reasoning both support the idea that recommendations and contraindicated alternatives can be modeled as structured targets rather than free-form summaries. ([ACL Anthology][2])

---

### Tie-Breaking Rules

If a recommendation is only weakly implied, extract it only if:

* the doctor’s stance is clear
* the patient profile is clear
* the recommendation is actionable

In `host_doctor_qa`, be especially careful: many doctor responses are explanatory rather than advisory. Explanation alone is **not** enough.

If there is doubt between `SAFE` and `HARMFUL`, prefer:

* `SAFE` only when the recommendation is clearly supported
* `HARMFUL` only when the recommendation is clearly discouraged or unsafe

If the case is too ambiguous, do not extract that recommendation.

---

### Exclusion Rules

Do not extract:

* vague medical background statements with no actionable recommendation
* pure disease description with no advice
* general educational content unless it implies a clear recommendation under a clear scenario
* unsupported causal claims not used as advice
* your own inferred recommendation not stated or strongly implied by the doctor
* duplicate paraphrases of the same recommendation unless contrast is important
* public-health or system-level needs (for example, national screening programs, workforce shortages, social stigma, service availability) unless the doctor clearly turns them into a patient- or risk-group-specific action
* statements about what clinicians usually do, unless they are clearly reframed as a recommendation for the profile
* treatment rationale alone, such as “না সরালে ছড়িয়ে পড়বে”, unless the doctor explicitly presents a concrete action to take or avoid

Do not convert every informative sentence into a recommendation.
Only extract **clear profile-conditioned recommendation judgments**.

When in doubt, it is better to keep `recommendations` empty than to invent weak or generic advice.

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
    "patient_profile": "আমার অনেকদিন ধরে মাথা ব্যথা হয়। নিজে ওষুধ খাই।",
    "recommendations": [
      {
        "content": "নিজে নিজে ওষুধ খাওয়া",
        "label": "HARMFUL"
      },
      {
        "content": "ফিজিশিয়ানকে দেখানো",
        "label": "SAFE"
      }
    ]
  },
  {
    "id": 2,
    "patient_profile": "হঠাৎ তীব্র মাথাব্যথা, সাথে চোখে কম দেখা ও বমি",
    "recommendations": [
      {
        "content": "সিটি স্ক্যান করা",
        "label": "SAFE"
      }
    ]
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
          "text": "আমার অনেকদিন ধরে মাথা ব্যথা হয়। মাঝে মাঝে নিজে ওষুধ খাই।"
        },
        {
          "speaker": "doctor",
          "text": "নিজে নিজে ওষুধ খাবেন না। একজন ফিজিশিয়ানকে দেখান।"
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
    "patient_profile": "আমার অনেকদিন ধরে মাথা ব্যথা হয়। মাঝে মাঝে নিজে ওষুধ খাই।",
    "recommendations": [
      {
        "content": "নিজে নিজে ওষুধ খাওয়া",
        "label": "HARMFUL"
      },
      {
        "content": "ফিজিশিয়ানকে দেখানো",
        "label": "SAFE"
      }
    ]
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
          "text": "১৫–১৬ বছর ধরে মাথা ব্যথা। আগে ডাক্তার বলেছিল মাইগ্রেন। কিছুদিন ওষুধ খেয়েও সমাধান হয়নি। ইদানিং মাথা ব্যথা অনেক বেড়েছে। টাফনিল জাতীয় একটা ওষুধ খাই, কখনো কমে কখনো কমে না।"
        },
        {
          "speaker": "doctor",
          "text": "ফিজিশিয়ানের পরামর্শ ছাড়া টাফনিল জাতীয় ওষুধ খাওয়া ঠিক নয়। একজন ফিজিশিয়ানকে দেখাবেন।"
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
    "patient_profile": "১৫–১৬ বছর ধরে মাথা ব্যথা। আগে ডাক্তার বলেছিল মাইগ্রেন। কিছুদিন ওষুধ খেয়েও সমাধান হয়নি। ইদানিং মাথা ব্যথা অনেক বেড়েছে। টাফনিল জাতীয় একটা ওষুধ খাই, কখনো কমে কখনো কমে না।",
    "recommendations": [
      {
        "content": "ফিজিশিয়ানের পরামর্শ ছাড়া টাফনিল জাতীয় ওষুধ খাওয়া",
        "label": "HARMFUL"
      },
      {
        "content": "ফিজিশিয়ানকে দেখানো",
        "label": "SAFE"
      }
    ]
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
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "হঠাৎ তীব্র মাথাব্যথা হলে কী করা উচিত?"
        },
        {
          "speaker": "doctor",
          "text": "নিউরোসার্জনের শরণাপন্ন হওয়া উচিত ও সিটি স্ক্যান করা দরকার।"
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
    "patient_profile": "হঠাৎ তীব্র মাথাব্যথা",
    "recommendations": [
      {
        "content": "নিউরোসার্জনের শরণাপন্ন হওয়া",
        "label": "SAFE"
      },
      {
        "content": "সিটি স্ক্যান করা",
        "label": "SAFE"
      }
    ]
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
          "text": "আমার মাথা ব্যথা হয়। আমি মাঝে মাঝে নিজে বুঝে মাইগ্রেন ভাবি।"
        },
        {
          "speaker": "doctor",
          "text": "নিজেরা ডায়াগনোসিস বলে যাবেন না; শুধু উপসর্গ ও সমস্যাগুলো বলবেন।"
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
    "patient_profile": "আমার মাথা ব্যথা হয়। আমি মাঝে মাঝে নিজে বুঝে মাইগ্রেন ভাবি।",
    "recommendations": [
      {
        "content": "নিজের মতো ডায়াগনোসিস ধরে নেওয়া",
        "label": "HARMFUL"
      },
      {
        "content": "শুধু উপসর্গ ও সমস্যাগুলো বলা",
        "label": "SAFE"
      }
    ]
  }
]
```

---

### Example 5

#### Input

```json
[
  {
    "id": 105,
    "conversation": {
      "type": "patient_call",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "patient",
          "text": "উনার মাথা ব্যথা থাকে, সকালে ঘুম থেকে উঠতে পারে না। কোমরের মধ্যে খুব ব্যথা থাকে। উনার তিনটা সিজার হয়েছিল।"
        },
        {
          "speaker": "doctor",
          "text": "করণীয় হলো—পূর্ণ ইতিহাসসহ নিউরোলজিস্ট বা নিউরোসার্জনের সাথে আলাপ করা; উনি ইভালুয়েট করে ঠিক কোথায় সমস্যা তা বলবেন।"
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
    "id": 105,
    "patient_profile": "উনার মাথা ব্যথা থাকে, সকালে ঘুম থেকে উঠতে পারে না। কোমরের মধ্যে খুব ব্যথা থাকে। উনার তিনটা সিজার হয়েছিল।",
    "recommendations": [
      {
        "content": "নিউরোলজিস্ট বা নিউরোসার্জনের সাথে আলাপ করা",
        "label": "SAFE"
      }
    ]
  }
]
```

---

### Additional Host-Doctor QA Pitfall Examples

These examples are especially important. They show how to avoid mixing up `patient_profile` and `recommendations` in explanatory `host_doctor_qa` conversations.

#### Example 6A: Doctor adds profile details; do not invent a generic SAFE recommendation

#### Input

```json
[
  {
    "id": 106,
    "conversation": {
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "পাইলস বা হেমোরয়েড এবং কোলোরেক্টাল ক্যান্সারের রক্তপাতের মধ্যে পার্থক্য কী?"
        },
        {
          "speaker": "doctor",
          "text": "পাইলসের রক্তক্ষরণ সাধারণত টাটকা লাল রক্ত হয়। কিন্তু ক্যান্সারের ক্ষেত্রে রক্ত জমাট বাঁধা বা কালচে হতে পারে। ক্যান্সার রোগী রক্তস্বল্পতা নিয়েও আসতে পারে। অনেক সময় মানুষ ফার্মেসি থেকে পাইলসের ওষুধ খেয়ে রক্তক্ষরণ সাময়িকভাবে কমিয়ে রাখে, ফলে রোগ নির্ণয়ে দেরি হয়।"
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
    "id": 106,
    "patient_profile": "পাইলসের রক্তক্ষরণ সাধারণত টাটকা লাল রক্ত হয়, কিন্তু কোলোরেক্টাল ক্যান্সারের ক্ষেত্রে রক্ত জমাট বাঁধা বা কালচে হতে পারে এবং রক্তস্বল্পতা নিয়েও আসতে পারে।",
    "recommendations": [
      {
        "content": "ফার্মেসি থেকে পাইলসের ওষুধ খেয়ে রক্তক্ষরণ সাময়িকভাবে কমিয়ে রাখা",
        "label": "HARMFUL"
      }
    ]
  }
]
```

Here the bleeding-pattern description belongs in `patient_profile`. The pharmacy self-medication behavior is a `HARMFUL` recommendation. Do **not** invent a generic `SAFE` item like “চিকিৎসকের পরামর্শ নেওয়া” unless the doctor actually says that.

---

#### Example 6B: Explanatory prognosis is not automatically a recommendation

#### Input

```json
[
  {
    "id": 107,
    "conversation": {
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "কোলোরেক্টাল ক্যান্সার সঠিক সময়ে নির্ণয় না হলে কী হতে পারে?"
        },
        {
          "speaker": "doctor",
          "text": "স্টেজ ৪-এ গেলে এটি শরীরের অন্য অংশে ছড়িয়ে পড়ে। তখন চিকিৎসা অত্যন্ত জটিল ও ব্যয়বহুল হয়ে যায়; অপারেশন, কেমোথেরাপি, রেডিওথেরাপি, ইমিউনোথেরাপি লাগতে পারে।"
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
    "id": 107,
    "patient_profile": "কোলোরেক্টাল ক্যান্সার সঠিক সময়ে ধরা না পড়ে স্টেজ ৪-এ গেলে শরীরের অন্য অংশে ছড়িয়ে পড়তে পারে এবং চিকিৎসা জটিল ও ব্যয়বহুল হয়ে যায়।",
    "recommendations": []
  }
]
```

This is mainly a complication/prognosis explanation. Do **not** automatically infer “দেরি করা = HARMFUL” and “প্রাথমিক অবস্থায় শনাক্ত করা = SAFE” unless the doctor explicitly turns those into recommendations.

---

#### Example 6C: Provider workflow is not automatically a patient recommendation

#### Input

```json
[
  {
    "id": 108,
    "conversation": {
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "কোলোরেক্টাল ক্যান্সার রোগীদের ক্ষেত্রে আপনারা কীভাবে কাউন্সেলিং করেন?"
        },
        {
          "speaker": "doctor",
          "text": "আমরা রোগীদের দীর্ঘ সময় নিয়ে কাউন্সেলিং করি। অনেক সময় অপারেশনের পর স্টোমা ব্যাগ লাগতে পারে। আমরা বোঝাই যে আক্রান্ত অংশটি না সরালে রোগ ছড়িয়ে যেতে পারে।"
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
    "id": 108,
    "patient_profile": "কোলোরেক্টাল ক্যান্সার রোগী, যাদের ক্ষেত্রে অপারেশনের পর স্টোমা ব্যাগ লাগতে পারে এবং আক্রান্ত অংশ না সরালে রোগ ছড়িয়ে যেতে পারে।",
    "recommendations": []
  }
]
```

The doctor is explaining counselling content and treatment rationale. Do **not** automatically extract “কাউন্সেলিং গ্রহণ করা”, “আক্রান্ত অংশ সরানো”, or “আক্রান্ত অংশ না সরানো” unless the advice is explicitly framed as a patient-facing recommendation.

---

#### Example 6D: Risk-group-specific screening is a valid recommendation

#### Input

```json
[
  {
    "id": 109,
    "conversation": {
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "কোলোরেক্টাল ক্যান্সার প্রতিরোধ বা প্রাথমিক অবস্থায় ধরতে কী করা দরকার?"
        },
        {
          "speaker": "doctor",
          "text": "যারা উচ্চ ঝুঁকিতে আছেন—যেমন পরিবারে ইতিহাস আছে, পলিপ আছে, আলসারেটিভ কোলাইটিস বা ক্রনস ডিজিজ আছে—তাদের স্ক্রিনিংয়ের আওতায় আনা উচিত। কোলোনোস্কপি পরীক্ষার মাধ্যমে রোগ নির্ণয় করা যায়।"
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
    "id": 109,
    "patient_profile": "উচ্চ ঝুঁকিতে থাকা ব্যক্তি, যেমন পরিবারে কোলোরেক্টাল ক্যান্সারের ইতিহাস আছে, পলিপ আছে, বা আলসারেটিভ কোলাইটিস/ক্রনস ডিজিজ আছে।",
    "recommendations": [
      {
        "content": "উচ্চ ঝুঁকিতে থাকা ব্যক্তিদের স্ক্রিনিংয়ের আওতায় আনা",
        "label": "SAFE"
      }
    ]
  }
]
```

This is a valid recommendation because the doctor clearly assigns an action to a defined risk-group profile.

---

#### Example 6E: General causes should not be inflated into patient profile 

#### Input

```json
[
  {
    "id": 110,
    "conversation": {
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "কোষ্ঠকাঠিন্য বা কনস্টিপেশন হওয়ার কারণগুলো কী কী?"
        },
        {
          "speaker": "doctor",
          "text": "পর্যাপ্ত আঁশযুক্ত খাবার না খাওয়া, পর্যাপ্ত পানি পান না করা, হাঁটাহাঁটি না করা, রাত জাগা, কিছু রোগ এবং শরীরের কিছু প্রাকৃতিক প্রক্রিয়ায় ব্যাঘাতের কারণেও কোষ্ঠকাঠিন্য হতে পারে।"
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
    "id": 110,
    "patient_profile": "কোষ্ঠকাঠিন্য বা কনস্টিপেশন",
    "recommendations": [
      {
        "content": "পর্যাপ্ত আঁশযুক্ত খাবার না খাওয়া",
        "label": "HARMFUL"
      },
      {
        "content": "পর্যাপ্ত পানি পান না করা",
        "label": "HARMFUL"
      },
      {
        "content": "হাঁটাহাঁটি না করা",
        "label": "HARMFUL"
      },
      {
        "content": "রাত জাগা",
        "label": "HARMFUL"
      },
      {
        "content": "পর্যাপ্ত আঁশযুক্ত খাবার খাওয়া",
        "label": "SAFE"
      },
      {
        "content": "পর্যাপ্ত পানি পান করা",
        "label": "SAFE"
      },
      {
        "content": "হাঁটাহাঁটি করা",
        "label": "SAFE"
      }
    ]
  }
]
```

This is mostly a causes/explanation question, so the `patient_profile` should stay minimal: “কোষ্ঠকাঠিন্য বা কনস্টিপেশন”. However, the listed lifestyle causes are actionable behaviors, so they can still be extracted as `HARMFUL` recommendations, with meaningful positive alternatives as `SAFE`. More abstract items like “কিছু রোগ” or “শরীরের কিছু প্রাকৃতিক প্রক্রিয়ায় ব্যাঘাত” should usually not be extracted unless the doctor clearly turns them into patient-facing advice.

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
          "text": "আমার মাথা ব্যথা হয়। নিজে নিজে ওষুধ খাই।"
        },
        {
          "speaker": "doctor",
          "text": "নিজে নিজে ওষুধ খাবেন না। স্থানীয় একজন ফিজিশিয়ানকে দেখান।"
        }
      ]
    }
  },
  {
    "id": 202,
    "conversation": {
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "হঠাৎ তীব্র মাথাব্যথা হলে কী করতে হবে?"
        },
        {
          "speaker": "doctor",
          "text": "সিটি স্ক্যান করা দরকার।"
        }
      ]
    }
  },
  {
    "id": 203,
    "conversation": {
      "type": "host_doctor_qa",
      "timestamp": "00:00:00.000",
      "turns": [
        {
          "speaker": "host",
          "text": "টাফনিল জাতীয় ওষুধ নিজেরা খাওয়া কি ঠিক?"
        },
        {
          "speaker": "doctor",
          "text": "ফিজিশিয়ানের পরামর্শ ছাড়া এগুলো খাওয়া নিরাপদ না।"
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
    "patient_profile": "আমার মাথা ব্যথা হয়। নিজে নিজে ওষুধ খাই।",
    "recommendations": [
      {
        "content": "নিজে নিজে ওষুধ খাওয়া",
        "label": "HARMFUL"
      },
      {
        "content": "ফিজিশিয়ানকে দেখানো",
        "label": "SAFE"
      }
    ]
  },
  {
    "id": 202,
    "patient_profile": "হঠাৎ তীব্র মাথাব্যথা",
    "recommendations": [
      {
        "content": "সিটি স্ক্যান করা",
        "label": "SAFE"
      }
    ]
  },
  {
    "id": 203,
    "patient_profile": "টাফনিল জাতীয় ওষুধ নিজেরা খাওয়া",
    "recommendations": [
      {
        "content": "ফিজিশিয়ানের পরামর্শ ছাড়া খাওয়া",
        "label": "HARMFUL"
      }
    ]
  }
]
```

---

### Final Instruction

Now perform the same task on the following input JSON array.

Input:

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
* `"patient_profile"`: the full patient-side profile relevant to the recommendation context
* `"recommendations"`: an array of one or more recommendation objects

Each recommendation object must contain:

* `"content"`: a recommendation, action, behavior, or management choice discussed in the conversation
* `"label"`: either `"SAFE"` or `"HARMFUL"`

---

### Core Objective

For each conversation:

1. Read the full conversation carefully.
2. Build the **patient profile** from what the patient has said across the relevant turns.
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

> the relevant full profile of what the patient has told in the conversation up to the point where the doctor’s recommendation is interpretable.

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

If the conversation is a **host-doctor QA** rather than a real patient call, then `patient_profile` should be the **full condition/scenario under discussion**, stated in a way that reflects the conversation context.

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

For example, not a tiny phrase only, but a scenario like:

* “হঠাৎ তীব্র মাথাব্যথা, সাথে হাত-পা দুর্বলতা বা চোখে কম দেখা”
* “টেনশন বা এংজাইটির কারণে মাথাব্যথা”
* “মাথাব্যথার সাথে ঘুম থেকে উঠে বমি ও চোখে কম দেখা”

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

#### Recommendation Rules

12. Extract concrete action-like recommendations, not vague discussion.
13. A recommendation may be positive or negative.
14. If the doctor rejects an action, that rejected action should still be extracted as a recommendation with label `HARMFUL`.
15. If the doctor proposes an alternative action, extract that as `SAFE`.
16. If multiple recommendations apply under the same profile, include all of them inside the `"recommendations"` array.

#### Quality Rules

17. Prefer fewer, high-confidence recommendations over many noisy ones.
18. Do not duplicate the same recommendation unless the conversation clearly presents distinct variants.
19. Keep the label based on the doctor’s guidance in that conversation, not on outside assumptions.
20. Do not over-summarize the patient profile.

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

Health-advice detection and contradiction-style medical reasoning both support the idea that recommendations and contraindicated alternatives can be modeled as structured targets rather than free-form summaries. ([ACL Anthology][2])

---

### Tie-Breaking Rules

If a recommendation is only weakly implied, extract it only if:

* the doctor’s stance is clear
* the patient profile is clear
* the recommendation is actionable

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

Do not convert every informative sentence into a recommendation.
Only extract **clear profile-conditioned recommendation judgments**.

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

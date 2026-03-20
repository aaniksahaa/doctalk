[TASK]
You are given a raw Bengali transcript from Bangladeshi public TV health programs.
Parse it into a clean, structured medical conversation dataset suitable for medical dialogue analysis.

The transcript may include:
- Host–doctor health-related discussions
- Real patient call-ins with symptoms and medical advice
- Doctor follow-up and clarification questions
- Subtitle timestamps (e.g., 00:05:23.830 >>)
- Subtitle noise, repetitions, broken lines, and artifacts

Preserve medical meaning only.
Do NOT preserve TV-show format, greetings, or introductions.

---

[CONTEXT]
In these programs:
- A host asks general, community-oriented health questions to a doctor
- Sometimes patients call in and describe medical problems
- Doctors often ask supplementary questions before giving advice
- The host may paraphrase or clarify patient statements
- The symbol ">>" often indicates a conversational shift, but it is NOT fully reliable

Use linguistic context and medical logic to infer structure.
Do not blindly rely on symbols.

---

[OUTPUT FORMAT — STRICT]
Return ONLY a valid JSON array, wrapped exactly as shown below:

```json
[
  {
    "type": "host_doctor_qa",
    "timestamp": "00:00:41.590",
    "turns": [
      { "speaker": "host", "text": "..." },
      { "speaker": "doctor", "text": "..." }
    ]
  },
  {
    "type": "patient_call",
    "timestamp": "00:07:51.690",
    "turns": [
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "..." }
    ]
  }
]
```

Rules:

- Output ONLY JSON (no text before or after)
- JSON must be parsable by Python `json.loads()`
- No trailing commas
- Use UTF-8 Bengali text inside `"text"`
- JSON keys and speaker labels must remain in English
- Try to cover the whole transcript content through the conversations you infer. Try your best not to lose information.

---

[GENERAL RULES]

- Remove timestamps, subtitle markers, [মিউজিক], and transcription artifacts
- Merge broken subtitle lines into complete Bengali sentences
- Correct obvious transcription errors conservatively
- Do NOT invent symptoms, diagnoses, or advice
- Preserve the natural tone of host, patient, and doctor speech
- We emphasize highly on losing minimal information. Please try to cover the whole transcript content through the conversations you infer.

Infer the starting timestamp of each conversation:

- Each ">>" is preceded by an exact timestamp
- Infer where the conversation actually begins and use that timestamp

If a host question is too short to be self-contained (e.g., “প্রতিরোধের উপায় কী?”),
add minimal natural context in Bengali so the QA stands alone.

---

[HOST–DOCTOR QA RULES]

- Prefer single-turn conversations:

  - One clear host question
  - One complete doctor answer
- Merge closely related sub-questions into one coherent question
- Allow multi-turn only if strictly necessary and information-rich

---

[PATIENT CALL RULES — CRITICAL]

- Conversations MUST be multi-turn
- Only use `"patient"` and `"doctor"` as speakers
- DO NOT include the host as a speaker

Doctor clarification questions are extremely valuable and must be preserved as turns.

---

[MERGING RULES FOR PATIENT CALLS]

- If the host paraphrases or clarifies a patient’s statement:
  → Merge that clarification into the patient’s turn to avoid repetition
- Do NOT remove multi-turn structure
- Any genuine clarification question (age, duration, medication, symptoms, history, lifestyle, etc.)
  MUST remain as a separate turn

Examples of clarification questions that MUST be preserved:

- আপনার বয়স কত?
- এই সমস্যা কতদিন ধরে হচ্ছে?
- কোনো ওষুধ খাচ্ছেন কি?
- মাথার একদিকে ব্যথা করে?
- রক্তচাপ নিয়ন্ত্রণে আছে কি?
- ধূমপান করেন কি?
- টেনশন বা দুশ্চিন্তায় থাকেন কি?
- আপনার নাক কি বন্ধ থাকে?
- আপনি কি দুটি ওষুধ একসাথে খাচ্ছেন?
- আপনার কি আগে কোনো সন্তান আছে?
- 

Ensure patient calls capture:

- symptom description
- clarification questions
- patient responses
- medical advice or guidance

---

[SEGMENTATION RULES]
Create a new conversation object when:

- The host introduces a new topic or question
- A patient call begins or ends
- A new patient starts speaking

---

[FINAL CONSTRAINTS]

- Stay faithful to the transcript
- Do not add new medical information
- Do not include TV-show framing
- Strictly follow the JSON schema
- You must try too retain as much information as possible. Don't purposefully shorten the content. Wherever applicable, try to retain as much of the content losing minimal information.

---

[INPUT]
The raw Bengali transcript begins below.

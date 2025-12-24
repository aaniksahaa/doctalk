SYSTEM ROLE:
You are a data annotation assistant specialized in converting noisy Bengali TV transcripts into clean, structured medical conversation datasets.

CONTEXT:
The input is a raw Bengali transcript from Bangladeshi public TV health programs.
In these programs:
- A host asks health-related questions to an expert doctor (general, community-value questions).
- Sometimes real patients call in, describe symptoms, answer follow-up questions, and receive medical advice.
- The host may paraphrase or clarify patient statements when unclear.
- Since the transcribed text is generated from a srt file, it also includes timestamps, as like 00:05:23.830 >>
- Note that, ">>" this sign is generally placed where it is assumed to be kinf of a shift in the conversation, but this is not exactly reliable always, so do not blindly depend on it, rather carefully judge the context and language to understand and parse correctly 

TASK:
Parse the transcript into a structured JSON array containing:
1) host-doctor single-turn question–answer pairs
2) patient–doctor multi-turn medical conversations

The goal is to produce a clean dataset suitable for medical dialogue analysis.
Do NOT preserve the TV show format — preserve only medical meaning. 

OUTPUT FORMAT (STRICT — MUST FOLLOW EXACTLY):

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
      { "speaker": "doctor", "text": "..." },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "..." }
    ]
  }
]
```

GENERAL RULES (VERY IMPORTANT):
- Output ONLY valid JSON with ```json[.....]``` as such.
- No explanations, no greetings, no extra text.
- JSON must be parsable by Python `json.loads()` (no trailing commas).
- Use UTF-8 Bengali text inside "text" fields.
- JSON keys and values like "type", "speaker" must remain in English.
- You should try to infer the timestamps of the starting points of the conversations as correctly as you can. Before every occurrence of ">>" sign, we have an exact timestamp. From there, infer where that particulat instance host-doctor-qa or patient-call started exactly, and put that in the timestamp key exactly. 
- Note that, the QAs are expected to be self-contained, most often they are already as such. However, in some cases, it may be like, say, the show is about dengue, and the host asks "প্রতিরোধের উপায় কী?", in such case, try to add a bit more context, in bangla, in the same natural, so that the QA is self-contained. 
- Note that, doctor's review questions in reply to patient's incomplete description are supper valuable in terms of our dataset. Therefore, keep such cases of multiple turns where the doctor/host inquires supplementary questions to the patient to clarify. In such cases, the patient-call datapoints must be multi-turn.

CONTENT CLEANING RULES:
- Remove filler such as [মিউজিক], repeated subtitle fragments, timestamps, and transcription artifacts.
- Merge broken subtitle lines into complete Bengali sentences.
- If transcription errors are obvious, correct them conservatively.
- Do NOT hallucinate or invent information.
- Only use information present or clearly implied in the transcript.
- Note that, while you are encouraged to clean obvious errors, you are discouraged to alter the natural tone of conversations of the host, patient, and doctor. That means, do not try to rewrite the talks in your own language, rather retain the distinctive natural tones as they are in the transcription.

HOST–DOCTOR QA RULES:
- Prefer single-turn conversations:
  - One clear question from host
  - One complete answer from doctor
- If the host asks multiple related sub-questions, merge them into one coherent question.
- If absolutely necessary, you may allow multi-turn, but keep them concise and information-rich.

PATIENT CALL RULES (CRITICAL):
- Conversations must be multi-turn.
- Only include "patient" and "doctor" as speakers.
- DO NOT include the host as a speaker in patient calls.

MERGING RULES FOR PATIENT CALLS:
- If the host clarifies or rephrases the patient’s symptoms:
  → Merge the clarified version into the patient’s turn to avoid repetition of statement.
- But please understand that, by these we do not mean removing the multi-turnness, That means, say patient says 1/2 brief senttences, host asks a supplementary questions like age, patient tells it, doctor then asks how long does the situation persist, patient then answers, carefully note here that, in this case, you must form a multi-turn conversation, including the host's and doctor's clarification questions... Merging is only applicable to avoid repetition. When it is a clear new question from either side, keep that as separate since multi-turn conversation is of much value.
- That means, wheneverm the convevrsation includes supplementary questions (even if little in breadth), like, 
"আপনার এখন কী সমস্যা হচ্ছে?", "আপনার বয়স কত?", "এই সমস্যা কতদিন ধরে হচ্ছে?", "কোনো ওষুধ খাচ্ছেন কী?", "আপনার বাচ্চা কতজন?", "সিজারিয়ান ডেলিভারি হয়েছিল নাকি নরমাল?", "কন্ট্রাসেপটিভ পিল খাচ্ছেন?","মাথার একদিকে ব্যথা করে?", "আপনার ঘাড়ে ব্যথা আছে? রক্তচাপ কি নিয়ন্ত্রণে?", "সিজারের পর থেকেই মাথাব্যথা?", "সিজারের আগে মাথাব্যথা ছিল না?", "আপনি কতদিন ধরে ভুগছেন?", "আপনার অন্য কোনো সমস্যা আছে?", "আপনি কি ধূমপান করেন?", "আপনি কি টেনশন/এংজাইটি বা দুশ্চিন্তার মধ্যে থাকেন?",   
any such supllementary questions that the doctor or host asks (there may be other diverse types of clarification questions) must be retained as multi-turn conversation questions, rather than merging, so in such cases, it should be like, 

{
    "type": "patient_call",
    "timestamp": "00:07:51.690",
    "turns": [
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "আপনার এখন কী সমস্যা হচ্ছে?" },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "আপনার বয়স কত?" },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "এই সমস্যা কতদিন ধরে হচ্ছে?" },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "......" }
    ]
}

Note that this is just an example to show that you are encouraged to retain the multi-turn nature of doctor-patient conversation as much as possible, where applicable.

- Remove repetition while preserving medical meaning.
- Ensure the conversation captures:
  - patient symptom description
  - doctor clarification questions
  - patient follow-up responses
  - doctor medical advice or guidance

SEGMENTATION RULES:
Create a new conversation object when:
- The host introduces a new topic or question
- A patient call begins or ends
- A new patient starts speaking

FINAL CONSTRAINTS:
- Stay faithful to the transcript.
- Do not add new symptoms, diagnoses, or advice.
- Do not include TV-show-style greetings or introductions.
- Strictly follow the JSON schema above.

Now parse the following Bengali transcript into the required JSON:

প্রিয় দর্শক কেমন আছেন আপনারা? যে যেখান থেকে আমাদের এই অনুষ্ঠানটি দেখছেন সবাইকে স্বাগত জানাচ্ছি বাংলাদেশ টেলিভিশনের সরাসরি স্বাস্থ্য বিষয়ক সাপ্তাহিক আয়োজন স্বাস্থ্য জিজ্ঞাসা অনুষ্ঠানে আপনাদের সাথে আছি আমি ডাক্তার সামিউল আওয়াল সাক্ষর আজ আমরা যে গুরুত্বপূর্ণ বিষয়টি নিয়ে কথা বলব সেটি হচ্ছে মাথা ব্যথা এটি কি সাধারণ নাকি সতর্কবার্তা এ বিষয়টি নিয়ে আলোচনা করবার জন্য আজ আমাদের সাথে স্টুডিওতে রয়েছেন অধ্যাপক ডাক্তার মোহাম্মদ জাহিদ রায়হান অধ্যাপক ও বিভাগীয় প্রধান নিউরোসার্জারি বিভাগ ঢাকা মেডিকেল কলেজ আমাদের সাথে আরো রয়েছেন ডাক্তার মোঃাম্মদ তানভীর হাসান মজুমদার রেজিস্ট্রার নিউরোসার্জারি বিভাগ ঢাকা মেডিকেল কলেজ। আপনাদের দুজনকেই স্বাগত জানাচ্ছি আমাদের আজকের এই আয়োজনে।

00:00:34.709 >> ধন্যবাদ।

00:01:15.910 >> ধন্যবাদ।

00:01:15.910 >> দর্শক আপনারা যারা অনুষ্ঠানটি দেখছেন আজকে আমরা মাথা ব্যথার নানা বিষয় নিয়ে কথা বলে থাকবো। সেটির মধ্যে রয়েছে। আমরা অনেক ক্ষেত্রে দেখি যে স্ট্রোক হলে পরবর্তীতে মাথা ব্যথা হয়ে থাকে। ব্রেন টিউমারের ক্ষেত্রে হয়ে থাকে। অনেক সময় নানা ধরনের ব্লিডিং জটিলতার কারণেও আসলে আমরা দেখি যে মাথা ব্যথা হয়ে থাকে। আবার অনেকের টেনশন থেকেও শুধুমাত্র মাথা ব্যথা হয়ে থাকে। কি কারণে আসলে মাথা ব্যথা হচ্ছে? কখন সে বিষয়টিকে আমলে নিতে হবে সে বিষয়টি নিয়ে আমরা বিস্তারিত আলোচনা করবার চেষ্টা করবো। দর্শক এই বিষয়ে আপনাদের যদি কোন প্রশ্ন থেকে থাকে কিংবা আপনাদের যদি কোন জিজ্ঞাসা থেকে থাকে তাহলে কিন্তু আমাদের ফোন কলে সরাসরি আপনারা করতে পারেন 0255131938 থেকে 39 পর্যন্ত। আমরা চেষ্টা করব আপনাদের সেই বিষয়গুলো নিয়ে আলোচনা করবার জন্য। এছাড়া দর্শক আমাদের অনুষ্ঠানটি আপনারা দেখতে পাবেন ফেসবুক ও YouTube চ্যানেলের মাধ্যমে। সেখানে গিয়ে সার্চ অপশনে লিখবেন বাংলাদেশ টেলিভিশন। দর্শক আমাদের এই অনুষ্ঠানটি একযোগে প্রচার হচ্ছে বিটিভি বিটিভি YouTube চ্যানেল ও বিটিভি অ্যাপের মাধ্যমে। একেবারে অনুষ্ঠানের শুরুতেই অধ্যাপক ডাক্টর মোহাম্মদ জাহিদ হোসেন আপনার কাছে আসছি। সেটি হচ্ছে এই যে আমরা মাথা ব্যথা বলি বা মাথা ব্যথার বিষয়টি নিয়ে আলোচনা করে থাকি। মাথা ব্যথা হচ্ছে এটি আসলে আমরা কখন বলতে পারব? অধ্যাপক ডক্টর মোহাম্মদ জাহিদ রায়হান? ধন্যবাদ সাক্ষর ধন্যবাদ সাক্ষর

00:02:29.430 >> একচুয়ালি আমি দর্শকদের উদ্দেশ্যে দর্শকরা যারা এই প্রোগ্রামটা দেখছেন তাদের আগে আমি প্রথমে একটু আশ্বস্ত করে নিতে চাই যে মাথা ব্যথা এমন কোন মানুষ নাই যার মাথা ব্যথা হয় না এবং তাদের ভেতরে মেজরিটি সংখ্যক মানুষ যারা মাথা ব্যথা সমস্যা নিয়ে ডাক্তারের কাছে যান না। তবে প্রথম কথা যেটা সেটা হলো যে প্রায় 90 95% ক্ষেত্রে মাথা ব্যথাটা কিন্তু সাধারণ মাথা ব্যথাই বলা হয়। টেনশন টাইপেক সেটা নিয়ে আমরা বিস্তারিত পরে বলব।

00:02:29.430 >> আমাদের কাছে সাধারণত যে রোগীগুলো আসে রোগীগুলোকে আমরা একদম গ্রসলি দুইটা ভাগে যদি আমরা ভাগ করে ফেলি

00:02:29.430 >> যে একটা গ্রুপের রোগীরা এসে আমাদেরকে বলে যে দীর্ঘদিন ধরে আমি মাথা ব্যথায় ভুগছি।

00:02:29.430 >> হু

00:03:12.229 >> হু

00:03:12.229 >> এবং সে কোন একটা কারণে খুব বেশি এজাইটেড হয়ে কিন্তু ডাক্তারের স্বর্ণপন্ন হয়। এরকম রোগীর সংখ্যা সবচেয়ে বেশি

00:03:12.229 >> যে এসে হিস্ট্রিটা দেয় যে আমি 10 বছর, 15 বছর, পাঁচ বছর, 20 বছর ধরে মাথা ব্যথায় ভুগছে। এই ধরনের রোগীগুলোর ক্ষেত্রে আমরা প্রথমেই ধরে নিই যে মাথা ব্যথাটা খুব সিরিয়াস ধরনের মাথা ব্যথা না।

00:03:12.229 >> অনেক সময় আমরা একটু মজা করে রোগীকে জিজ্ঞেস করি। বিশেষত আমি যেটা করি যে আপনি লেখাপড়া শেষ করছেন, চাকরি বাকরি করছেন, ঘর সংসার করতেছেন সবই তো করছেন। তো মাথা ব্যথাটা থাকলে অসুবিধা ঠিক। এটা নিয়েই থাকেন না। থাকেন না।

00:03:42.710 >> তো এই ধরনের রোগীগুলো ক্লিয়ারলি ডিফারেনশিয়েটেড। যে দীর্ঘদিন ধরে মাথা ব্যথায় ভুগছে। এটা একচুয়ালি টেনশন টাইপের হেডেক। উনি যখন কোন অস্থিরতায় থাকেন, কোন এজাইটেশনে থাকেন, তখনই উনার মাথা ব্যথাটা হয়। আর কিছু মাথা ব্যথা আছে যেগুলো একিউট অনসেট। এগুলো কিন্তু আমাদেরকে সিরিয়াসলি এড্রেস করতে হয়। যেমন হঠাৎ করে রোগী এসে বললাম আমার প্রচন্ড মাথা ব্যথা করছে। এরকম মাথা ব্যথা আমার জীবনে কখনো হয় নাই। মাথা ব্যথার সাথে কোনরকম শারীরিক দুর্বলতা, হাত পায়ের দুর্বলতা অথবা সাথে উনি চোখে কম দেখছেন এরকম কোন সমস্যা অথবা মাথা ব্যথার সাথে উনার বমি হচ্ছে। তো এই জিনিসগুলো কিন্তু আমাদের একটু সিরিয়াসলি এড্রেস করতে হয়। এই দুইটা জিনিসকে ব্রডহেডিং এ ধরে আমরা কিন্তু একচুয়ালি রোগীর মাথা ব্যথা ব্যাপারে চিন্তাভাবনা করি।

00:03:42.710 >> নিশ্চয়ই। ডাক্তার মোহাম্মদ তানভর হাসান মজুমদার এই যে মাথা ব্যথা অনেকে বলে থাকে যে একপাশে ব্যথা করছে আবার অনেকে দুই পাশে ব্যথা হচ্ছে। মাথা ব্যথার আসলে কোন ধরণ রয়েছে কিনা? ধন্যবাদ ডাক্তার সাক্ষর। মাথা ব্যথা আমরা সাধারণভাবে দুই ভাগে ভাগ করি। একটা প্রাইমারি হেডেক একটা সেকেন্ডারি হেডেক। প্রাইমারি হেডেক আমরা সবচেয়ে কমন যেটা টেনশন টাইপ হেডেক।

00:03:42.710 >> যেটা আমাদের অনেকেরই থাকে।

00:03:42.710 >> ওটাকে আমরা সেভাবে আমলে নেই না। টেনশন টাইপ হেডেকটা আমরা সাধারণত রোগীকে কাউন্সেলিং এর মাধ্যমে কিছু এন্টি ডিপ্রেসেন্ট ওষুধ দিয়ে আমরা ঠিক করে ফেলি। আরো আছে মাইগ্রেন যেটা সবাই চেনেন মাইগ্রেনের ব্যথাটা অনেকে জানেন যে মাথার একপশ ব্যথা থাকে রোগী দেখা যায় যে তার চোখে আলো পড়লে তার ভালো লাগে না অন্ধকার রুমে থাকতে ভালোবাসে

00:03:42.710 >> আরো আছে ক্লাস্টার হেডেক একটা চোখ চোখের আশেপাশে তার ব্যথা হয় অনেকের আছে সাইনোসাইটিসের হেডেক সাইনোসাইটিসের হেডেক

00:05:24.390 >> তার ওই যে ফ্রন্টাল সাইনাস আমরা যেটা বলি তার আশেপাশে তার ব্যথা হয় শীতকালে হয় শরীর যদি ঠান্ডা লাগে তাহলে হয় আর সেকেন্ডারি হেডেক যেটা বলি যেটাতে আমরা কোন কারণ খুঁজে পাই ব্রেনে কোন টিউমার রক্তক্ষরণ ইত্যাদি বিভিন্ন কারণে মাথা ব্যথা হয়ে থাকে ব্যথা হয়ে থাকে

00:05:43.350 >> নিশ্চয় অধ্যাপক ডাক্টার মোহাম্মদ জাহিদ রাহান আপনার কাছে আসছি সেটি হচ্ছে টেনশনের কারণে বা এংজাইটির কারণে যে মাথায় হেডেক হচ্ছে বা মাথা ব্যথা হচ্ছে একজন ব্যক্তি আসলে কিভাবে বুঝবেন যে এটি শুধুমাত্র টেনশনের কারণেই হচ্ছে

00:05:43.350 >> আসলে এটা রোগীর পক্ষে বোঝা ডিফিকাল্ট। রোগী শুধু একটা সিমটম নিয়ে আমাদের কাছে আসেন যে আমার মাথা ব্যথা করতেছে। একচুয়ালি আমি যেটা বলতে পারি এখানে সেটা হলো যে টেনশনের কারণে মাথা ব্যথাটা কেন হয়? যদিও এটার পেছনে একটা প্যাথোজেনেসিস আছে। তবে রোগীরা এটা সহজে বুঝতে পারবেন আমার কথাটা শুনলে আর কি।

00:05:43.350 >> সেটা হলো যে আমাদের যখন আমরা যখন কোন কিছু নিয়ে এজাইটেশনে ভুগি কোন দুশ্চিন্তা করি

00:05:43.350 >> তখন একচুয়ালি কিন্তু আমাদের শরীরে দুইটা সিস্টেম আছে সিম্প্যাথিক প্যারাসিমপ্যাথেক। তো সিম্প্যাথেটিক সিস্টেমটা কিন্তু ওভারঅক্টিভেটেড হয়।

00:05:43.350 >> এর কাজই হলো যে রক্তনালীগুলাকে প্রচুর স্ফৃত করে দেওয়া। এর ভেতর দিয়ে রক্তপ্রবাহ বাড়ায় দেওয়া। বাড়ায় দেওয়া।

00:06:36.550 >> চিন্তার ক্ষেত্রগুলো প্রসারিত করে দেওয়া। মানে একটা এমারজেন্সি স্টেট ডেভেলপ করা। তো যখন এই রক্তনালীগুলো স্ফৃত হয়ে যায় মেনলি আমাদের মাথার চামড়ার নিচে রক্তনালীগুলো স্ফৃত হলে ওখানে কিন্তু কিছু পেন রিসেপ্টর। হিউজ পেন রিসেপ্টর থাকে। ওগুলো কিন্তু স্ট্রেচ হয়। ওগুলো টান পড়ে। হু হু

00:06:55.189 >> তখনই কিন্তু আমাদের ব্যথাটা হয় এবং এইজন্য টেনশন টাইপ হেডেকের যে পেশেন্টগুলো তাদেরকে কিন্তু মেইনলি প্রোপানল টাইপের বেটা ব্লকের টাইপের প্রেসারের ওষুধ খুব লো ডোজে দিয়েই কিন্তু এই টেনশন টাইপ হেডেক সাথে কিছু প্যারাসিটামল জাতীয় ওষুধ এগুলো দিয়ে কিন্তু ম্যানেজ করে ফেলা যায়। তো এটা হলো প্যাথোজেনেসিস। একটু যেমন একজন চাকুরিজীবী সারাদিন কাজের শেষে যখন সে বাসায় ফিরছে তখন হয়তো তার একটু হেডেক হচ্ছে। হু হু হচ্ছে। হু হু

00:07:23.990 >> সে ঘুমাচ্ছে ঘুম দেওয়ার পর সে ফ্রেশ। তো এটা একচুয়ালি টেনশন টাইপ হেডেক বা প্রাইমারি হেডেক। এটা জটিল কিছু না। তবে সবসময় যদি একজন টেনশনে ভোগে অস্থিরতার মধ্যে থাকে তাহলে তার ক্রনিক কিছু ডিসঅর্ডার ডেভেলপ করতে পারে। সুতরাং এগুলো থেকে দূরে থাকাই ভালো।

00:07:23.990 >> নিশ্চয়। অধ্যাপক ডক্টর মোহাম্মদ জাহিদ রায়হান দর্শকের যেটি প্রশ্ন থাকে যে যাদের টেনশনের কারণে মাথা ব্যথা হচ্ছে সেটি নিয়েও কি চিকিৎসকের পরামর্শ নিতে হবে কিনা বা চিকিৎসকের স্বরণাপন্ন হতে হবে কিনা? কিনা? কিছু কিছু টেনশন টাইপ হেডেক আছে যেগুলো আমাদের ডেইলি লাইফকে হ্যাম্পার করে। দৈনন্দিন কাজে বাধা সৃষ্টি করে। যে আমার মাথা ব্যথা করছে আমি ঠিক আমার মানে মেজাজটা আমি ঠিক রাখতে পারছি না।

00:07:52.790 >> এবং দৈনন্দিন কর্মকাণ্ডে যখনই এটা বাধা সৃষ্টি করবে আমার অফিসে আমার বাসায় তখন ডেফিনেটলি সে কিন্তু ডাক্তারের কাছে ডাক্তারের স্মরণপন্ন হয় বা হওয়া উচিত। কিন্তু এটা আসলে খুব সিরিয়াস কিছু না। কাউন্সেলিং কাউন্সেলিং ইজ দা মেন স্টে। ইজ দা মেন স্টে।

00:08:28.469 >> ঠিকমত পেশেন্টকে কাউন্সেলিং করতে পারলেই আমার মনে হয় যে এই টেনশন টাইপের হেডেক থেকে রোগীকে মুক্তি দেওয়া সম্ভব।

00:08:28.469 >> নিশ্চয়ই ডাক্তার মোহাম্মদ তানভীর হাসান মজুমদার আপনার কাছে যে বিষয়টি জানবো সেটি হচ্ছে এই যে আমরা সতর্ক বার্তার কথা বলছি যে মাথা ব্যথা এক ধরনের সতর্ক বার্তা নিয়ে আসে। কখন কখন এবং কোন কোন ক্ষেত্রে এবং সেগুলো আসলে রোগীদের কিভাবে বুঝতে পারবেন, কখন চিকিৎসকের স্মরণপন্ন হবেন তারা। ধন্যবাদ। মাথা ব্যথা আমরা বেশিরভাগ ক্ষেত্রেই আমরা অত সিরিয়াস কিছু না। কিন্তু অল্প কিছু মাথা ব্যথা অবশ্যই সিরিয়াস হওয়ার বিষয় আছে। আমরা যেটা বলি রেড ফ্লেক্স সাইন। রেড ফ্লেক্স সাইন।

00:09:03.829 >> কারো হঠাৎ করে ব্যথা এবং তীব্র ব্যথা

00:09:03.829 >> তিনি অবশ্যই নিউরোসার্জন সরবন্ন হবেন। সিটি স্ক্যান করবেন। অথবা কারো বয়স বেশি 60 এর উপরে। হুম।

00:09:03.829 >> তার কখনোই মাথা ব্যথা ছিল না। তার এই ওল্ড এজে তার মাথা ব্যথা আসলো।

00:09:03.829 >> হুম।

00:09:22.070 >> হুম।

00:09:22.070 >> অথবা তার কারো যদি মাথা ব্যথার সাথে শরীরে একপশ চোখে ঝাপসা দেখে

00:09:22.070 >> সেটা আপনি সিরিয়াস হওয়ার বিষয় আছে।

00:09:22.070 >> অথবা কারো যদি মাথা ব্যথার সাথে ওজন কমে যাচ্ছে। যাচ্ছে।

00:09:35.269 >> আমরা যদি বলি সেরাটিস একাফলাইটিস বিভিন্ন কারণ হতে পারে। কারণ হতে পারে। এগুলোই এগুলোই

00:09:40.150 >> নিশ্চয়ই সেক্ষেত্রে আসলে পরবর্তী সময় চিকিৎসকের স্মরণাপন্ন হবার পর আপনারা আসলে কি কি পরীক্ষা নিরীক্ষা বা ইতিহাস কিভাবে নিয়ে থাকেন বা চিকিৎসা পদ্ধতির ব্যাপারগুলো কিভাবে নিশ্চিত করেন

00:09:40.150 >> আমরা সবচেয়ে কমন যেটা বলি যে টেনশন ভেটেক আমরা সেটা এক্সক্লুড করার চেষ্টা করি

00:09:40.150 >> যে তার পারিবারিক কোন ঝামেলা কোন অসুবিধা আছে কিনা আমি একটা উদাহরণ বলি গতকালকে আমি একটা রোগী দেখলাম একটা রোগী দেখলাম

00:10:03.350 >> তিনি সেনাবাহিনীতে চাকরি করেন

00:10:03.350 >> ছয় মাস পরেই তার রিটায়ারমেন্ট

00:10:03.350 >> তার মাথা ব্যথা প্রচন্ড মাথা ব্যথা তাকে জিজ্ঞাসা করলাম যে মাথা ব্যথার কারণটা কি তিনি বললেন যে রিটায়ারমেন্ট হবে পরিবার কিভাবে চলবে ওই টেনশনে তিনি টেনশনটা বিষয়গুলো নিয়ে আপনা থেকে আমরা আরো জানব তবে তার আগে একজন দর্শক আমাদের সাথে ফোন কলে যুক্ত হয়েছেন দর্শক এই মুহূর্তে কে আছেন আমাদের সাথে নাম বলে আপনার প্রশ্নটি করবেন করবেন

00:10:28.069 >> সম্ভবত দর্শক আপনার ফোনটি বিচ্ছিন্ন হয়ে গিয়েছে আপনি পুনরায় চেষ্টা করবেন আমরা শুনছিলাম ডক্টর মোহম্মদ তানভর আপনার কাছ থেকে থেকে একটা বুঝবো কিভাবে একটা বুঝবো কিভাবে

00:10:39.190 >> আপনার কোন টেনশনের উপাদান থাকবে কোন ব্যাকগ্রাউন্ডে তার হিস্ট্রি কোন পারিবারিক হোক সামাজিক হোক কোন চাপের মধ্যে তিনি আছেন এবং তার ব্যথাটা হবে ব্যান্ড লাইক তার মাথার চতুর্দিকে মনে কোন কিছু চাপ দিচ্ছে কিছু চাপ দিচ্ছে

00:10:53.910 >> তার ভার্টেক্স মাথার মাথার উপর ব্যথা হবে এবং আপনি যদি তার টেনশনটা রিলিভ করে দেন দেখবেন যে ম্যাজিক্যালি তার ব্যথাটা উপসম হয়ে গেছে হয়ে গেছে

00:11:02.150 >> নিশ্চয় অধ্যাপক ডাক্তার মোহাম্মদ জাহিদ রায়হান ঘুমের সাথে মাথা ব্যথার কোন সম্পর্ক রয়েছে কিনা?

00:11:02.150 >> ঘুমের সাথে মাথা ব্যথার সম্পর্ক হ্যাঁ ডেফিনেটলি আছে। ঘুম থেকে ওঠার পরে মাথা ব্যথার সম্পর্কটা আমরা বেশি করে এড্রেস করি। আমরা যারা নিউরোসার্জন সেটা হলো যে ডক্টর তানভর যেটা বলল যে রেড ফ্ল্যাগ। একচুয়ালি রেড ফ্ল্যাগের থেকেও ইম্পর্টেন্ট জিনিস হলো তিনটা কার্ডিনাল ফিচার হেডেকের সাথে। যে মাথা ব্যথা, বমি এবং চোখে কম দেখা অথবা দৃষ্টি শক্তি দ্রুত চলে যাওয়া। চলে যাওয়া।

00:11:39.030 >> এই হেডেক এবং ভমিটিং মাথার ভেতরে যদি কোন স্পেস অকুপাইং লেশন হয় টিউমার বা জাতীয় কোন সমস্যা হয় তাহলে কিন্তু রোগীর মর্নিং হেডেক এবং ভমিটিংটা খুব কার্ডিনাল ফিচার। সে সকালে ঘুম থেকে উঠবেই মাথা ব্যথা নিয়ে। নিয়ে।

00:11:53.990 >> আচ্ছা।

00:11:54.389 >> আচ্ছা।

00:11:54.389 >> আবার কিছু কিছু রোগী সারাদিন মাথা ব্যথা নিয়ে থাকে। কোন রকম সে হয়তো এক দুই ঘন্টা ঘুমায় মাথা ব্যথা নিয়ে। তারপরে সে আবার উঠে উঠে পড়ে তো মাথা ব্যথার জন্য একজন মানুষ ঘুমাতে পারছে না বা ঘুম থেকে উঠে তার মাথা ব্যথা নিয়েই তার ঘুমটা ভাঙছে সাথে তার ভাঙছে সাথে তার

00:12:12.389 >> আমরা এই মাথা ব্যথার বিষয়গুলো নিয়ে আপনার থেকে জানব তবে তার আগে একজন দর্শক আমাদের সাথে ফোন কলে যুক্ত হয়েছেন দর্শক এই মুহূর্তে কে আছেন আমাদের সাথে নাম বলে আপনার প্রশ্নটি করবেন

00:12:12.389 >> আমার জি দর্শক আপনার প্রশ্নটি করুন আমাদের

00:12:28.150 >> আমি

00:12:29.590 >> আমি স্যার স্যার মাথা সংসার

00:12:29.590 >> হু হু হু

00:12:35.750 >> হু হু হু

00:12:35.750 >> তারপর

00:12:38.550 >> তারপর আর হঠাৎ ভালো আর হঠাৎ ভালো

00:12:42.629 >> দর্শক এখন আপনার কি সমস্যা হচ্ছে

00:12:42.629 >> এখন মাথা

00:12:51.190 >> আচ্ছা অধ্যাপক ডাক্তার মোহম্মদ জাহিদ রায়হান দর্শকের কাছে কিছু জানা রয়েছে কিনা কিনা

00:12:53.750 >> আমি প্রশ্নটা ঠিক বুঝতে পারলাম না যদি একটু বলছিলেন তার হঠাৎ করে মাথা ব্যথা হয় আবার সেটি ভালো হয়ে যায়।

00:12:53.750 >> আচ্ছা আমি প্রথমে যেটা বললাম যে এটা কতদিন ধরে কতদিন ধরে আপনি ভুগছেন?

00:13:10.230 >> কতদিন?

00:13:10.230 >> প্রায় ছয় সাত মাস।

00:13:10.230 >> আপনার অন্য অন্য কোন সমস্যা আছে কিনা?

00:13:10.230 >> না ভাই অন্য কোন সমস্যা।

00:13:10.230 >> অন্য সমস্যা। আপনার বয়স কত?

00:13:10.230 >> বয়স

00:13:23.269 >> বয়স 48 বছর। 48 বছর।

00:13:25.269 >> 48 বছর। বছর

00:13:26.870 >> 48 বছর। বছর

00:13:26.870 >> আমার মনে হয় যে আপনি স্থানীয় কোন একজন ফিজিশিয়ানকে দেখাতে পারেন আপনার মাথা ব্যথার ব্যথার টোটাল টোটাল সমস্যাগুলো নিয়ে ওনার সাথে আলাপ করলে আমার মনে হয় যে উনি আপনার এই সুন্দর একটা দর্শক তিনি কিছু ওষুধও খাচ্ছেন তিনি কিছু নামও বলেছিলেন ওষুধগুলো খাচ্ছেন তাতেই আসলে দেখা যাচ্ছে যে স্পষ্ট করে উনি বলেন যে কি কি ওষুধ কিন্তু তিনি কিছু ওষুধ খাচ্ছিলেন এবং বলছিলেন যে হঠাৎ হঠাৎ করে মাথা ব্যথা হচ্ছে আবার হঠাৎ করে ঠিক করে যাচ্ছে এখন আসলে তার জন্য কি করণীয় যদি এটা সাত আট মাসের একটা হিস্ট্রি থাকে উনি ওষুধ খেলে ব্যথা চলে যাচ্ছেন উনার আবার ব্যথা ফিরে আসছে তো আমার মনে হয় যে এটা টেনশন টাইপ হেডেই হওয়ার সম্ভাবনা সবচেয়ে বেশি সবচেয়ে বেশি

00:14:07.110 >> তো আমার মনে হয় যে ওনারা নিজে নিজে মেডিকেশন করার কোন দরকার নাই

00:14:07.110 >> আমাদের দেশের রোগীরা তো ম্যাক্সিমাম ক্ষেত্রে ফার্মেসির সাথে যোগাযোগ করে ওষুধগুলো নেন এটাও নেওয়ার দরকার নেই আপনি স্থানীয় একজন এমবিবিএস ডাক্তারের স্বর্ণাপন্ন হলেই আমার মনে হয় যে উনি আপনাকে খুব ভালো একটা সমাধান দিতে পারবেন

00:14:07.110 >> নিশ্চয়ই আমরা আপনার কাছ থেকে শুনছিলাম মাথা ব্যথার বিষয়গুলো নিয়ে ঘুমের সাথে সম্পর্কের বিষয় সম্পর্কের বিষয় অধ্যাপক ডক্টর মোহাম্মদ জাহিদ রায়হান

00:14:29.990 >> আচ্ছা তো যেটা বলছিলাম এগুলো কিন্তু খুব কার্ডিনাল ফিচার আমরা সন্দেহ করি যে ব্রেন আমাদের মাথার খুলির ভেতরে যে ব্রেনটা থাকে এটা কিন্তু একটা ভলিউম নিয়ে থাকে এবং একটা হার্ড মাসের মধ্যে থাকে শক্ত খুলির ভেতরে থাকে তো এখানে যদি আমার কোন কিছু তৈরি হয় একটা ব্রেন টিউমার তৈরি হয় বা একটা নতুন করে কোন একটা মাস তৈরি হয় তো ব্রেন কিন্তু ওকে জায়গা দিতে পারে না।

00:14:29.990 >> ব্রেনের বিভিন্ন সেন্টার উপর কিন্তু ওই টিউমারটা তখন চাপ দেয় এবং এই চাপ দেওয়ার ফলশ্রুতিতে কিন্তু তখন আমাদের হেডেক, ভমিটিং, চোখে কম দেখা আরো অন্যান্য অনেক উপসর্গগুলো দেখা যায়। তো ঘুমের মধ্যে একচুয়ালি জিনিসটা অত ইম্পর্টেন্ট না। কিন্তু মাথা ব্যথা আমাকে ঘুমাতে দিচ্ছে না এবং আমি ঘুম থেকে উঠছি মাথা ব্যথা নিয়ে। এগুলো ভেরি কার্ডিনাল ফিচার। এবং মজার ব্যাপার হলো এগুলো যখন একজন রোগীর শুরু হয় উনি কিন্তু ঘরে থাকেন না। উনি ঘরে বসে থাকেন না। উনি ডেফিনেটলি একজন স্পেসিফিক নিউরোলজিস্ট অথবা নিউরোসার্জন কারো না কারণে স্বর্ণগুলো নিয়ে আপনার কাছ থেকে আমরা আরো জানবো। তবে তার আগে একজন দর্শক আমাদের সাথে ফোন কলে যুক্ত হয়েছেন। দর্শক এই মুহূর্তে কে আছেন আমাদের সাথে? নাম বলে আপনার প্রশ্নটি করবেন। দর্শক আমাদের সাথে ফোন কলে কে রয়েছেন? বেগম বেগম

00:15:47.509 >> জ দর্শক আপনার প্রশ্নটি করবেন আমাদের

00:15:47.509 >> উনার মাথা ব্যথা থাকে আর নাকের মধ্যে দিল খায় আর সকালে ঘুম থেকে উঠতে পারে না উনি কোমর নিয়ে কোমরের মধ্যে খুব ব্যথা থাকে

00:15:47.509 >> উনার তিনটা সিজার হয়েছিল

00:15:47.509 >> আচ্ছা ডাক্তার মোহম্মদ তানভীর হাসান মজুমদার দর্শকের কাছে কিছু জানা রয়েছে কিনা কিনা

00:16:08.310 >> জি উনার সিজার হয়েছে মহিলা রুগী না তাই বললেন তো বললেন তো

00:16:13.110 >> হ্যা তিনবার হয়েছে সেই ইতিহাস রয়েছে

00:16:13.110 >> জ

00:16:17.350 >> জ

00:16:17.350 >> আচ্ছা আচ্ছা সিজার সিজারের পর থেকে মাথা ব্যাথা

00:16:23.749 >> জি

00:16:23.749 >> সিজারের পর থেকে

00:16:23.749 >> হ্যালো

00:16:26.550 >> হ্যালো

00:16:26.550 >> মাথা ব্যাথা

00:16:27.670 >> মাথা ব্যাথা

00:16:27.670 >> মানে সিজারের আগে কি মাথা ব্যাথা ছিল না

00:16:27.670 >> মাথা ব্যাথা আকতে আছিল আর এখন মানে সিজারের পর উনি ঘুম থেকে উঠতে পারে না কোমরের মধ্যে কোমরের মধ্যে

00:16:34.230 >> জন্মবিরতিকর পিল খান কিনা একটু ইভশন প্রয়োজন আছে যাই হোক আমরা একটা স্পাইনাল হেডেক নিয়ে যদি বলি

00:16:34.230 >> নিশ্চয় নিশ্চয় দর্শক আপনার এই বিষয়টি নিয়ে কথা বলছি আমাদের সাথে থাকুন আমরা অনেক সময় যে সিজার করে এানস্থেটিস আমাদেরযে স্পাইনাল ব্লক দেয়। তো আমাদের মাথার মধ্যে যে সিএসএফ থাকে 150 এমল সিএসএফ থাকে। আমাদের ব্রেইন হচ্ছে 1400 গ্রাম। তো মোটামুটি 100 এমল ব্লাড সব মিলে 1700 গ্রাম।

00:16:34.230 >> তো এখানে সিএসএফ থাকার কারণে আমাদের ব্রেনের ওজন কিন্তু আমরা ফিল করি মাত্র 50 গ্রাম। তো স্পাইনাল যে ব্লকস দিয়ে থাকেন।

00:16:34.230 >> সেখানে কিছু সিএসএফ তো ড্রেন হয়। তো সেটা স্পাইনাল ব্লক দেওয়ার পর অনেকে বলেন যে মাথা ব্যথা ঘটছে কারণ সিএসএফটা কমে যাওয়াতে ব্রেনের যে সাসপেনশন সেটা কিন্তু কমে যাচ্ছে কমে যাচ্ছে

00:17:24.309 >> এজন্য পেশেন্টের ব্রেনটা হচ্ছে আমাদের যে ব্রেনের কাভার আছে ডুরা

00:17:24.309 >> ডুরাতে ঘর্ষণ হয়

00:17:24.309 >> তার কারণে মাথা ব্যথা ফিল করে

00:17:24.309 >> এছাড়াও ওরাল কন্ট্রাসেপটিভ পিল তো আছেই সেটা হিস্ট্রি তিনি বললেন না

00:17:24.309 >> সেক্ষেত্রে আসলে দর্শকের এখন কি করণীয়

00:17:24.309 >> তিনি অবশ্যই একজন নিউরোলজিস্ট বা নিউরোসার্জনের সাথে আলাপ করবেন। তিনি ফুল হিস্ট্রি ইভালুয়েট করে যাচাই করে বলতে পারবেন যে আসলে উনার সমস্যাটা কোথায়।

00:17:24.309 >> নিশ্চয় ধন্যবাদ আপনাকে। আরেকজন দর্শক আমাদের সাথে ফোন কলে রয়েছেন। দর্শক এই মুহূর্তে কে আছেন আমাদের সাথে? নাম বলে আপনার প্রশ্নটি করবেন।

00:17:24.309 >> আমার নাম আনোয়ারা।

00:18:08.789 >> দর্শক আপনার টিভির ভলিউমটি কমিয়ে দিয়ে আমাদের প্রশ্নটি আমাদের প্রশ্নটি

00:18:09.430 >> করবেন।

00:18:10.470 >> করবেন।

00:18:10.470 >> আমার নাম। আমরা আপনাকে শুনছি। আপনার প্রশ্নটি করুন আমাদের।

00:18:10.470 >> আমার

00:18:21.270 >> দর্শক এখন আপনার কি সমস্যা হচ্ছে?

00:18:21.270 >> হ্যাঁ বলছি টেলিভিশন ভলিউমটা কমে না। আমার মাথা ঘুরায়। মাথা ঘুরায়।

00:18:25.029 >> জি।

00:18:25.350 >> জি।

00:18:25.350 >> মানে প্রথম সকালবেলায় একবার ঘুম থেকে উঠে ভোরবেলা ভোরবেলা

00:18:30.310 >> আরো কম।

00:18:32.310 >> আরো কম।

00:18:32.310 >> জি।

00:18:33.750 >> জি।

00:18:33.750 >> এতক্ষণ শোনা যাবে না।

00:18:33.750 >> জি দর্শক আপনাকে আমরা শুনছি। হ্যাঁ বলুন।

00:18:33.750 >> সকালবেলা ঘুম থেকে উঠে দেখি আমি নামাজ পড়ছি। পড়ছি।

00:18:41.029 >> জি। জি

00:18:41.350 >> জি। জি

00:18:41.350 >> সেজদা দেওয়ার সময় দেখি যে আমার মাথা ঘুরছে ঘুরছে ঘুরছে ঘুরছে ঘুরছে

00:18:44.470 >> হু হু

00:18:45.029 >> হু হু

00:18:45.029 >> তারপরে আমাকে হসপিটালে নিয়ে যায় পাশাপাশি মনোয়ারা হসপিটাল ওখানে আমি যাই

00:18:45.029 >> আচ্ছা

00:18:49.990 >> আচ্ছা

00:18:49.990 >> যাওয়ার পর ডাক্তার আমাকে এই দুইটা ওষুধ দেয় দেয়

00:18:54.230 >> হুম

00:18:55.669 >> হুম

00:18:55.669 >> ওষুধ দুইটা দুইটা ছিল এবিডি আর এবিডি আর মিনারেল মিনারেল

00:19:03.430 >> আচ্ছা

00:19:04.150 >> আচ্ছা

00:19:04.150 >> হ্যাঁ বলছি পাঁচ দিন খাওয়ার জন্য

00:19:04.150 >> কিন্তু খাওয়ার পরেও এরপরে আমি একটু ঘুমিয়ে পড়ি বাসায় অনেক বড় পড়ি বাসায় অনেক বড়

00:19:10.470 >> হুম কিন্তু পাঁচ দিন চলে যায়। তারপর আবার ডাক্তারের কাছে যাই। ডাক্তার আবার গোবিন্দ গোবিন্দ হালকা আপনি কোন পরীক্ষা নিরীক্ষা করিয়েছিলেন কিনা? করিয়েছিলেন কিনা?

00:19:21.190 >> না পরীক্ষা নিরীক্ষা করাই নাই। এখন আমি অধ্যাপক জাহিদ কাছে কিছু জানার রয়েছে কিনা? আপনার বয়স কত? আমার বয়স 69 69

00:19:40.870 >> 69 আচ্ছা আপনার ডায়াবেটিস বা অন্য কোন অসুখ বিশুখ কিছু আছে

00:19:40.870 >> অন্য কোন কিছু নাই ডায়াবেটিস মানে মানে বিপদ মানে বিপদ মানে সেভেনের মত আছে সেভেনের মত আছে অলমোস্ট নিয়ন্ত্রণে যদি থাকে ওটা নিয়ন্ত্রণে আচ্ছা আমি

00:20:07.669 >> ধন্যবাদ আপনাকে কে একচুয়ালি আমরা টেলিভিশন প্রোগ্রামে তো রোগীদেরকে কমপ্লিট ম্যানেজমেন্ট দেওয়া সম্ভব না। কিন্তু কতগুলো বিষয় নিয়ে যদি কিছু ধারণা দিতে পারি এবং সে ধারণা অনুযায়ী যদি ওনারা চলেন এটা আমার মনে হয় যে এটা বেশি হেল্পফুল এসব প্রোগ্রামের মাধ্যমে। তো আপনার যেহেতু মাথা ঘোরাটা সমস্যা আমি একটু বলি। সেটা হলো আমাদের মাথার পেছনে কিন্তু একটা দুইটা মগজ একচুয়ালি থাকে। একটা ছোট মগজ একটা বড় মগজ। ছোটটাকে আমরা সেরিবেলাম বলি। তো এই সেরিবেলামের কোন সমস্যা যেকোন সমস্যাই হোক না কেন ফাস্ট কার্ডিনাল ফিচার হলো মাথা ঘরানো। সুতরাং আপনি আপনি যখন আমার কাছে এসে আপনার মাথা ঘরানোর কথা বলবেন তখন আমি প্রথমেই ধরে নেব যে আপনার ছোট মগজে কোন সমস্যা হচ্ছে কিনা। এবং আপনার যে বয়সটা বললেন সে বয়সের অন্যতম প্রধান কারণ হলো এই ছোট মগজে রক্ত সরবরাহ হয়ে বাধা সৃষ্টি হওয়া। অনেকগুলো কারণ আছে। তার মধ্যে অন্যতম হলো অথরোস্কলটিক চেঞ্জ। যেগুলো রক্তনালীতে চর্বি জমে ভরাট হয়ে যায়। ছোট মগজে যদি রক্ত সরবরাহ কম থাকে তাহলে বিভিন্ন ধরনের মাথাগড়া হতে পারে। তো এটা হলো একটা কারণ। এরকম কিন্তু বহু কারণ আছে। তো আমাদের কাছে যেসব রোগীরা আসেন তাদের এটা অন্যতম কারণ। আরো অনেক কারণ আছে। তো এই কারণগুলোর জন্য বেসিকলি আমাদের কিন্তু কিছু ইনভেস্টিগেশন করতেই হয়। তার মধ্যে আমরা যদি ইনডাইরেক্ট মানে অপ্রত্যক্ষভাবে কোন প্রমাণ চাই তাহলে আমরা ঘাড়ের একটা এক্সরে করলে আমরা বুঝতে পারি। যে ঘাড়ের হাড্ডি যদি কোন ডিজেনারেশনের কারণে বাঁকাতারা হয়ে যায় বা ডিফর্মড হয়ে যায় ওটার পাশ দিয়ে কিন্তু রক্তনালীটা আমাদের মগজে পৌঁছায়। ওটাও রক্তসর্বায় বাধা সৃষ্টি হয়। এথরোস্কলটিক চেঞ্জের জন্য হয়। তো এগুলো কিন্তু আপনি যখন একজন ডক্টরের স্বর্ণপন্ন হবেন উনি এই পরীক্ষাগুলো খুব সহজ ছোটখাট কয়েকটা পরীক্ষা করলেই উনি কিন্তু একটা প্রাথমিক ধারণা পেয়ে যাবেন যে আপনার মাথা ঘোরার কারণটা কি এবং এটা সহজেই কিন্তু এড্রেস করা যায়। আর কিছু কিছু অসুখ আছে যেগুলোর জন্য মাথা ব্যথা কোন মাথা ঘোরানো কোনভাবেই ভালো হতে চায় না। তো সেগুলো ডিফারেন্ট টাইপ অফ ডিজিজ কন্ডিশন সেগুলো কিন্তু বিভিন্ন ধরনের পরীক্ষা নিরীক্ষার মাধ্যমে ডায়াগনোসিস করা সম্ভব। তো আমার মনে হয় যে আপনার এটাই কারণ হতে পারে। অন্যতম প্রধান কারণ এটাই হতে পারে যে আপনার ছোট মগজে রক্ত সরবরাহ কোন কারণে হয়তো বাধা সৃষ্টি হচ্ছে এবং আপনাকে ভয় ভয় পাওয়ার কোন দরকার নেই। বাধা সৃষ্টি হচ্ছে মানে এটাকে এড্রেস করা সম্ভব। এটাকে ভালো করে দেওয়া সম্ভব। মেডিকেল ম্যানেজমেন্টে এটাকে ভালো করে দেওয়া সম্ভব। কোন কোন ক্ষেত্রে সার্জারি লাগে। ধন্যবাদ।


SYSTEM ROLE:
You are a data annotation assistant specialized in converting noisy Bengali TV transcripts into clean, structured medical conversation datasets.

CONTEXT:
The input is a raw Bengali transcript from Bangladeshi public TV health programs.
In these programs:
- A host asks health-related questions to an expert doctor (general, community-value questions).
- Sometimes real patients call in, describe symptoms, answer follow-up questions, and receive medical advice.
- The host may paraphrase or clarify patient statements when unclear.
- Since the transcribed text is generated from a srt file, it also includes timestamps, as like 00:05:23.830 >>
- Note that, ">>" this sign is generally placed where it is assumed to be kinf of a shift in the conversation, but this is not exactly reliable always, so do not blindly depend on it, rather carefully judge the context and language to understand and parse correctly 

TASK:
Parse the transcript into a structured JSON array containing:
1) host-doctor single-turn question–answer pairs
2) patient–doctor multi-turn medical conversations

The goal is to produce a clean dataset suitable for medical dialogue analysis.
Do NOT preserve the TV show format — preserve only medical meaning. 

OUTPUT FORMAT (STRICT — MUST FOLLOW EXACTLY):

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
      { "speaker": "doctor", "text": "..." },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "..." }
    ]
  }
]
```

GENERAL RULES (VERY IMPORTANT):
- Output ONLY valid JSON with ```json[.....]``` as such.
- No explanations, no greetings, no extra text.
- JSON must be parsable by Python `json.loads()` (no trailing commas).
- Use UTF-8 Bengali text inside "text" fields.
- JSON keys and values like "type", "speaker" must remain in English.
- You should try to infer the timestamps of the starting points of the conversations as correctly as you can. Before every occurrence of ">>" sign, we have an exact timestamp. From there, infer where that particulat instance host-doctor-qa or patient-call started exactly, and put that in the timestamp key exactly. 
- Note that, the QAs are expected to be self-contained, most often they are already as such. However, in some cases, it may be like, say, the show is about dengue, and the host asks "প্রতিরোধের উপায় কী?", in such case, try to add a bit more context, in bangla, in the same natural, so that the QA is self-contained. 
- Note that, doctor's review questions in reply to patient's incomplete description are supper valuable in terms of our dataset. Therefore, keep such cases of multiple turns where the doctor/host inquires supplementary questions to the patient to clarify. In such cases, the patient-call datapoints must be multi-turn.

CONTENT CLEANING RULES:
- Remove filler such as [মিউজিক], repeated subtitle fragments, timestamps, and transcription artifacts.
- Merge broken subtitle lines into complete Bengali sentences.
- If transcription errors are obvious, correct them conservatively.
- Do NOT hallucinate or invent information.
- Only use information present or clearly implied in the transcript.
- Note that, while you are encouraged to clean obvious errors, you are discouraged to alter the natural tone of conversations of the host, patient, and doctor. That means, do not try to rewrite the talks in your own language, rather retain the distinctive natural tones as they are in the transcription.

HOST–DOCTOR QA RULES:
- Prefer single-turn conversations:
  - One clear question from host
  - One complete answer from doctor
- If the host asks multiple related sub-questions, merge them into one coherent question.
- If absolutely necessary, you may allow multi-turn, but keep them concise and information-rich.

PATIENT CALL RULES (CRITICAL):
- Conversations must be multi-turn.
- Only include "patient" and "doctor" as speakers.
- DO NOT include the host as a speaker in patient calls.

MERGING RULES FOR PATIENT CALLS:
- If the host clarifies or rephrases the patient’s symptoms:
  → Merge the clarified version into the patient’s turn to avoid repetition of statement.
- But please understand that, by these we do not mean removing the multi-turnness, That means, say patient says 1/2 brief senttences, host asks a supplementary questions like age, patient tells it, doctor then asks how long does the situation persist, patient then answers, carefully note here that, in this case, you must form a multi-turn conversation, including the host's and doctor's clarification questions... Merging is only applicable to avoid repetition. When it is a clear new question from either side, keep that as separate since multi-turn conversation is of much value.
- That means, wheneverm the convevrsation includes supplementary questions (even if little in breadth), like, 
"আপনার এখন কী সমস্যা হচ্ছে?", "আপনার বয়স কত?", "এই সমস্যা কতদিন ধরে হচ্ছে?", "কোনো ওষুধ খাচ্ছেন কী?", "আপনার বাচ্চা কতজন?", "সিজারিয়ান ডেলিভারি হয়েছিল নাকি নরমাল?", "কন্ট্রাসেপটিভ পিল খাচ্ছেন?","মাথার একদিকে ব্যথা করে?", "আপনার ঘাড়ে ব্যথা আছে? রক্তচাপ কি নিয়ন্ত্রণে?", "সিজারের পর থেকেই মাথাব্যথা?", "সিজারের আগে মাথাব্যথা ছিল না?", "আপনি কতদিন ধরে ভুগছেন?", "আপনার অন্য কোনো সমস্যা আছে?", "আপনি কি ধূমপান করেন?", "আপনি কি টেনশন/এংজাইটি বা দুশ্চিন্তার মধ্যে থাকেন?",   
any such supllementary questions that the doctor or host asks (there may be other diverse types of clarification questions) must be retained as multi-turn conversation questions, rather than merging, so in such cases, it should be like, 

{
    "type": "patient_call",
    "timestamp": "00:07:51.690",
    "turns": [
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "আপনার এখন কী সমস্যা হচ্ছে?" },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "আপনার বয়স কত?" },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "এই সমস্যা কতদিন ধরে হচ্ছে?" },
      { "speaker": "patient", "text": "..." },
      { "speaker": "doctor", "text": "......" }
    ]
}

Note that this is just an example to show that you are encouraged to retain the multi-turn nature of doctor-patient conversation as much as possible, where applicable.

- Remove repetition while preserving medical meaning.
- Ensure the conversation captures:
  - patient symptom description
  - doctor clarification questions
  - patient follow-up responses
  - doctor medical advice or guidance

SEGMENTATION RULES:
Create a new conversation object when:
- The host introduces a new topic or question
- A patient call begins or ends
- A new patient starts speaking

FINAL CONSTRAINTS:
- Stay faithful to the transcript.
- Do not add new symptoms, diagnoses, or advice.
- Do not include TV-show-style greetings or introductions.
- Strictly follow the JSON schema above.

Now parse the Bengali transcript into the required JSON:

You MUST cover the whole transcript in your JSON. the conversations all must be meaningful, fully complete as in transcription. You must not output any greetings etc, only the JSON in ```json[...]```
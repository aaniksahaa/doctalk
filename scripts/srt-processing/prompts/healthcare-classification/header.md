[ROLE]
You are a strict healthcare content classifier.

[TASK]
Determine whether a youtube video content is related to healthcare, providing knowledge or discussion regarding health, diseases etc.

Healthcare-related content includes:
- Medicine or medical advice
- Physical or mental health topics
- Diseases, symptoms, diagnosis, or treatment
- Health tips, wellness, nutrition, fitness

Non-healthcare content includes:
- Entertainment, gaming, vlogs, lifestyle content, political news
- Technology, travel, or general news unrelated to health
- Purely motivational content without medical context

A useful knowledge for you is that, we have some names of television programs and channels which we particularly target. So if the metadata contains these channels or program names in the title and description, it is very likely a desired content.

List of Program and Channel Names:

**BTV**
স্বাস্থ্য জিজ্ঞাসা – Bangladesh Television

**ATN Bangla**
সুস্থ থাকুন – ATN Bangla

**NTV**
স্বাস্থ্য প্রতিদিন – NTV Health Show

**RTV**
সুস্থ থাকুন – RTV Health
RTV Health Program

**MyTV**
My Health – MyTV

**GTV**
Doctor’s Chamber – GTV

**DBC News**
স্বাস্থ্যকথা – DBC News

**Channel 24**
সুরক্ষায় প্রতিদিন – Channel 24
সুস্থ মেরুদণ্ড – Channel 24

**Jamuna TV**
Doctors On Call – Jamuna TV

**Maasranga TV**
Doctor’s Chamber – Maasranga TV Program

**Deepto TV**
সুস্থ জীবন – Deepto Health Show

**Banglavision**
স্বাস্থ্য কথা – Banglavision

**Boishakhi TV**
Boishakhi Health – Boishakhi TV

**News24**
Health Tips – News24

However, note that, these same channels can contain non-healthcare programs like news etc.

Sometimes, due to channel authority's mistakes, it may happen that the title is news but the description says healthcare content, For instance, 

Title:
দুপুর ২টার সংবাদ
Description:
টেলিফোনে দর্শকদের অংশগ্রহণে স্বাস্থ্য বিষয়ক \nসরাসরি অনুষ্ঠান - “স্বাস্থ্য জিজ্ঞাসা” \nআজকের বিষয়: হৃদরোগের চিকিৎসা এবং করোনা সংক্রান্ত যে কোন সমস্যায় করণীয়।\nগ্রন্থনা ও উপস্থাপনা: ডা ফাহিম আহমেদ রুপম, কনসালটেন্ট, মেডিসিন ও ডায়ামেটিস।\n\nআলোচক: \nহেল্পডেস্ক: ডা: তামান্না মাহ্‌মুদ ঊর্মি, এমবিবিএস, এম.ফিল \nপ্রচার: ২৮ সেপ্টেম্বর  ২০২২\n\n[ আমাদের ফেসবুক পেজটিকে Like ও Follow করুন এবং \nইউটিউব চ্যানেলটি সাবস্ক্রাইব করে সাথে থাকুন ]\n\nSubscribe to us on YouTube:\nhttps://www.youtube.com/c/BangladeshTelevision-BTV?sub_confirmation=1\nLike, Follow us on Facebook: \nhttps://www.facebook.com/btv.gov.bd\nVisit us: http://www.btv.gov.bd\n_________________________________________________\nAll Rights Reserved © Bangladesh Television 2022\n#BangladeshTelevision

In such case, classify it as healthcare content.

[OUTPUT FORMAT]
Respond ONLY with a valid JSON object:
{
  "healthcare": true | false
}

[EXAMPLES]

Input:
Title: 
কোমরের ব্যথা কেন হয়? | Back Pain Treatment | Dr. Moshiur Rahman Limon | My Health | EP-463
Description:
কোমরের ব্যথা কেন হয়? | Back Pain Treatment | Dr. Moshiur Rahman Limon | My Health | EP-463\nআরও বিস্তারিত জানতে ভিজিট করুন: <URL>\nYouTube Channel:\nMytv Bangladesh: <URL>\nMytv News : <URL>\nmytv Entertainment: <URL>\nmytv Natok: <URL>\nMytv Islamic: <URL>\nMytv Live: <URL>\nMytv Music: <URL>\nFacebook Page:\nmytv Bangladesh: <URL>\nMytv News : <URL>\nMytv । মাইটিভি : <URL>\nmytv Entertainment: <URL>\nTiktok:\n<URL>\nFair Use Disclaimer:\nThis channel may use some copyrighted materials without specific authorization of the owner but contents used here falls under the “Fair Use” as described in The Copyright Act 2000 Law No. 28 of the year 2000 of Bangladesh under Chapter 6, Section 36 and Chapter 13 Section 72. According to that law allowance is made for \"fair use\" for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\n\"Copyright Disclaimer Under Section 107 of the Copyright Act 1976, allowance is made for fair use for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\"\nAbout MYTV:\nMY TV is a satellite-based Bengali language television channel. It has been broadcasting since April 15, 2010. It is a popular TV channel in Bangladesh. It broadcasts a variety of programs including news, dramas, movies, religious, educational, and political discussions. It is broadcast in over 153 countries, including the US, Canada, Europe, and various countries in the Middle East.\nContent Rights & Permissions:\nMYTV retains exclusive rights to all content aired on the channel, and permission for its use is strictly limited to MYTV (V.M. International Limited).\nAddress:\nMytv Bhaban , 155, 150/3 , Hatirjheel,\nDhaka-1219, Bangladesh.\nFor more info please contact:\nName : Mytv Admin\nEmail: <EMAIL>\n#mytvBangladesh #News
Output:
{ "healthcare": true }

Input:
Title:
কুষ্টিয়ায় অগ্রহায়ণের আমেজে খেজুর রস–গুড় উৎপাদনে ব্যস্ততা | kushtia | Mytv News
Description:
কুষ্টিয়ায় অগ্রহায়ণের আমেজে খেজুর রস–গুড় উৎপাদনে ব্যস্ততা | kushtia | Mytv News\nআরও বিস্তারিত জানতে ভিজিট করুন: <URL>\nYouTube Channel:\nMytv Bangladesh: <URL>\nMytv News : <URL>\nmytv Entertainment: <URL>\nmytv Natok: <URL>\nMytv Islamic: <URL>\nMytv Live: <URL>\nMytv Music: <URL>\nFacebook Page:\nmytv Bangladesh: <URL>\nMytv News : <URL>\nMytv । মাইটিভি : <URL>\nmytv Entertainment: <URL>\nTiktok:\n<URL>\nFair Use Disclaimer:\nThis channel may use some copyrighted materials without specific authorization of the owner but contents used here falls under the “Fair Use” as described in The Copyright Act 2000 Law No. 28 of the year 2000 of Bangladesh under Chapter 6, Section 36 and Chapter 13 Section 72. According to that law allowance is made for \"fair use\" for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\n\"Copyright Disclaimer Under Section 107 of the Copyright Act 1976, allowance is made for fair use for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\"\nAbout MYTV:\nMY TV is a satellite-based Bengali language television channel. It has been broadcasting since April 15, 2010. It is a popular TV channel in Bangladesh. It broadcasts a variety of programs including news, dramas, movies, religious, educational, and political discussions. It is broadcast in over 153 countries, including the US, Canada, Europe, and various countries in the Middle East.\nContent Rights & Permissions:\nMYTV retains exclusive rights to all content aired on the channel, and permission for its use is strictly limited to MYTV (V.M. International Limited).\nAddress:\nMytv Bhaban , 155, 150/3 , Hatirjheel,\nDhaka-1219, Bangladesh.\nFor more info please contact:\nName : Mytv Admin\nEmail: <EMAIL>\n#mytvBangladesh #News
Output:
{ "healthcare": false }

Input:
Title:
বেগম খালেদা জিয়ার শারীরিক অবস্থার সর্বশেষ | Mytv News
Description:
বেগম খালেদা জিয়ার শারীরিক অবস্থার সর্বশেষ | Mytv News\nআরও বিস্তারিত জানতে ভিজিট করুন: <URL>\nYouTube Channel:\nMytv Bangladesh: <URL>\nMytv News : <URL>\nmytv Entertainment: <URL>\nmytv Natok: <URL>\nMytv Islamic: <URL>\nMytv Live: <URL>\nMytv Music: <URL>\nFacebook Page:\nmytv Bangladesh: <URL>\nMytv News : <URL>\nMytv । মাইটিভি : <URL>\nmytv Entertainment: <URL>\nTiktok:\n<URL>\nFair Use Disclaimer:\nThis channel may use some copyrighted materials without specific authorization of the owner but contents used here falls under the “Fair Use” as described in The Copyright Act 2000 Law No. 28 of the year 2000 of Bangladesh under Chapter 6, Section 36 and Chapter 13 Section 72. According to that law allowance is made for \"fair use\" for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\n\"Copyright Disclaimer Under Section 107 of the Copyright Act 1976, allowance is made for fair use for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\"\nAbout MYTV:\nMY TV is a satellite-based Bengali language television channel. It has been broadcasting since April 15, 2010. It is a popular TV channel in Bangladesh. It broadcasts a variety of programs including news, dramas, movies, religious, educational, and political discussions. It is broadcast in over 153 countries, including the US, Canada, Europe, and various countries in the Middle East.\nContent Rights & Permissions:\nMYTV retains exclusive rights to all content aired on the channel, and permission for its use is strictly limited to MYTV (V.M. International Limited).\nAddress:\nMytv Bhaban , 155, 150/3 , Hatirjheel,\nDhaka-1219, Bangladesh.\nFor more info please contact:\nName : Mytv Admin\nEmail: <EMAIL>\n#mytvBangladesh #News
Output:
{ "healthcare": false }

Input:
Title:
স্বাস্থ্য জিজ্ঞাসা - আজকের বিষয়: শীতকালীন ত্বকের যত্ন ও করণীয় | স্বাস্থ্য বিষয়ক সরাসরি অনুষ্ঠান
Description:
টেলিফোনে দর্শকদের অংশগ্রহণে স্বাস্থ্য বিষয়ক সরাসরি অনুষ্ঠান - “স্বাস্থ্য জিজ্ঞাসা”\nউপস্থাপনা: ডা. সামিউল আউয়াল সাক্ষর\nআজকের বিষয়: শীতকালীন ত্বকের যত্ন ও করণীয়\nআলোচক\n- অধ্যাপক ডা. আহাম্মদ আলী, সাবেক বিভাগীয় প্রধান, চর্ম ও যৌন রোগ বিভাগ, শহীদ সোহরাওয়ার্দী মেডিকেল কলেজ ও হাসপাতাল\n- ডা. তাসনিম খান, সহযোগী অধ্যাপক, চর্ম ও যৌন রোগ বিভাগ, নর্দান মেডিকেল কলেজ ও হাসপাতাল\nপ্রযোজনা: গোলাম মোর্শেদ\nতারিখ: ২২ নভেম্বর, ২০২৫\n⭕আমাদের ইউটিউব চ্যানেলটি সাবস্ক্রাইব করে সাথে থাকুন ⭕\n⬤ BTV NEWS: <URL>\n⬤ BTV Drama: <URL>\n⬤ BTV Music: <URL>\n⬤ Bangladesh Television: <URL>\n⭕ বিটিভির অফিসিয়াল ফেসবুক পেজ: <URL>\nওয়েবসাইট: <URL>\n_\nAll Rights Reserved © Bangladesh Television 2025\n#bangladeshtelevision #BTV",
Output:
{ "healthcare": true }

Input:
Title:
স্বাস্থ্য জিজ্ঞাসা -০৬ ডিসেম্বর, ২০২৩
Description:
স্বাস্থ্য জিজ্ঞাসা -০৬ ডিসেম্বর, ২০২৩
Output:
{ "healthcare": true }

Input:
Title:
ড. মুহাম্মদ ইউনূসের নেতৃত্বে ৩৫ মন্ত্রণালয়ের স্বাস্থ্য সমঝোতা স্মারক | Mytv News
Description:
ড. মুহাম্মদ ইউনূসের নেতৃত্বে ৩৫ মন্ত্রণালয়ের স্বাস্থ্য সমঝোতা স্মারক | Mytv News\nআরও বিস্তারিত জানতে ভিজিট করুন: <URL>\nYouTube Channel:\nMytv Bangladesh: <URL>\nMytv News : <URL>\nmytv Entertainment: <URL>\nmytv Natok: <URL>\nMytv Islamic: <URL>\nMytv Live: <URL>\nMytv Music: <URL>\nFacebook Page:\nmytv Bangladesh: <URL>\nMytv News : <URL>\nMytv । মাইটিভি : <URL>\nmytv Entertainment: <URL>\nTiktok:\n<URL>\nFair Use Disclaimer:\nThis channel may use some copyrighted materials without specific authorization of the owner but contents used here falls under the “Fair Use” as described in The Copyright Act 2000 Law No. 28 of the year 2000 of Bangladesh under Chapter 6, Section 36 and Chapter 13 Section 72. According to that law allowance is made for \"fair use\" for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\n\"Copyright Disclaimer Under Section 107 of the Copyright Act 1976, allowance is made for fair use for purposes such as criticism, comment, news reporting, teaching, scholarship, and research. Fair use is a use permitted by copyright statute that might otherwise be infringing. Non-profit, educational or personal use tips the balance in favor of fair use.\"\nAbout MYTV:\nMY TV is a satellite-based Bengali language television channel. It has been broadcasting since April 15, 2010. It is a popular TV channel in Bangladesh. It broadcasts a variety of programs including news, dramas, movies, religious, educational, and political discussions. It is broadcast in over 153 countries, including the US, Canada, Europe, and various countries in the Middle East.\nContent Rights & Permissions:\nMYTV retains exclusive rights to all content aired on the channel, and permission for its use is strictly limited to MYTV (V.M. International Limited).\nAddress:\nMytv Bhaban , 155, 150/3 , Hatirjheel,\nDhaka-1219, Bangladesh.\nFor more info please contact:\nName : Mytv Admin\nEmail: <EMAIL>\n#mytvBangladesh #News
Output:
{ "healthcare": false }

[INPUT]
Now carefully perform the classification for the following video metadata.


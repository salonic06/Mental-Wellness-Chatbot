"""User language preference and localized UI shell (5 Indian languages + English)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from bot_reply import BotReply, Button
from db_paths import connect
from db_sql import execute

ButtonList = List[Button]

# code, native label (picker), English name (LLM)
LANGUAGES: List[Tuple[str, str, str]] = [
    ("en", "English", "English"),
    ("hi", "हिंदी", "Hindi"),
    ("mr", "मराठी", "Marathi"),
    ("gu", "ગુજરાતી", "Gujarati"),
    ("bn", "বাংলা", "Bengali"),
]

SUPPORTED = frozenset(code for code, _, _ in LANGUAGES)
DEFAULT_LANG = "en"
WHATSAPP_LIST_MAX_ROWS = 10

LANG_ALIASES: Dict[str, str] = {
    "english": "en",
    "hindi": "hi",
    "marathi": "mr",
    "gujarati": "gu",
    "bengali": "bn",
    "bangla": "bn",
}

LANG_SET_MSG: Dict[str, str] = {
    "en": "Language set to English.",
    "hi": "भाषा हिंदी में सेट हो गई।",
    "mr": "भाषा मराठीत सेट केली.",
    "gu": "ભાષા ગુજરાતીમાં સેટ થઈ.",
    "bn": "ভাষা বাংলায় সেট হয়েছে।",
}

LLM_LANG: Dict[str, str] = {
    "en": "English",
    "hi": "Hindi (Devanagari script)",
    "mr": "Marathi (Devanagari script)",
    "gu": "Gujarati (Gujarati script)",
    "bn": "Bengali (Bangla script)",
}

# All user-facing shell strings — every key must exist for each supported locale.
STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": (
            "Hey — I'm your wellness companion.\n\n"
            "Check-ins, open chat, breathing, and meditation — not therapy, "
            "just a steady presence that remembers your mood over time.\n\n"
            "Tell me how you're doing, or tap the menu below.\n"
            "Type /language to switch language."
        ),
        "language_pick": (
            "Choose your language:\n\n"
            "Menus and my replies will use this language until you change it "
            "with /language or *Language* in the menu."
        ),
        "language_invalid": "Please pick a language from the list, or send /language hindi | marathi | gujarati | bengali | english.",
        "help": (
            "I'm your wellness companion — talk naturally or tap the menu.\n\n"
            "• /checkin — guided mood log\n"
            "• Talk it out — open chat\n"
            "• /summary — your week + patterns\n"
            "• /language — change language"
        ),
        "menu_label": "Wellness menu",
        "help_menu_label": "Quick actions",
        "lang_list_btn": "Choose language",
        "section_wellness": "Wellness",
        "section_languages": "Languages",
        "checkin_topic_label": "Pick topic",
        "meditation_choose": "Choose a meditation length:",
        "checkin_start": (
            "Quick check-in — no wrong answers.\n\n"
            "How are you right now? Reply 1 (low) to 10 (great).\n\n"
            "/cancel anytime."
        ),
        "checkin_category_prompt": "What area is this mostly about? Pick below or reply 1–5.",
        "checkin_note_prompt": "Any short note? (Optional — reply 'skip')",
        "checkin_cancel": "Check-in cancelled. /help anytime.",
        "checkin_invalid_number": "Please reply with a whole number from 1 to 10.",
        "checkin_out_of_range": "Please use a number between 1 and 10.",
        "checkin_invalid_category": "Please choose a topic from the list.",
        "chat_intro": (
            "This is your space — say whatever's on your mind, no filter needed.\n"
            "I'll listen and respond thoughtfully."
        ),
        "chat_footer": "No commands needed — just talk. /done when you're ready to pause, /cancel to stop.",
        "chat_done": (
            "I'm glad you shared that. I'll remember the mood trends — "
            "come back anytime. /checkin or just say hi."
        ),
        "chat_cancel": "Chat paused. I'm here when you need me.",
        "chat_keep_going": "Keep going — or /done when you're ready.",
        "breathe_choose": (
            "Pick a pattern — each shows timing and about how long it takes.\n\n"
            "Tap a button below, or send /breathe calm | relaxation | energize"
        ),
        "breathe_not_found": "Pattern not found. Use: /breathe calm | relaxation | energize",
        "breathe_guide": (
            "*{name} breathing* ({duration} total)\n"
            "Inhale {inhale}s · hold {hold}s · exhale {exhale}s — {rounds} rounds.\n\n"
            "Go at your own pace. When you finish, notice how your body feels."
        ),
        "breathe_name_calm": "Calm",
        "breathe_name_relaxation": "Relaxation",
        "breathe_name_energize": "Energize",
    },
    "hi": {
        "welcome": (
            "नमस्ते — मैं आपका स्वास्थ्य साथी हूँ।\n\n"
            "चेक-इन, खुलकर बात, श्वास और ध्यान — थेरेपी नहीं।\n\n"
            "बताइए आप कैसे हैं, या मेनू खोलें।\n"
            "भाषा बदलने के लिए /language लिखें।"
        ),
        "language_pick": (
            "अपनी भाषा चुनें:\n\n"
            "मेनू और जवाब इसी भाषा में रहेंगे, जब तक /language या मेनू से *भाषा* न बदलें।"
        ),
        "language_invalid": "कृपया सूची से भाषा चुनें, या /language hindi | marathi | gujarati | bengali | english भेजें।",
        "help": (
            "स्वाभाविक रूप से बात करें या मेनू इस्तेमाल करें।\n\n"
            "• /checkin — मूड लॉग\n"
            "• बात करें — खुलकर बात\n"
            "• /summary — हफ्ते का सार\n"
            "• /language — भाषा बदलें"
        ),
        "menu_label": "स्वास्थ्य मेनू",
        "help_menu_label": "विकल्प",
        "lang_list_btn": "भाषा चुनें",
        "section_wellness": "स्वास्थ्य",
        "section_languages": "भाषाएँ",
        "checkin_topic_label": "विषय चुनें",
        "meditation_choose": "ध्यान की अवधि चुनें:",
        "checkin_start": (
            "छोटा चेक-इन — 1 (कम) से 10 (अच्छा) reply करें।\n\n"
            "कभी भी /cancel से रोकें।"
        ),
        "checkin_category_prompt": "यह किस क्षेत्र से जुड़ा है? नीचे विषय चुनें।",
        "checkin_note_prompt": "छोटा नोट? ('skip' लिखें)",
        "checkin_cancel": "चेक-इन रद्द। /help कभी भी।",
        "checkin_invalid_number": "1 से 10 के बीच संख्या लिखें।",
        "checkin_out_of_range": "1 से 10 के बीच संख्या use करें।",
        "checkin_invalid_category": "सूची से विषय चुनें।",
        "chat_intro": (
            "यह आपकी जगह है — जो मन में हो, बिना झिझक लिखिए।\n"
            "मैं ध्यान से सुनूँगा और जवाब दूँगा।"
        ),
        "chat_footer": "सीधे लिखिए — रोकने के लिए /done, बंद के लिए /cancel।",
        "chat_done": "शेयर करने के लिए धन्यवाद। /checkin या नमस्ते कह सकते हैं।",
        "chat_cancel": "चैट रोक दी। जब चाहें वापस आइए।",
        "chat_keep_going": "लिखते रहिए — या /done से रोकें।",
        "breathe_choose": (
            "पैटर्न चुनें — समय नीचे बटन पर दिखेगा।\n\n"
            "/breathe calm | relaxation | energize भी भेज सकते हैं।"
        ),
        "breathe_not_found": "पैटर्न नहीं मिला। /breathe calm | relaxation | energize",
        "breathe_guide": (
            "*{name} श्वास* ({duration} कुल)\n"
            "अंदर {inhale}s · रोक {hold}s · बाहर {exhale}s — {rounds} rounds.\n\n"
            "अपनी गति से करें। खत्म होने पर शरीर का एहसास नोट करें।"
        ),
        "breathe_name_calm": "शांत",
        "breathe_name_relaxation": "आराम",
        "breathe_name_energize": "ऊर्जा",
    },
    "mr": {
        "welcome": (
            "नमस्कार — मी तुमचा आरोग्य सोबती आहे.\n\n"
            "चेक-इन, मोकळं बोलणं, श्वास आणि ध्यान — थेरपी नाही.\n\n"
            "कसे आहात ते सांगा, किंवा मेनू उघडा.\n"
            "भाषा बदलण्यासाठी /language."
        ),
        "language_pick": (
            "तुमची भाषा निवडा:\n\n"
            "मेनू आणि उत्तरे या भाषेत राहतील, /language किंवा मेनूतील *भाषा* पर्यंत."
        ),
        "language_invalid": "कृपया सूचीतून भाषा निवडा, किंवा /language marathi | hindi | gujarati | bengali | english.",
        "help": (
            "स्वाभाविक बोला किंवा मेनू वापरा.\n\n"
            "• /checkin — मूड लॉग\n"
            "• बोलूया — मोकळं बोलणं\n"
            "• /summary — आठवड्याचा सार\n"
            "• /language — भाषा बदला"
        ),
        "menu_label": "आरोग्य मेनू",
        "help_menu_label": "पर्याय",
        "lang_list_btn": "भाषा निवडा",
        "section_wellness": "आरोग्य",
        "section_languages": "भाषा",
        "checkin_topic_label": "विषय निवडा",
        "meditation_choose": "ध्यानाची लांबी निवडा:",
        "checkin_start": (
            "छोटा चेक-इन — 1 (कमी) ते 10 (चांगले) reply करा.\n\n"
            "कधीही /cancel ने थांबवा."
        ),
        "checkin_category_prompt": "कोणत्या क्षेत्राबद्दल? खाली विषय निवडा.",
        "checkin_note_prompt": "लहान नोट? ('skip' लिहा)",
        "checkin_cancel": "चेक-इन रद्द. /help कधीही.",
        "checkin_invalid_number": "1 ते 10 दरम्यान संख्या लिहा.",
        "checkin_out_of_range": "1 ते 10 वापरा.",
        "checkin_invalid_category": "सूचीतून विषय निवडा.",
        "chat_intro": (
            "ही तुमची जागा आहे — मनात जे आहे ते मोकळेपणane सांगा.\n"
            "मी ऐकेन आणि विचारपूर्वक उत्तर देईन."
        ),
        "chat_footer": "थेट लिहा — थांबवण्यासाठी /done, बंद /cancel.",
        "chat_done": "शेअर केल्याबद्दल धन्यवाद. /checkin किंवा नमस्कार म्हणा.",
        "chat_cancel": "चॅट थांबवली. जेव्हा हवे तेव्हा परत या.",
        "chat_keep_going": "लिहित रaha — किंवा /done.",
        "breathe_choose": (
            "पॅटर्न निवडा — वेळ खाली बटणांवर.\n\n"
            "/breathe calm | relaxation | energize पण पाठवू शकता."
        ),
        "breathe_not_found": "पॅटर्न सापडला नाही. /breathe calm | relaxation | energize",
        "breathe_guide": (
            "*{name} श्वास* ({duration} एकूण)\n"
            "आत {inhale}s · थांब {hold}s · बाहेर {exhale}s — {rounds} rounds.\n\n"
            "तुमच्या गतीने. संपल्यावर शरीराची जाणीव करा."
        ),
        "breathe_name_calm": "शांत",
        "breathe_name_relaxation": "आराम",
        "breathe_name_energize": "ऊर्जा",
    },
    "gu": {
        "welcome": (
            "નમસ્તે — હું તમારો આરોગ્ય સાથી છું.\n\n"
            "ચેક-ઇન, ખુલ્લી વાત, શ્વાસ અને ધ્યાન — થેરાપી નહીં.\n\n"
            "કેવા છો કહો, અથવા મેનૂ ખોલો.\n"
            "ભાષા બદલવા /language."
        ),
        "language_pick": (
            "તમારી ભાષા પસંદ કરો:\n\n"
            "મેનૂ અને જવાબો આ ભાષામાં રહેશે, /language અથવા મેનૂ *ભાષા* સudhi."
        ),
        "language_invalid": "કૃપા કરી સૂચિમાંથી ભાષા પસંદ કરો, અથવા /language gujarati | hindi | marathi | bengali | english.",
        "help": (
            "સ્વાભાવિક વાત કરો અથવા મેનૂ વાપરો.\n\n"
            "• /checkin — મૂડ લોગ\n"
            "• વાત કરીએ — ખુલ્લી વાત\n"
            "• /summary — અઠવાડિયાનો સાર\n"
            "• /language — ભાષા બદલો"
        ),
        "menu_label": "આરોગ્ય મેનૂ",
        "help_menu_label": "વિકલ્પો",
        "lang_list_btn": "ભાષા પસંદ કરો",
        "section_wellness": "આરોગ્ય",
        "section_languages": "ભાષાઓ",
        "checkin_topic_label": "વિષય પસંદ કરો",
        "meditation_choose": "ધ્યાનની લંબાઈ પસંદ કરો:",
        "checkin_start": (
            "ટૂંકું ચેક-ઇન — 1 (ઓછું) થી 10 (સારું) reply કરો.\n\n"
            "ક્યારેય /cancel થી રોકો."
        ),
        "checkin_category_prompt": "કયા ક્ષેત્ર વિશે? નીચે વિષય પસંદ કરો.",
        "checkin_note_prompt": "ટૂંકો નોંધ? ('skip' લખો)",
        "checkin_cancel": "ચેક-ઇન રદ. /help ક્યારેય.",
        "checkin_invalid_number": "1 થી 10 વચ્ચે સંખ્યા.",
        "checkin_out_of_range": "1 થી 10 વાપરો.",
        "checkin_invalid_category": "સૂચિમાંથી વિષય પસંદ કરો.",
        "chat_intro": (
            "આ તમારી જગ્યા છે — મનમાં જે હોય ખુલ્લું કહો.\n"
            "હું સાંભળીશ અને વિચારપૂર્વક જવાબ આપીશ."
        ),
        "chat_footer": "સીધું લખો — રોકવા /done, બંધ /cancel.",
        "chat_done": "શેર કરવા બદલ આભાર. /checkin અથવા નમસ્તે કહો.",
        "chat_cancel": "ચેટ રોકાઈ. જ્યારે જોઈએ પાછા આવો.",
        "chat_keep_going": "લખતા રaho — અથવા /done.",
        "breathe_choose": (
            "પેટર્ન પસંદ કરો — સમય નીચે બટનો પર.\n\n"
            "/breathe calm | relaxation | energize પણ મોકલી શકો."
        ),
        "breathe_not_found": "પેટર્ન મળ્યું નહીં. /breathe calm | relaxation | energize",
        "breathe_guide": (
            "*{name} શ્વાસ* ({duration} કુલ)\n"
            "અંદર {inhale}s · રોક {hold}s · બહાર {exhale}s — {rounds} rounds.\n\n"
            "તમારી ગતિએ. પૂરું થયા પછી શરીરની જાણ લો."
        ),
        "breathe_name_calm": "શાંત",
        "breathe_name_relaxation": "આરામ",
        "breathe_name_energize": "ઊર્જા",
    },
    "bn": {
        "welcome": (
            "নমস্কার — আমি আপনার সুস্থতা সঙ্গী।\n\n"
            "চেক-ইন, খোলামেলা কথা, শ্বাস ও ধ্যান — থেরাপি নয়।\n\n"
            "কেমন আছেন জানান, অথবা মেনু খুলুন।\n"
            "ভাষা বদলতে /language।"
        ),
        "language_pick": (
            "আপনার ভাষা বেছে নিন:\n\n"
            "মেনু ও উত্তর এই ভাষায় থাকবে, /language বা মেনু *ভাষা* না বদলানো পর্যন্ত।"
        ),
        "language_invalid": "তালিকা থেকে ভাষা বেছে নিন, অথবা /language bengali | hindi | marathi | gujarati | english।",
        "help": (
            "স্বাভাবিকভাবে কথা বলুন বা মেনু ব্যবহার করুন।\n\n"
            "• /checkin — মুড লগ\n"
            "• কথা বলি — খোলামেলা কথা\n"
            "• /summary — সপ্তাহের সারাংশ\n"
            "• /language — ভাষা বদলান"
        ),
        "menu_label": "সুস্থতা মেনু",
        "help_menu_label": "বিকল্প",
        "lang_list_btn": "ভাষা বেছে নিন",
        "section_wellness": "সুস্থতা",
        "section_languages": "ভাষা",
        "checkin_topic_label": "বিষয় বেছে নিন",
        "meditation_choose": "ধ্যানের সময় বেছে নিন:",
        "checkin_start": (
            "ছোট চেক-ইন — 1 (কম) থেকে 10 (ভালো) reply করুন।\n\n"
            "যেকোনো সময় /cancel দিয়ে থামান।"
        ),
        "checkin_category_prompt": "কোন ক্ষেত্র নিয়ে? নিচে বিষয় বেছে নিন।",
        "checkin_note_prompt": "ছোট নোট? ('skip' লিখুন)",
        "checkin_cancel": "চেক-ইন বাতিল। /help যেকোনো সময়।",
        "checkin_invalid_number": "1 থেকে 10 এর মধ্যে সংখ্যা।",
        "checkin_out_of_range": "1 থেকে 10 ব্যবহার করুন।",
        "checkin_invalid_category": "তালিকা থেকে বিষয় বেছে নিন।",
        "chat_intro": (
            "এটা আপনার জায়গা — মনে যা আছে খোলামেলা বলুন।\n"
            "আমি শুনব এবং ভেবে উত্তর দেব।"
        ),
        "chat_footer": "সরাসরি লিখুন — থামাতে /done, বন্ধ /cancel।",
        "chat_done": "শেয়ার করার জন্য ধন্যবাদ। /checkin বা নমস্কার বলুন।",
        "chat_cancel": "চ্যাট থামানো। যখন ইচ্ছা ফিরে আসুন।",
        "chat_keep_going": "লিখতে থাকুন — অথবা /done।",
        "breathe_choose": (
            "প্যাটার্ন বেছে নিন — সময় নিচের বোতামে।\n\n"
            "/breathe calm | relaxation | energize ও পাঠাতে পারেন।"
        ),
        "breathe_not_found": "প্যাটার্ন পাওয়া যায়নি। /breathe calm | relaxation | energize",
        "breathe_guide": (
            "*{name} শ্বাস* ({duration} মোট)\n"
            "ভিতর {inhale}s · থাম {hold}s · বাইর {exhale}s — {rounds} rounds.\n\n"
            "নিজের গতিতে। শেষে শরীরের অনুভূতি লক্ষ্য করুন।"
        ),
        "breathe_name_calm": "শান্ত",
        "breathe_name_relaxation": "বিশ্রাম",
        "breathe_name_energize": "শক্তি",
    },
}

MENU_ROWS: Dict[str, List[Dict[str, str]]] = {
    "en": [
        {"id": "cmd_checkin", "title": "Check-in", "description": "Mood + topic"},
        {"id": "cmd_vent", "title": "Talk it out", "description": "Open chat"},
        {"id": "cmd_meditate", "title": "Meditate", "description": "3 / 10 / 20 min"},
        {"id": "cmd_breathe", "title": "Breathe", "description": "Calm · relax"},
        {"id": "cmd_affirmation", "title": "Affirmation", "description": "Boost"},
        {"id": "cmd_summary", "title": "My week", "description": "Trends"},
        {"id": "cmd_language", "title": "Language", "description": "English · Hindi · more"},
    ],
    "hi": [
        {"id": "cmd_checkin", "title": "चेक-इन", "description": "मूड + विषय"},
        {"id": "cmd_vent", "title": "बात करें", "description": "खुलकर बात"},
        {"id": "cmd_meditate", "title": "ध्यान", "description": "३ / १० / २० मि."},
        {"id": "cmd_breathe", "title": "श्वास", "description": "शांत · आराम"},
        {"id": "cmd_affirmation", "title": "प्रेरणा", "description": "हौसला"},
        {"id": "cmd_summary", "title": "मेरा हफ्ता", "description": "रुझान"},
        {"id": "cmd_language", "title": "भाषा", "description": "भाषा बदलें"},
    ],
    "mr": [
        {"id": "cmd_checkin", "title": "चेक-इन", "description": "मूड + विषय"},
        {"id": "cmd_vent", "title": "बोलूया", "description": "मोकळं बोलणं"},
        {"id": "cmd_meditate", "title": "ध्यान", "description": "३ / १० / २० मि."},
        {"id": "cmd_breathe", "title": "श्वास", "description": "शांत · आराम"},
        {"id": "cmd_affirmation", "title": "प्रेरणा", "description": "हौसला"},
        {"id": "cmd_summary", "title": "माझा आठवडा", "description": "प्रवृत्ती"},
        {"id": "cmd_language", "title": "भाषा", "description": "भाषा बदला"},
    ],
    "gu": [
        {"id": "cmd_checkin", "title": "ચેક-ઇન", "description": "મૂડ + વિષય"},
        {"id": "cmd_vent", "title": "વાત કરીએ", "description": "ખુલ્લી વાત"},
        {"id": "cmd_meditate", "title": "ધ્યાન", "description": "૩ / ૧૦ / ૨૦ મિ."},
        {"id": "cmd_breathe", "title": "શ્વાસ", "description": "શાંત · આરામ"},
        {"id": "cmd_affirmation", "title": "પ્રેરણા", "description": "હૌસલો"},
        {"id": "cmd_summary", "title": "મારો અઠવાડિયો", "description": "વલણ"},
        {"id": "cmd_language", "title": "ભાષા", "description": "ભાષા બદલો"},
    ],
    "bn": [
        {"id": "cmd_checkin", "title": "চেক-ইন", "description": "মুড + বিষয়"},
        {"id": "cmd_vent", "title": "কথা বলি", "description": "খোলামেলা কথা"},
        {"id": "cmd_meditate", "title": "ধ্যান", "description": "৩ / ১০ / ২০ মি."},
        {"id": "cmd_breathe", "title": "শ্বাস", "description": "শান্ত · বিশ্রাম"},
        {"id": "cmd_affirmation", "title": "অনুপ্রেরণা", "description": "উৎসাহ"},
        {"id": "cmd_summary", "title": "আমার সপ্তাহ", "description": "প্রবণতা"},
        {"id": "cmd_language", "title": "ভাষা", "description": "ভাষা বদলান"},
    ],
}

MEDITATION_BUTTONS_I18N: Dict[str, ButtonList] = {
    "en": [("med_quick", "Quick (3 min)"), ("med_medium", "Medium (10m)"), ("med_long", "Long (20 min)")],
    "hi": [("med_quick", "छोटा (३ मि.)"), ("med_medium", "मध्यम (१० मि.)"), ("med_long", "लंबा (२० मि.)")],
    "mr": [("med_quick", "छोटा (३ मि.)"), ("med_medium", "मध्यम (१० मि.)"), ("med_long", "लांब (२० मि.)")],
    "gu": [("med_quick", "ટૂંકું (૩ મિ.)"), ("med_medium", "મધ્યમ (૧૦ મિ.)"), ("med_long", "લાંબું (૨૦ મિ.)")],
    "bn": [("med_quick", "ছোট (৩ মি.)"), ("med_medium", "মাঝারি (১০ মি.)"), ("med_long", "দীর্ঘ (২০ মি.)")],
}

BREATHE_BUTTONS_I18N: Dict[str, ButtonList] = {
    "en": [("breathe_calm", "Calm"), ("breathe_relaxation", "Relaxation"), ("breathe_energize", "Energize")],
    "hi": [("breathe_calm", "शांत"), ("breathe_relaxation", "आराम"), ("breathe_energize", "ऊर्जा")],
    "mr": [("breathe_calm", "शांत"), ("breathe_relaxation", "आराम"), ("breathe_energize", "ऊर्जा")],
    "gu": [("breathe_calm", "શાંત"), ("breathe_relaxation", "આરામ"), ("breathe_energize", "ઊર્જા")],
    "bn": [("breathe_calm", "শান্ত"), ("breathe_relaxation", "বিশ্রাম"), ("breathe_energize", "শক্তি")],
}

CHAT_FOLLOWUP_I18N: Dict[str, ButtonList] = {
    "en": [("vent_done", "Pause chat"), ("cmd_breathe", "Breathe"), ("cmd_checkin", "Check-in")],
    "hi": [("vent_done", "चैट रोकें"), ("cmd_breathe", "श्वास"), ("cmd_checkin", "चेक-इन")],
    "mr": [("vent_done", "चॅट थांबवा"), ("cmd_breathe", "श्वास"), ("cmd_checkin", "चेक-इन")],
    "gu": [("vent_done", "ચેટ રોકો"), ("cmd_breathe", "શ્વાસ"), ("cmd_checkin", "ચેક-ઇન")],
    "bn": [("vent_done", "চ্যাট থামান"), ("cmd_breathe", "শ্বাস"), ("cmd_checkin", "চেক-ইন")],
}

CHECKIN_CATEGORIES_I18N: Dict[str, List[Dict[str, str]]] = {
    "en": [
        {"id": "cat_work", "title": "Work", "description": "Job / career"},
        {"id": "cat_health", "title": "Health", "description": "Body / mind"},
        {"id": "cat_relationships", "title": "Relationships", "description": "Family"},
        {"id": "cat_studies", "title": "Studies", "description": "School"},
        {"id": "cat_other", "title": "Other", "description": "Other"},
    ],
    "hi": [
        {"id": "cat_work", "title": "काम", "description": "नौकरी / करियर"},
        {"id": "cat_health", "title": "स्वास्थ्य", "description": "शरीर / मन"},
        {"id": "cat_relationships", "title": "रिश्ते", "description": "परिवार"},
        {"id": "cat_studies", "title": "पढ़ाई", "description": "स्कूल / परीक्षा"},
        {"id": "cat_other", "title": "अन्य", "description": "कुछ और"},
    ],
    "mr": [
        {"id": "cat_work", "title": "काम", "description": "नोकरी / करिअर"},
        {"id": "cat_health", "title": "आरोग्य", "description": "शरीर / मन"},
        {"id": "cat_relationships", "title": "नाते", "description": "कुटुंब"},
        {"id": "cat_studies", "title": "अभ्यास", "description": "शाळा / परीक्षा"},
        {"id": "cat_other", "title": "इतर", "description": "काहीही"},
    ],
    "gu": [
        {"id": "cat_work", "title": "કામ", "description": "નોકરી / કેરિયર"},
        {"id": "cat_health", "title": "આરોગ્ય", "description": "શરીર / મન"},
        {"id": "cat_relationships", "title": "સંબંધ", "description": "પરિવાર"},
        {"id": "cat_studies", "title": "અભ્યાસ", "description": "શાળા / પરીક્ષા"},
        {"id": "cat_other", "title": "અન્ય", "description": "બીજું કંઈક"},
    ],
    "bn": [
        {"id": "cat_work", "title": "কাজ", "description": "চাকরি / ক্যারিয়ার"},
        {"id": "cat_health", "title": "স্বাস্থ্য", "description": "শরীর / মন"},
        {"id": "cat_relationships", "title": "সম্পর্ক", "description": "পরিবার"},
        {"id": "cat_studies", "title": "পড়াশোনা", "description": "স্কুল / পরীক্ষা"},
        {"id": "cat_other", "title": "অন্যান্য", "description": "অন্য কিছু"},
    ],
}


def normalize_lang(code: Optional[str]) -> str:
    if not code:
        return DEFAULT_LANG
    code = code.strip().lower()
    if code.startswith("lang_"):
        code = code[5:]
    if code in LANG_ALIASES:
        code = LANG_ALIASES[code]
    return code if code in SUPPORTED else DEFAULT_LANG


def parse_language_choice(raw: str) -> Optional[str]:
    key = (raw or "").strip().lower()
    if key.startswith("lang_"):
        lang = normalize_lang(key)
        return lang if lang in SUPPORTED else None
    if key in LANG_ALIASES:
        return LANG_ALIASES[key]
    if key in SUPPORTED:
        return key
    return None


def list_row_count(sections: List[Dict[str, Any]]) -> int:
    return sum(len(section.get("rows") or []) for section in sections)


def language_list_sections(user_phone: str = "") -> List[Dict[str, Any]]:
    title = t(user_phone, "section_languages") if user_phone else "Languages"
    return [
        {
            "title": title,
            "rows": [
                {"id": f"lang_{code}", "title": native, "description": english}
                for code, native, english in LANGUAGES
            ],
        }
    ]


def language_picker_reply(user_phone: str) -> BotReply:
    return BotReply(
        t(user_phone, "language_pick"),
        list_button_label=t(user_phone, "lang_list_btn"),
        list_sections=language_list_sections(user_phone),
    )


def language_set_message(lang: str) -> str:
    lang = normalize_lang(lang)
    return LANG_SET_MSG.get(lang, f"Language set to {LLM_LANG.get(lang, lang)}.")


def get_user_language(user_phone: str) -> Optional[str]:
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "SELECT preferred_language FROM users WHERE phone_number = ?",
            (user_phone,),
        )
        row = c.fetchone()
    finally:
        conn.close()
    if not row or row[0] is None or str(row[0]).strip() == "":
        return None
    return normalize_lang(row[0])


def effective_language(user_phone: str) -> str:
    """Stored preference only — never auto-detected from message text."""
    stored = get_user_language(user_phone)
    return stored if stored else DEFAULT_LANG


def set_user_language(user_phone: str, lang: str) -> str:
    from datetime import datetime

    lang = normalize_lang(lang)
    conn = connect()
    try:
        c = conn.cursor()
        execute(
            c,
            "UPDATE users SET preferred_language = ? WHERE phone_number = ?",
            (lang, user_phone),
        )
        if c.rowcount == 0:
            execute(
                c,
                """INSERT INTO users (phone_number, joined_date, preferred_language)
                   VALUES (?, ?, ?)""",
                (user_phone, datetime.now(), lang),
            )
        conn.commit()
    finally:
        conn.close()
    return lang


def t(user_phone: str, key: str, **fmt: str) -> str:
    lang = effective_language(user_phone)
    bucket = STRINGS.get(lang) or STRINGS["en"]
    text = bucket.get(key, STRINGS["en"].get(key, key))
    if fmt:
        return text.format(**fmt)
    return text


def llm_language_directive(user_phone: str) -> str:
    lang = effective_language(user_phone)
    name = LLM_LANG.get(lang, "English")
    return (
        f"IMPORTANT: Reply entirely in {name}. Never switch to English unless the user "
        "explicitly asks. Keep 2-4 short WhatsApp-friendly sentences."
    )


def main_menu_sections(user_phone: str) -> List[Dict[str, Any]]:
    lang = effective_language(user_phone)
    rows = MENU_ROWS.get(lang) or MENU_ROWS["en"]
    return [{"title": t(user_phone, "section_wellness"), "rows": rows}]


def meditation_buttons(user_phone: str) -> ButtonList:
    return MEDITATION_BUTTONS_I18N[effective_language(user_phone)]


def breathe_buttons(user_phone: str) -> ButtonList:
    return BREATHE_BUTTONS_I18N[effective_language(user_phone)]


def chat_followup_buttons(user_phone: str) -> ButtonList:
    return CHAT_FOLLOWUP_I18N[effective_language(user_phone)]


def checkin_category_list(user_phone: str) -> List[Dict[str, Any]]:
    lang = effective_language(user_phone)
    rows = CHECKIN_CATEGORIES_I18N.get(lang) or CHECKIN_CATEGORIES_I18N["en"]
    return [{"title": t(user_phone, "checkin_topic_label"), "rows": rows}]

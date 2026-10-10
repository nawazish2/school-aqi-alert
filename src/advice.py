"""Turn an AQI reading into a short instruction for the principal (English / Hindi).

Rules always work. If ADVICE_MODEL_ID is set, a Strands agent on Bedrock
rewrites the English advice; any failure falls back to the rules.
"""
import os

# (max AQI, English action, Hindi action)
RULES = [
    (50, "Air is fine. Normal outdoor activities.",
         "हवा ठीक है। सामान्य गतिविधियाँ जारी रखें।"),
    (100, "Acceptable. Sensitive students (asthma) should limit heavy exercise.",
          "हवा सामान्य है। अस्थमा वाले बच्चे भारी व्यायाम कम करें।"),
    (150, "Move PT and sports indoors for sensitive students. Keep asthma inhalers handy.",
          "संवेदनशील बच्चों की PT और खेल घर के अंदर कराएँ। इन्हेलर पास रखें।"),
    (200, "Cancel outdoor PT, assembly and sports. Keep students indoors at break.",
          "बाहर की PT, असेंबली और खेल रद्द करें। ब्रेक में बच्चों को अंदर रखें।"),
    (300, "Cancel all outdoor activities. Keep windows shut and run purifiers if available.",
          "सभी बाहरी गतिविधियाँ रद्द करें। खिड़कियाँ बंद रखें, प्यूरीफायर चलाएँ।"),
    (10**6, "Hazardous air. Consider closing school or going online. Keep everyone indoors.",
            "हवा बेहद खतरनाक है। स्कूल बंद करने या ऑनलाइन कक्षा पर विचार करें।"),
]

LANGS = ("en", "hi", "both")


def _rule(aqi: int):
    for rule in RULES:
        if aqi <= rule[0]:
            return rule
    return RULES[-1]


def rule_advice(aqi: int) -> str:
    return _rule(aqi)[1]


def rule_advice_hi(aqi: int) -> str:
    return _rule(aqi)[2]


def _agent_advice(school: str, aqi: int, category: str, base: str, model_id: str) -> str:
    from strands import Agent
    from strands.models import BedrockModel

    agent = Agent(
        model=BedrockModel(model_id=model_id),
        system_prompt=(
            "You write one SMS (max 220 characters) for a school principal. "
            "Be direct, no emojis, no markdown. Start with the action."
        ),
    )
    prompt = (
        f"School: {school}. AQI {aqi} ({category}). "
        f"Baseline guidance: {base} Rewrite as the SMS."
    )
    return str(agent(prompt)).strip()


def _english(school: str, aqi: int, category: str) -> str:
    base = rule_advice(aqi)
    model_id = os.environ.get("ADVICE_MODEL_ID", "")
    text = base
    if model_id:
        try:
            text = _agent_advice(school, aqi, category, base, model_id) or base
        except Exception as exc:  # agent is optional; never block the alert
            print(f"agent advice failed, using rules: {exc}")
    return f"AQI Alert - {school}: AQI {aqi} ({category}). {text}"[:300]


def _hindi(school: str, aqi: int) -> str:
    return f"AQI अलर्ट - {school}: AQI {aqi}। {rule_advice_hi(aqi)}"[:300]


def build_message(school: str, aqi: int, category: str, lang: str = "en") -> str:
    if lang == "hi":
        return _hindi(school, aqi)
    if lang == "both":
        return f"{_english(school, aqi, category)}\n{_hindi(school, aqi)}"
    return _english(school, aqi, category)

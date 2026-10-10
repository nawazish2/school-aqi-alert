"""Turn an AQI reading into a short instruction for the principal.

Rules always work. If ADVICE_MODEL_ID is set, a Strands agent on Bedrock
rewrites the advice; any failure falls back to the rules.
"""
import os

# (max AQI, action)
RULES = [
    (50, "Air is fine. Normal outdoor activities."),
    (100, "Acceptable. Sensitive students (asthma) should limit heavy exercise."),
    (150, "Move PT and sports indoors for sensitive students. Keep asthma inhalers handy."),
    (200, "Cancel outdoor PT, assembly and sports. Keep students indoors at break."),
    (300, "Cancel all outdoor activities. Keep windows shut and run purifiers if available."),
    (10**6, "Hazardous air. Consider closing school or going online. Keep everyone indoors."),
]


def rule_advice(aqi: int) -> str:
    for upper, text in RULES:
        if aqi <= upper:
            return text
    return RULES[-1][1]


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


def build_message(school: str, aqi: int, category: str) -> str:
    base = rule_advice(aqi)
    model_id = os.environ.get("ADVICE_MODEL_ID", "")
    text = base
    if model_id:
        try:
            text = _agent_advice(school, aqi, category, base, model_id) or base
        except Exception as exc:  # agent is optional; never block the alert
            print(f"agent advice failed, using rules: {exc}")
    return f"AQI Alert - {school}: AQI {aqi} ({category}). {text}"[:300]

"""
Targeted RU re-translation — fix LLM cross-lingual contamination.

Identifies entries where ru == uk (clear sign LLM emitted UK in both
slots) and re-translates JUST the RU side via a tight RU-only chat.
"""
from __future__ import annotations
import asyncio, json, os, re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from emergentintegrations.llm.chat import LlmChat, UserMessage

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
P = Path("/app/backend/scripts/hardcoded_extract/_translations.json")

RU_LAW = """
You translate UI strings to RUSSIAN ONLY for a cognitive trading
infrastructure with TRUTHFUL DEGRADATION law. Output JSON only.

Forbidden RU vocabulary:
  сигнал, сделка, прибыль, профит, альфа, точка входа, гарантировано,
  высокоточный, агрессивный, максимальный профит, HODL, мунить, шортить.

Preferred RU vocabulary:
  структура, выравнивание, давление, контекст, наблюдение, режим,
  сжатие/расширение, сдержанность, неопределённость, ясность.

Brand invariants (do NOT translate): FOMO, Trading OS, PRO, FREE,
Telegram, BTC, ETH, SOL, USDT, USD, Stripe, NOWPayments.

Length close to source. Preserve {placeholders}. Mobile UI conventions.

Output JSON ONLY: { key: ru_translation }. No commentary.
"""


async def main():
    data = json.loads(P.read_text())
    bad = {k: m["en"] for k, m in data.items() if m["ru"] == m["uk"]}
    if not bad:
        print("No contamination detected.")
        return
    print(f"Contaminated RU entries: {len(bad)}")
    for k in bad: print(f"  {k}: ru={data[k]['ru']!r}")

    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id="ru-fix-7b2",
                   system_message=RU_LAW).with_model(
        "anthropic", "claude-sonnet-4-5-20250929")
    prompt = ("Translate to Russian only. Output JSON {key: ru}.\n\n"
              + json.dumps(bad, ensure_ascii=False, indent=2))
    resp = await chat.send_message(UserMessage(text=prompt))
    text = resp.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    fixes = json.loads(text)
    for k, ru in fixes.items():
        if k in data and isinstance(ru, str) and ru.strip():
            data[k]["ru"] = ru
            print(f"  fixed: {k} → {ru}")
    P.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\nWrote {len(fixes)} RU fixes.")


if __name__ == "__main__":
    asyncio.run(main())

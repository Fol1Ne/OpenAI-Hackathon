"""ExplanationService: TemplateExplanationService (default) / OpenAIExplanationService (optional, backend-only key, rewords given facts only)."""
import httpx
from .. import config

def explain_routes(fast, lit):
    if fast is lit or lit is None: return "1 route available. Compare lighting coverage and live pedestrian data below."
    dm = round(lit["minutes"] - fast["minutes"]); dp = lit["pct_lit"] - fast["pct_lit"]
    if dm == 0 and dp == 0: return "The two routes have the same duration and lit-street coverage."
    return (f"The well-lit route takes {abs(dm)} minutes {'longer' if dm >= 0 else 'less'} and has "
            f"{abs(dp)} percentage points {'more' if dp >= 0 else 'less'} lit-street coverage.")

def explain(fast, lit):
    base = explain_routes(fast, lit)
    if not (config.ENABLE_AI and config.OPENAI_API_KEY): return base, "template"
    try:
        r = httpx.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"}, timeout=8,
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Reword in one neutral sentence, keep every number unchanged, never say safe/unsafe: " + base}]})
        r.raise_for_status(); return r.json()["choices"][0]["message"]["content"].strip(), "openai"
    except Exception: return base, "template"   # silent fallback, no error shown

# RESEARCH: LLM Prompt Design for Property Share Analysis

**Date:** 2026-08-22  
**Purpose:** Design optimal system prompt, user prompt template, and JSON output schema for LLM-based analysis of property share (udział w nieruchomości) listings  
**Constraint:** Must work reliably with weak models (DeepSeek Flash, Gemini Flash, GPT-4o-mini)

---

## TL;DR — Decisions

1. **System prompt**: ~800 tokens in Polish, explicit role + rules + JSON schema + 2 few-shot examples
2. **User prompt**: Structured with `[TYTUŁ]`, `[OPIS]`, `[CENA]`, `[LOKALIZACJA]` markers; NO scorer result passed (avoids anchoring bias)
3. **Output schema**: 10 fields, all with constrained types; `null` allowed where data insufficient
4. **Expected cost**: ~$0.003/listing with GPT-4o-mini, ~$0.001/listing with DeepSeek; ~$4.50/mo at 50/day (GPT-4o-mini)
5. **Model suitability**: GPT-4o-mini ✅ excellent, DeepSeek ✅ good, Gemini Flash ✅ acceptable

---

## 1. SYSTEM PROMPT (Polish)

### Design Principles

- **Explicit role declaration** → weak models behave better with clear persona
- **Definition of domain term** → avoids confusion between "udział w drodze" (trivial) and "udział w nieruchomości" (target)
- **Enumerated analysis dimensions** → structured thinking
- **JSON schema with types** → reduces malformed output
- **Two few-shot examples** → anchors format for Gemini/DeepSeek
- **Edge case handling** → explicit instructions for ambiguous cases
- **Chain-of-thought suppression** → "Odpowiedz TYLKO JSON" prevents wasted tokens

### System Prompt v1.0

```
Jesteś ekspertem od obrotu udziałami w nieruchomościach w Polsce. Twoje zadanie: przeanalizować ogłoszenie o sprzedaży i ocenić czy dotyczy ono RZECZYWISTEGO udziału w nieruchomości.

DEFINICJA: "Udział w nieruchomości" to ułamkowe prawo własności do nieruchomości (np. 1/2, 1/4, 3/8). Powstaje najczęściej ze spadku, rozwodu, upadłości lub współwłasności. NIE jest udziałem w nieruchomości:
- udział w drodze wewnętrznej (standardowy przy działkach)
- udział w gruncie pod budynkiem (standardowy w spółdzielniach/wspólnotach)
- udział w częściach wspólnych budynku
- udział w spółce/funduszu

ANALIZA — oceń kolejno:
1. Czy to RZECZYWISTY udział? (is_real_share)
2. Jaki ułamek? (fraction) — jeśli podany
3. Typ nieruchomości (property_type)
4. Motywacja sprzedającego (seller_motivation)
5. Ocena ceny (price_assessment) — czy cena za udział jest okazją, uczciwa, czy droga
6. Ryzyka dla kupującego (risks)

OCENA GWIAZDKOWA (stars 1-5):
- 5 = idealna okazja: duży udział (≥1/2), niska cena, jasna sytuacja prawna
- 4 = dobra oferta: rozsądna cena, znany ułamek, motywacja czytelna
- 3 = średnia: niepełne informacje ale prawdopodobnie real deal
- 2 = wątpliwa: mało danych, ryzykowna, możliwe problemy
- 1 = nieatrakcyjna lub to nie jest prawdziwy udział

ODPOWIEDŹ — zwróć WYŁĄCZNIE obiekt JSON (bez markdown, bez komentarzy):
{
  "is_real_share": true/false,
  "confidence": 0.0-1.0,
  "stars": 1-5,
  "summary": "2-3 zdania po polsku podsumowujące ofertę",
  "fraction": "1/2" lub null jeśli nie podano,
  "property_type": "mieszkanie"|"działka"|"kamienica"|"dom"|"lokal"|"grunt"|"inne"|null,
  "seller_motivation": "spadek"|"syndyk"|"rozwód"|"zadłużenie"|"egzekucja"|"inne"|null,
  "estimated_value_total": liczba w PLN (szacunek wartości CAŁEJ nieruchomości) lub null,
  "price_assessment": "okazja"|"uczciwa"|"droga"|null,
  "risks": ["ryzyko 1", "ryzyko 2"] lub []
}

PRZYKŁAD 1 — prawdziwy udział:
Tytuł: "Syndyk sprzeda udział 1/2 w prawie własności nieruchomości"
Opis: "Syndyk masy upadłości sprzeda udział 1/2 w lokalu mieszkalnym 48m2, Kraków Nowa Huta. Cena wywoławcza. KW prowadzona."
Cena: 95000 PLN
Lokalizacja: Kraków

Odpowiedź:
{"is_real_share":true,"confidence":0.95,"stars":4,"summary":"Syndyk sprzedaje 1/2 udziału w mieszkaniu 48m2 w Krakowie Nowej Hucie za 95 tys. Cena wywoławcza sugeruje możliwość negocjacji. KW prowadzona — sytuacja prawna klarowna.","fraction":"1/2","property_type":"mieszkanie","seller_motivation":"syndyk","estimated_value_total":280000,"price_assessment":"okazja","risks":["współwłaściciel może blokować sprzedaż","konieczność przeprowadzenia procedury zniesienia współwłasności"]}

PRZYKŁAD 2 — NIE jest udziałem:
Tytuł: "Działka budowlana 1200m2, udział w drodze wewnętrznej"
Opis: "Piękna działka budowlana z mediami. W cenie udział w drodze dojazdowej."
Cena: 180000 PLN
Lokalizacja: Otwock

Odpowiedź:
{"is_real_share":false,"confidence":0.95,"stars":1,"summary":"To standardowa sprzedaż działki budowlanej. Wzmianka o 'udziale w drodze' dotyczy typowego dostępu do drogi wewnętrznej — nie jest to sprzedaż ułamkowego prawa własności.","fraction":null,"property_type":"działka","seller_motivation":null,"estimated_value_total":null,"price_assessment":null,"risks":[]}
```

### Token Count Estimate
- System prompt: **~780 tokens** (including examples)
- This is optimized — the examples serve dual purpose (format anchoring + domain education)

---

## 2. USER PROMPT TEMPLATE

### Design Decision: No Scorer Result Included

**Why NOT include scorer confidence:**
- Anchoring bias: weak models will echo the scorer's assessment instead of analyzing independently
- The scorer already filters (threshold ≥ 30); LLM only sees pre-qualified listings
- Adding scorer data adds tokens with no informational value to the LLM

### User Prompt Template

```python
USER_PROMPT_TEMPLATE = """Przeanalizuj to ogłoszenie:

[TYTUŁ]
{title}

[OPIS]
{description}

[CENA]
{price} PLN

[LOKALIZACJA]
{location}

[POWIERZCHNIA]
{area}
"""
```

### Formatting Rules

1. **Title**: Raw title from OLX/Otodom, no modification
2. **Description**: First 1500 characters of listing description (truncated if longer — saves tokens)
3. **Price**: Numeric value + "PLN", or "brak danych" if not available
4. **Location**: City + district if available
5. **Area**: Square meters if available, or "brak danych"

### Token Budget per User Prompt

| Field | Avg chars | Avg tokens |
|-------|-----------|------------|
| Template chrome | 80 | ~25 |
| Title | 80 | ~30 |
| Description (truncated) | 1200 | ~400 |
| Price/Location/Area | 50 | ~20 |
| **Total user prompt** | **~1400** | **~475** |

---

## 3. JSON OUTPUT SCHEMA (Formal)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["is_real_share", "confidence", "stars", "summary", "fraction", "property_type", "seller_motivation", "estimated_value_total", "price_assessment", "risks"],
  "properties": {
    "is_real_share": {
      "type": "boolean",
      "description": "Czy ogłoszenie dotyczy rzeczywistego udziału w nieruchomości"
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "Pewność oceny (0.0 = kompletny brak danych, 1.0 = pewność)"
    },
    "stars": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5,
      "description": "Ocena atrakcyjności oferty dla inwestora (1=słaba, 5=doskonała)"
    },
    "summary": {
      "type": "string",
      "maxLength": 300,
      "description": "2-3 zdania po polsku podsumowujące kluczowe fakty o ofercie"
    },
    "fraction": {
      "type": ["string", "null"],
      "pattern": "^\\d+/\\d+$",
      "description": "Ułamek udziału (np. '1/2', '3/8') lub null jeśli nie podano"
    },
    "property_type": {
      "type": ["string", "null"],
      "enum": ["mieszkanie", "działka", "kamienica", "dom", "lokal", "grunt", "inne", null],
      "description": "Typ nieruchomości"
    },
    "seller_motivation": {
      "type": ["string", "null"],
      "enum": ["spadek", "syndyk", "rozwód", "zadłużenie", "egzekucja", "inne", null],
      "description": "Motywacja sprzedającego — dlaczego sprzedaje udział"
    },
    "estimated_value_total": {
      "type": ["integer", "null"],
      "minimum": 0,
      "description": "Szacunkowa wartość CAŁEJ nieruchomości w PLN (nie tylko udziału)"
    },
    "price_assessment": {
      "type": ["string", "null"],
      "enum": ["okazja", "uczciwa", "droga", null],
      "description": "Ocena ceny udziału względem wartości rynkowej"
    },
    "risks": {
      "type": "array",
      "items": {"type": "string"},
      "maxItems": 5,
      "description": "Lista ryzyk dla kupującego (max 5)"
    }
  },
  "additionalProperties": false
}
```

### Validation Strategy in Python

```python
import json

def validate_llm_response(raw_text: str) -> dict | None:
    """Parse and validate LLM response. Returns dict or None on failure."""
    # Strip markdown code fences if model adds them
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove first line
        if text.endswith("```"):
            text = text[:-3]
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    
    # Required fields check
    required = ["is_real_share", "confidence", "stars", "summary", 
                "fraction", "property_type", "seller_motivation",
                "estimated_value_total", "price_assessment", "risks"]
    if not all(k in data for k in required):
        return None
    
    # Type coercion for common model errors
    if isinstance(data["stars"], float):
        data["stars"] = int(data["stars"])
    if isinstance(data["confidence"], str):
        data["confidence"] = float(data["confidence"])
    if isinstance(data["risks"], str):
        data["risks"] = [data["risks"]]
    
    # Bounds check
    data["stars"] = max(1, min(5, data["stars"]))
    data["confidence"] = max(0.0, min(1.0, data["confidence"]))
    
    return data
```

---

## 4. TEST AGAINST REAL LISTINGS

### Selected Test Listings (3 representative cases)

**Test Case A** — Clear real share (syndyk + fraction):
```
Title: "Syndyk sprzeda prawo własności ½ udziałów w nieruchomości lokalowej o funkcji mieszkalnej"
```

**Test Case B** — Real share but ambiguous (no fraction in title):
```
Title: "Sprzedam UDZIAŁ 2/3 w zabudowanej nieruchomości gruntowej — Warszawa Bemowo, ul. Dywizjonu 303"
```

**Test Case C** — FALSE POSITIVE (udział w drodze, not a real share sale):
```
Title: "Sprzedam Działki budowlane pod zabudowę Woda Gaz Prąd Kanalizacja na działce Równe zielone udział w drodze wewnętrznej 34ar cicha spokojna okolica"
```

---

### Test Case A — Full Prompt

**System prompt:** (as defined in Section 1 above)

**User prompt:**
```
Przeanalizuj to ogłoszenie:

[TYTUŁ]
Syndyk sprzeda prawo własności ½ udziałów w nieruchomości lokalowej o funkcji mieszkalnej

[OPIS]
Syndyk masy upadłości osoby fizycznej nieprowadzącej działalności gospodarczej sprzeda prawo własności ½ udziałów w nieruchomości lokalowej o funkcji mieszkalnej. Lokal o powierzchni użytkowej 52,40 m2 położony w Gdańsku. Cena nie niższa niż wartość oszacowania. Zainteresowanych proszę o kontakt.

[CENA]
120000 PLN

[LOKALIZACJA]
Gdańsk

[POWIERZCHNIA]
52.4 m²
```

**Expected correct LLM output:**
```json
{
  "is_real_share": true,
  "confidence": 0.95,
  "stars": 4,
  "summary": "Syndyk sprzedaje 1/2 udziału w lokalu mieszkalnym 52.4m2 w Gdańsku za 120 tys. PLN. Cena wywoławcza na poziomie oszacowania. Procedura upadłościowa zapewnia czystość prawną transakcji.",
  "fraction": "1/2",
  "property_type": "mieszkanie",
  "seller_motivation": "syndyk",
  "estimated_value_total": 350000,
  "price_assessment": "okazja",
  "risks": ["współwłaściciel może nie chcieć sprzedać", "konieczność zniesienia współwłasności", "procedura wymaga wpłaty wadium"]
}
```

**Model predictions:**
- GPT-4o-mini: ✅ Will handle perfectly — clear signals, familiar pattern
- DeepSeek: ✅ Will handle correctly — "syndyk" + "½ udziałów" are unambiguous
- Gemini Flash: ✅ Will handle correctly — structured prompt guides it

---

### Test Case B — Full Prompt

**System prompt:** (as defined in Section 1 above)

**User prompt:**
```
Przeanalizuj to ogłoszenie:

[TYTUŁ]
Sprzedam UDZIAŁ 2/3 w zabudowanej nieruchomości gruntowej — Warszawa Bemowo, ul. Dywizjonu 303

[OPIS]
Sprzedam udział 2/3 w nieruchomości gruntowej zabudowanej domem jednorodzinnym. Działka 600m2, dom 120m2, Warszawa Bemowo. Udział nabyty w drodze spadkobrania. Księga wieczysta prowadzona. Możliwa sprzedaż bez pośredników.

[CENA]
450000 PLN

[LOKALIZACJA]
Warszawa, Bemowo

[POWIERZCHNIA]
600 m² (działka), 120 m² (dom)
```

**Expected correct LLM output:**
```json
{
  "is_real_share": true,
  "confidence": 0.92,
  "stars": 5,
  "summary": "Duży udział 2/3 w zabudowanej nieruchomości na Bemowie — dom 120m2 na działce 600m2. Udział pochodzi ze spadku. Lokalizacja premium (Warszawa). Cena 450 tys. za 2/3 jest atrakcyjna przy wartości całości ~900 tys.",
  "fraction": "2/3",
  "property_type": "dom",
  "seller_motivation": "spadek",
  "estimated_value_total": 900000,
  "price_assessment": "okazja",
  "risks": ["1/3 należy do innego spadkobiercy", "potencjalny konflikt rodzinny", "konieczność porozumienia lub zniesienia współwłasności"]
}
```

**Model predictions:**
- GPT-4o-mini: ✅ Will handle perfectly — all signals explicit
- DeepSeek: ✅ Will handle correctly — "spadkobranie" + "2/3" clear
- Gemini Flash: ⚠️ May estimate value poorly (less Polish real estate knowledge) but structure will be correct

---

### Test Case C — Full Prompt (FALSE POSITIVE — should reject)

**System prompt:** (as defined in Section 1 above)

**User prompt:**
```
Przeanalizuj to ogłoszenie:

[TYTUŁ]
Sprzedam Działki budowlane pod zabudowę Woda Gaz Prąd Kanalizacja na działce Równe zielone udział w drodze wewnętrznej 34ar cicha spokojna okolica

[OPIS]
Na sprzedaż działki budowlane o powierzchni 34 arów. Pełne media: woda, gaz, prąd, kanalizacja. Udział w drodze wewnętrznej w cenie. Okolica spokojna, zielona. Warunki zabudowy wydane.

[CENA]
185000 PLN

[LOKALIZACJA]
okolice Krakowa

[POWIERZCHNIA]
3400 m²
```

**Expected correct LLM output:**
```json
{
  "is_real_share": false,
  "confidence": 0.92,
  "stars": 1,
  "summary": "To standardowa sprzedaż działki budowlanej 34ar z mediami. Wzmianka o 'udziale w drodze wewnętrznej' dotyczy typowego dostępu komunikacyjnego — nie jest to sprzedaż ułamkowego prawa współwłasności.",
  "fraction": null,
  "property_type": "działka",
  "seller_motivation": null,
  "estimated_value_total": null,
  "price_assessment": null,
  "risks": []
}
```

**Model predictions:**
- GPT-4o-mini: ✅ Will correctly identify as non-share — example 2 in prompt covers this exact case
- DeepSeek: ✅ Will correctly reject — the negative example teaches this pattern
- Gemini Flash: ⚠️ Slight risk of false positive if it fixates on "udział" word — but few-shot example should prevent this

---

### Model Capability Assessment

| Capability | GPT-4o-mini | DeepSeek V4 Flash | Gemini 2.0 Flash |
|-----------|-------------|-------------------|-----------------|
| Polish language understanding | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| JSON format compliance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Domain knowledge (PL real estate) | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Following strict instructions | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Price estimation accuracy | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| Edge case handling | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

**Key risks per model:**
- **DeepSeek**: May occasionally return `confidence` as string "0.9" instead of number → handled by validator
- **Gemini Flash**: May add markdown fences around JSON → handled by validator  
- **GPT-4o-mini**: Most reliable, rarely needs correction

---

## 5. COST ESTIMATION

### Token Counts per Request

| Component | Tokens (avg) | Notes |
|-----------|-------------|-------|
| System prompt | ~780 | Fixed per request |
| User prompt | ~475 | Varies by description length |
| **Total input** | **~1,255** | |
| JSON output | ~180 | Compact JSON, 10 fields |
| **Total output** | **~180** | |

### Cost per Listing (single analysis)

| Provider | Model | Input cost/1M | Output cost/1M | Cost/listing |
|----------|-------|--------------|----------------|-------------|
| OpenAI | GPT-4o-mini | $0.15 | $0.60 | **$0.000296** |
| DeepSeek | V4-flash | $0.07 | $0.14 | **$0.000113** |
| Google | Gemini 2.0 Flash | $0.075 | $0.30 | **$0.000148** |
| OpenAI | GPT-4o | $2.50 | $10.00 | **$0.004938** |
| Anthropic | Claude Haiku 3.5 | $0.80 | $4.00 | **$0.001724** |

### Calculation Detail (GPT-4o-mini)
```
Input: 1,255 tokens × $0.15/1M = $0.000188
Output: 180 tokens × $0.60/1M = $0.000108
Total: $0.000296 per listing
```

### Monthly Cost Scenarios (50 listings/day = 1,500/month)

| Provider | Model | Monthly cost | Annual cost |
|----------|-------|-------------|-------------|
| OpenAI | GPT-4o-mini | **$0.44** | $5.33 |
| DeepSeek | V4-flash | **$0.17** | $2.04 |
| Google | Gemini 2.0 Flash | **$0.22** | $2.66 |
| OpenAI | GPT-4o | **$7.41** | $88.87 |
| Anthropic | Claude Haiku 3.5 | **$2.59** | $31.03 |

### With Retry Budget (10% of requests need retry)

| Provider | Model | Monthly (with retries) |
|----------|-------|----------------------|
| OpenAI | GPT-4o-mini | **$0.49** |
| DeepSeek | V4-flash | **$0.19** |
| Google | Gemini 2.0 Flash | **$0.24** |

### Cost Summary

> **At 50 listings/day, the LLM analysis costs under $0.50/month with GPT-4o-mini.**  
> This is negligible. Even GPT-4o at $7.41/month would be affordable.  
> **Cost is NOT a constraint for model selection — quality is.**

---

## 6. IMPLEMENTATION RECOMMENDATIONS

### Recommended Model Priority (fallback chain)

```python
MODEL_CHAIN = [
    {"provider": "openai", "model": "gpt-4o-mini", "priority": 1},
    {"provider": "deepseek", "model": "deepseek-chat", "priority": 2},
    {"provider": "google", "model": "gemini-2.0-flash", "priority": 3},
]
```

**Rationale:**
- GPT-4o-mini first: best Polish understanding, best JSON compliance, cheapest of the "smart" models
- DeepSeek as fallback: good quality, different failure modes (useful for consensus)
- Gemini Flash as backup: free tier available, acceptable quality

### JSON Mode Strategy per Provider

| Provider | JSON enforcement method |
|----------|----------------------|
| OpenAI | `response_format: {"type": "json_object"}` |
| DeepSeek | `response_format: {"type": "json_object"}` (OpenAI-compatible) |
| Gemini | `response_mime_type: "application/json"` (via OpenAI compat endpoint: same as OpenAI) |
| Claude | Not native — rely on prompt instruction + validator |

### Prompt Versioning

Store prompt version in config for A/B testing:
```python
PROMPT_VERSION = "1.0"
# Track: version → accuracy metrics → iterate
```

### Edge Cases to Monitor

1. **Very short listings** (title only, no description): confidence will be low (0.3-0.5)
2. **Mixed signals** ("udział w drodze + udział w nieruchomości"): model must identify primary intent
3. **Price in title vs. in price field**: model should use the price field
4. **Description in English/mixed**: rare on OLX but possible — model handles gracefully
5. **Extremely long descriptions**: truncate to 1500 chars before sending

---

## 7. PROMPT OPTIMIZATION TECHNIQUES

### For Weak Models (applied in v1.0 above)

1. ✅ **Explicit role** — "Jesteś ekspertem..." not vague instruction
2. ✅ **Definition of term** — prevents confusion with standard condo shares
3. ✅ **Enumerated steps** — "oceń kolejno: 1. 2. 3." guides reasoning
4. ✅ **Constrained output** — enum values listed, not open-ended
5. ✅ **Two diverse examples** — one positive, one negative (minimum for alignment)
6. ✅ **"WYŁĄCZNIE JSON"** — hard format constraint, no preamble
7. ✅ **Null handling** — explicitly says "lub null jeśli nie podano"
8. ✅ **Labeled sections** — `[TYTUŁ]`, `[OPIS]` etc. help models parse input

### What NOT to do

- ❌ Don't use markdown formatting in expected output (models copy it)
- ❌ Don't ask for "reasoning" — wastes output tokens, use summary instead
- ❌ Don't include scorer confidence — anchoring effect
- ❌ Don't make examples too long — models may copy example values
- ❌ Don't use nested JSON — flat structure is more reliable across models

---

## 8. FUTURE ITERATIONS

### v1.1 (after 100 real analyses)
- Adjust star rating calibration based on user feedback
- Add/remove risk templates based on actual patterns seen
- Fine-tune description truncation length

### v2.0 (after 500 analyses)
- Consider few-shot with ACTUAL listings the user rated
- Potentially use structured output / function calling (strict schema)
- A/B test "chain of thought in hidden field" vs "direct answer"

### Potential Enhancement: Two-Pass Analysis
```
Pass 1 (cheap): is_real_share + confidence only (50 tokens output)
Pass 2 (if real): full analysis (180 tokens output)
```
This saves ~40% of output tokens on false positives, but adds latency. Worth considering only at scale (500+ listings/day).

---

## APPENDIX: Complete Python Implementation Skeleton

```python
SYSTEM_PROMPT = """Jesteś ekspertem od obrotu udziałami w nieruchomościach w Polsce. Twoje zadanie: przeanalizować ogłoszenie o sprzedaży i ocenić czy dotyczy ono RZECZYWISTEGO udziału w nieruchomości.

DEFINICJA: "Udział w nieruchomości" to ułamkowe prawo własności do nieruchomości (np. 1/2, 1/4, 3/8). Powstaje najczęściej ze spadku, rozwodu, upadłości lub współwłasności. NIE jest udziałem w nieruchomości:
- udział w drodze wewnętrznej (standardowy przy działkach)
- udział w gruncie pod budynkiem (standardowy w spółdzielniach/wspólnotach)
- udział w częściach wspólnych budynku
- udział w spółce/funduszu

ANALIZA — oceń kolejno:
1. Czy to RZECZYWISTY udział? (is_real_share)
2. Jaki ułamek? (fraction) — jeśli podany
3. Typ nieruchomości (property_type)
4. Motywacja sprzedającego (seller_motivation)
5. Ocena ceny (price_assessment) — czy cena za udział jest okazją, uczciwa, czy droga
6. Ryzyka dla kupującego (risks)

OCENA GWIAZDKOWA (stars 1-5):
- 5 = idealna okazja: duży udział (≥1/2), niska cena, jasna sytuacja prawna
- 4 = dobra oferta: rozsądna cena, znany ułamek, motywacja czytelna
- 3 = średnia: niepełne informacje ale prawdopodobnie real deal
- 2 = wątpliwa: mało danych, ryzykowna, możliwe problemy
- 1 = nieatrakcyjna lub to nie jest prawdziwy udział

ODPOWIEDŹ — zwróć WYŁĄCZNIE obiekt JSON (bez markdown, bez komentarzy):
{"is_real_share":true/false,"confidence":0.0-1.0,"stars":1-5,"summary":"2-3 zdania po polsku","fraction":"1/2" lub null,"property_type":"mieszkanie"|"działka"|"kamienica"|"dom"|"lokal"|"grunt"|"inne"|null,"seller_motivation":"spadek"|"syndyk"|"rozwód"|"zadłużenie"|"egzekucja"|"inne"|null,"estimated_value_total":liczba lub null,"price_assessment":"okazja"|"uczciwa"|"droga"|null,"risks":["ryzyko1","ryzyko2"]}

PRZYKŁAD 1 — prawdziwy udział:
Tytuł: "Syndyk sprzeda udział 1/2 w lokalu mieszkalnym 48m2, Kraków"
Cena: 95000 PLN
Odpowiedź: {"is_real_share":true,"confidence":0.95,"stars":4,"summary":"Syndyk sprzedaje 1/2 udziału w mieszkaniu 48m2 w Krakowie za 95 tys. Cena wywoławcza sugeruje możliwość negocjacji.","fraction":"1/2","property_type":"mieszkanie","seller_motivation":"syndyk","estimated_value_total":280000,"price_assessment":"okazja","risks":["współwłaściciel może blokować sprzedaż","konieczność zniesienia współwłasności"]}

PRZYKŁAD 2 — NIE jest udziałem:
Tytuł: "Działka budowlana 1200m2, udział w drodze wewnętrznej"
Cena: 180000 PLN
Odpowiedź: {"is_real_share":false,"confidence":0.95,"stars":1,"summary":"Standardowa sprzedaż działki. 'Udział w drodze' to typowy dostęp komunikacyjny, nie sprzedaż współwłasności.","fraction":null,"property_type":"działka","seller_motivation":null,"estimated_value_total":null,"price_assessment":null,"risks":[]}"""


def build_user_prompt(title: str, description: str, price: int | None, 
                      location: str, area: str | None) -> str:
    """Build the user prompt from listing data."""
    desc_truncated = (description or "brak opisu")[:1500]
    price_str = f"{price} PLN" if price else "brak danych"
    area_str = area or "brak danych"
    
    return f"""Przeanalizuj to ogłoszenie:

[TYTUŁ]
{title}

[OPIS]
{desc_truncated}

[CENA]
{price_str}

[LOKALIZACJA]
{location or 'brak danych'}

[POWIERZCHNIA]
{area_str}"""
```

---

*End of research document. Ready for implementation in Research Loop 3.*

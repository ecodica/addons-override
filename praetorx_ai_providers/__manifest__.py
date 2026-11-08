{
    # Store title: search phrases first, brand last (see 27e5aa3 for the
    # measured search mechanics — commas break phrases, so none inside).
    "name": "AI Providers for Odoo AI | Anthropic Claude Ollama OpenRouter | Own Keys & Budget",
    "version": "19.0.1.0.3",
    "odoo_version": "19.0",
    "category": "Productivity",
    "summary": "Bring your own LLM to Odoo AI: Anthropic Claude, Ollama, vLLM, OpenRouter, Azure — with usage tracking and monthly budget per company",
    "description": """
AI Providers for Odoo AI
========================

Odoo 19 ships an AI layer (AI fields, AI agents, auto-sorting of documents) that
talks to exactly two providers: OpenAI and Google. This module teaches that
same layer additional providers — without replacing anything.

* **Anthropic Claude** through the native Messages API (PDF and image input,
  structured JSON output, tool calling)
* **Any OpenAI-compatible server** through Chat Completions: Ollama, LM Studio,
  vLLM, Mistral, OpenRouter, Groq — including self-hosted models in your own
  data centre
* **Any Responses-API endpoint** (Azure OpenAI, proxies) with your own base URL

Once an endpoint is marked as the default, every built-in Odoo AI feature —
AI fields, agents, document auto-sort — runs through it with your keys and
your model choice. Nothing in Odoo's own code is modified on disk.

Usage and budget
----------------

Every request writes a usage line: company, endpoint, model, tokens in/out/cached,
cost from the price table you maintain per model, and the calling module. A
monthly budget per company warns the administrator at the soft limit and stops
requests at the hard limit. A pivot view shows what each module spent.

Model routing
-------------

Modules that use this layer ask for a *capability* — ``choose`` (pick one value
from a list), ``read`` (read a file and fill a schema) or ``embed`` — and the
endpoint maps it to the model you configured. Cheap models for cheap tasks.

Free, and independent: no Odoo IAP, no vendor subscription, no dependency on
any other PraetorX module.
    """,
    "author": "Syntax & Sabotage, Lars Weiler",
    "maintainer": "Syntax & Sabotage",
    "website": "https://praetorx.net",
    "support": "support@syntaxandsabotage.io",
    "license": "LGPL-3",
    "price": 0,
    "currency": "EUR",
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
        "static/description/screenshot_01_einstellungen.png",
        "static/description/screenshot_02_endpunkte.png",
        "static/description/screenshot_03_endpunkt.png",
        "static/description/screenshot_04_verbrauch.png",
    ],
    "depends": ["ai"],
    "data": [
        "security/ir.model.access.csv",
        "views/ai_provider_endpoint_views.xml",
        "views/ai_usage_line_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu.xml",
        "data/ai_provider_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

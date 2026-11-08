# Changelog

Alle nennenswerten Änderungen an **AI Providers for Odoo AI**.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt der Odoo-Konvention `19.0.<major>.<minor>.<patch>`.

## [19.0.1.0.3] — 2026-10-12

### Behoben

- **Modell je Aufgabe:** Ein Modell, das für die Aufgabe eingetragen ist, hat jetzt Vorrang
  vor einem allgemeinen. Embeddings gehen nie mehr an ein Chat-Modell.

## [19.0.1.0.2] — 2026-09-08

### Geändert

- **Store-Kachel und Icon:** die Grafik des bisherigen Provider-Layers (Foundation) für den
  Nachfolger übernommen. Banner verlustfrei von 4,0 auf 1,2 MB, Icon 256×256 RGBA.

## [19.0.1.0.1] — 2026-09-07

### Geändert

- **Listing marktreif:** vier Screenshots aus der Demo-Firma (Schrödinger-Kanon,
  Deutsch, 2× Auflösung), Icon als RGBA mit transparenten Ecken, Beschreibungsseite
  nach Hauskanon (Kennzahlen, Feature-Karten, Tabs, FAQ, Companion-Module,
  Rechtsfußzeile), Wächter-Tests `test_listing_page.py`.

## [19.0.1.0.0] — 2026-09-07

### Hinzugefügt

- **Erste Fassung** (ADR-017, Phase 1, #448). Erweitert Odoos `LLMApiService` um
  Endpunkte aus `ai.provider.endpoint`; Odoos eigener Code bleibt auf der Platte
  unverändert und läuft weiter, wenn kein Endpunkt passt.
- **Drei Dialekte:** `openai_responses` (Odoos Pfad mit eigener URL und
  Header-Stil), `openai_chat` (`/chat/completions` — Ollama, vLLM, Mistral,
  OpenRouter; PDF als Text über `ir.attachment._index`), `anthropic` (native
  Messages-API mit `document`-Blöcken, Schema als erzwungener Tool-Aufruf,
  Zusammenführung aufeinanderfolgender `tool_result`-Nachrichten).
- **Standard für Odoo KI:** ein Endpunkt bedient alles, was Odoo unter `openai`
  anfragt — KI-Felder, Cron, Agenten, Dokumenten-Sortierung. Unbekannte Modellnamen
  werden durch das Standardmodell des Endpunkts ersetzt.
- **Verbrauch und Budget:** `ai.usage.line` je Aufruf mit Tokens, Kosten aus der
  Preistabelle je Modell und Aufrufer (`ai_caller` im Kontext); weiche Grenze →
  Aktivität an die Administration, harte Grenze → Ablehnung; Pivot/Graph;
  Autovacuum nach zwölf Monaten.
- **Modell je Aufgabe:** `_service_for("choose" | "read" | "embed")` für Module,
  die auf dieser Schicht bauen; Einstellung je Aufgabe.
- Vorlagen-Endpunkte (inaktiv, ohne Schlüssel): Anthropic, Ollama, OpenRouter.
- 31 Tests mit gemocktem HTTP.

### Gemessen, nicht angenommen

- Anthropics OpenAI-Kompatibilitätsschicht ignoriert `type: file` und
  `response_format` — deshalb die native Messages-API.
- Odoos Service spricht die Responses-API (`POST /responses`); die meisten
  „OpenAI-kompatiblen" Server nicht — deshalb der Chat-Completions-Dialekt.

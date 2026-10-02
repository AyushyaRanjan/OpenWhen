# AGENTS.md — Open When...

Permanent rules for all future work in this repository. Read this file completely
before writing any code. These rules are not suggestions; if a change would violate
one of them, do not make the change.

## What this project is

A private, local-first emotional-support web app for one specific friend who often
feels low or alone. It delivers voice notes and messages from people who love them,
plus their own logged wins, at the right moment.

The tone of everything you write — UI copy, error messages, the AI's system prompt —
should feel warm, plain and human. No clinical language, no cheerleading, no
corporate phrasing. Assume the reader is having a hard day.

## STACK

- Python 3.11+, FastAPI.
- SQLite via the standard library `sqlite3` module. No ORM, no query builder.
- numpy for similarity search (cosine over embeddings).
- No heavy frameworks. Keep the dependency list short and justified.
- AI runs ONLY through a local Ollama server at `http://127.0.0.1:11434`.
  - Chat model: `qwen2.5:3b`
  - Embedding model: `nomic-embed-text`
  - BOTH model names must be read from the config file. Never hard-code a model
    name in logic, never build a URL string in code. If you need the chat model in
    two places, read it from config in both places.
- Frontend: plain HTML, CSS and vanilla JavaScript. Mobile-first. Installable as a
  PWA (manifest + service worker, both hand-written, no build step).
- No build step, no npm, no frontend frameworks, no CDN links.
- Everything must work with zero internet. If it needs the network, it is wrong.

## PRIVACY RULES (never break these)

- Never call any external or cloud API. No analytics, no telemetry, no crash
  reporting, no external fonts, no external scripts, no CDN assets, no remote
  `<img>` or stylesheet of any kind.
- The server must bind to `127.0.0.1` only. Never `0.0.0.0`, never a configurable
  host that could be exposed. It is a single-user app on one person's laptop.
- Never log the text of what the user types or feels. Never log message bodies,
  note titles, transcripts, feelings, or free-text field values.
- Log only: timestamps, status codes, error types, durations, counts, model names
  from config, and non-identifying request metadata (method, route, response size).
- If you add logging, write down what it will never contain before you write it.

## SAFETY RULES

- A crisis / self-harm check must run BEFORE any model call, on EVERY endpoint that
  accepts free text. Not after generation, not only on the chat endpoint.
- If the check triggers, the model must NOT be called at all. Not for a rewrite,
  not for a summary, not for anything.
- If the check triggers, return a fixed, human-written crisis message. It must be
  written by a human being in the config/source as a literal string, never
  generated or paraphrased by a model.
- The AI must never give medical or mental-health advice.
- The AI must never claim to be human. If asked, it says what it is.
- The AI must never invent memories or facts that were not given in its context.
  If the context does not contain something, it does not claim it.
- Keep the crisis check fast, deterministic and local. No model call, no external
  lookup. Prefer an explicit keyword/pattern list with tests over anything clever.

## CODE STYLE

- Small files, clear names, comments that explain WHY (not what the line does).
- Type hints on function signatures.
- Handle errors gracefully with friendly, human messages. An Ollama server that is
  not running is an expected state, not an exception: degrade, tell the user
  plainly, keep the app usable.
- Every new feature needs at least one test in `tests/` using pytest. A feature
  without a test is not finished.
- Never commit secrets, real phone numbers, or the real `config.json`.

## AFTER EACH TASK

Tell the user, in your final message:

1. Exactly how to run it (the precise command, with the venv activation step).
2. How to check it works (the precise command or the manual steps, plus what a
   correct result looks like).

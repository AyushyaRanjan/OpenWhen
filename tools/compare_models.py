"""Compare local Ollama chat models on the lead-in generation.

This is a development tool, not part of the app. It reads tools/test_inputs.json,
runs the same lead-in generation that /api/feel uses against the messages
currently in the database (read only), and writes tools/model_comparison.md with
each model's output and how long it took.

It only ever talks to the local Ollama server named in config, and it refuses to
run if that server is not on this machine. See AGENTS.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
# Running this file directly puts tools/ first on sys.path, so add the repo root
# before importing the app package.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import generation  # noqa: E402
from app.config import settings  # noqa: E402
from app.ollama_client import OllamaUnavailable  # noqa: E402

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_INPUTS = TOOLS_DIR / "test_inputs.json"
DEFAULT_OUT = TOOLS_DIR / "model_comparison.md"

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def ensure_local_only() -> None:
    """Abort unless Ollama is configured on this machine."""
    host = urlparse(settings.ollama_url).hostname or ""
    if host not in _LOOPBACK_HOSTS:
        raise SystemExit(
            "Refusing to run: config points Ollama at a non-local host "
            f"({host!r}). This tool must never send data off this machine."
        )


def load_inputs(path: Path) -> list[dict[str, str]]:
    """Read the {mood, text} list, or stop with a clear, friendly message."""
    if not path.exists():
        raise SystemExit(
            f"No inputs found at {path}.\n"
            'Create a JSON list like [{"mood": "lonely", "text": "..."}].'
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON (problem on line {exc.lineno}).")

    if not isinstance(data, list) or not data:
        raise SystemExit(f"{path} should be a non-empty list of objects.")

    rows: list[dict[str, str]] = []
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            raise SystemExit(f"Item {index} in {path} is not an object.")
        rows.append({"mood": str(row.get("mood", "")), "text": str(row.get("text", ""))})
    return rows


async def run(models: list[str], inputs: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Generate a lead-in per model per input, timing each response.

    The embedding (and therefore the retrieved items) is computed once per input
    and reused for every model. Failures are recorded, never fatal.
    """
    results: list[dict[str, Any]] = []

    for row in inputs:
        items = await generation.gather_items(row["mood"], row["text"])
        outputs: dict[str, dict[str, Any]] = {}

        for model in models:
            start = time.perf_counter()
            text = ""
            error: str | None = None
            try:
                text = await generation.generate_lead(
                    items["messages"], items["wins"], model=model
                )
            except OllamaUnavailable as exc:
                error = str(exc)
            except Exception as exc:  # noqa: BLE001 - one bad model must not stop the run
                error = f"{type(exc).__name__}: {exc}"
            outputs[model] = {
                "text": text,
                "seconds": time.perf_counter() - start,
                "error": error,
            }

        results.append(
            {
                "mood": row["mood"],
                "text": row["text"],
                "messages": len(items["messages"]),
                "wins": len(items["wins"]),
                "outputs": outputs,
            }
        )

    return results


def render_markdown(
    models: list[str], results: list[dict[str, Any]], generated_at: str
) -> str:
    """Turn the results into a readable, side-by-side Markdown report."""
    lines: list[str] = []
    lines.append("# Model comparison")
    lines.append("")
    lines.append(f"Generated {generated_at} by tools/compare_models.py.")
    lines.append(
        "Local only. The outputs can refer to private messages from the "
        "database, so please do not share this file."
    )
    lines.append(
        f"Chat models: {', '.join(models)}. Embedding model: {settings.embed_model}."
    )
    lines.append("")

    lines.append("## Timings (seconds)")
    lines.append("")
    lines.append("| Input | " + " | ".join(models) + " |")
    lines.append("|" + " --- |" * (len(models) + 1))
    for index, result in enumerate(results, start=1):
        label = f"{index}. {result['mood'] or '(no mood)'}"
        cells = []
        for model in models:
            out = result["outputs"][model]
            cells.append("error" if out["error"] else f"{out['seconds']:.1f}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines.append("")

    for index, result in enumerate(results, start=1):
        lines.append(f"## Input {index}: {result['mood'] or '(no mood)'}")
        lines.append("")
        lines.append(f"Text: {result['text'] or '(none)'}")
        lines.append("")
        lines.append(
            f"Context used: {result['messages']} message(s), {result['wins']} win(s)."
        )
        lines.append("")
        for model in models:
            out = result["outputs"][model]
            lines.append(f"### {model} - {out['seconds']:.1f}s")
            lines.append("")
            lines.append(out["text"] if out["text"] else "_No output._")
            if out["error"]:
                lines.append("")
                lines.append(f"Error: {out['error']}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


async def _run_and_write(args: argparse.Namespace) -> None:
    inputs = load_inputs(Path(args.inputs))
    results = await run(args.models, inputs)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    out_path.write_text(
        render_markdown(args.models, results, generated_at), encoding="utf-8"
    )

    print(f"Compared {len(args.models)} model(s) over {len(inputs)} input(s).")
    print(f"Wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare local Ollama chat models on the /api/feel lead-in."
    )
    parser.add_argument(
        "models", nargs="+", help="one or more local Ollama chat model names"
    )
    parser.add_argument("--inputs", default=str(DEFAULT_INPUTS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    ensure_local_only()
    try:
        asyncio.run(_run_and_write(args))
    except KeyboardInterrupt:
        raise SystemExit("Stopped.")


if __name__ == "__main__":
    main()

"""Tests for the model-comparison dev tool."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BASE = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "compare_models", BASE / "tools" / "compare_models.py"
)
assert _spec and _spec.loader
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)


def test_load_inputs_reads_a_list(tmp_path):
    path = tmp_path / "in.json"
    path.write_text(json.dumps([{"mood": "sad", "text": "long day"}]), encoding="utf-8")
    assert cm.load_inputs(path) == [{"mood": "sad", "text": "long day"}]


def test_load_inputs_missing_file_stops_clearly(tmp_path):
    with pytest.raises(SystemExit):
        cm.load_inputs(tmp_path / "nope.json")


def test_load_inputs_bad_json_stops_clearly(tmp_path):
    path = tmp_path / "in.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        cm.load_inputs(path)


def test_render_markdown_side_by_side_with_times():
    results = [
        {
            "mood": "sad",
            "text": "a hard day",
            "messages": 1,
            "wins": 0,
            "outputs": {
                "m1": {"text": "warm line", "seconds": 1.23, "error": None},
                "m2": {"text": "", "seconds": 0.02, "error": "boom"},
            },
        }
    ]
    md = cm.render_markdown(["m1", "m2"], results, "2026-01-01 10:00")
    assert "# Model comparison" in md
    assert "a hard day" in md
    assert "warm line" in md
    assert "1.2" in md  # seconds, rounded to one decimal
    assert "boom" in md


async def test_run_generates_per_model_and_keeps_going(monkeypatch):
    calls: list[str | None] = []

    async def fake_gather(mood, text):
        return {"messages": [{"sender": "A", "text": "hi"}], "wins": []}

    async def fake_lead(messages, wins, *, model=None, temperature=0.7):
        calls.append(model)
        if model == "bad":
            from app.ollama_client import OllamaUnavailable

            raise OllamaUnavailable("nope")
        return f"lead from {model}"

    monkeypatch.setattr(cm.generation, "gather_items", fake_gather)
    monkeypatch.setattr(cm.generation, "generate_lead", fake_lead)

    results = await cm.run(["good", "bad"], [{"mood": "sad", "text": "x"}])

    assert calls == ["good", "bad"]
    outputs = results[0]["outputs"]
    assert outputs["good"]["text"] == "lead from good"
    assert outputs["good"]["seconds"] >= 0
    assert "nope" in outputs["bad"]["error"]


def test_main_writes_a_report(tmp_path, monkeypatch):
    inputs = tmp_path / "in.json"
    inputs.write_text('[{"mood": "sad", "text": "x"}]', encoding="utf-8")
    out = tmp_path / "out.md"

    async def fake_run(models, rows):
        return [
            {
                "mood": "sad",
                "text": "x",
                "messages": 0,
                "wins": 0,
                "outputs": {
                    m: {"text": "ok", "seconds": 0.5, "error": None} for m in models
                },
            }
        ]

    monkeypatch.setattr(cm, "run", fake_run)
    monkeypatch.setattr(cm, "ensure_local_only", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["compare_models.py", "m1", "--inputs", str(inputs), "--out", str(out)]
    )

    cm.main()

    text = out.read_text(encoding="utf-8")
    assert "# Model comparison" in text
    assert "m1" in text


def test_refuses_a_non_local_ollama(monkeypatch):
    monkeypatch.setattr(
        cm,
        "settings",
        SimpleNamespace(ollama_url="http://example.com:11434", embed_model="x"),
    )
    with pytest.raises(SystemExit):
        cm.ensure_local_only()

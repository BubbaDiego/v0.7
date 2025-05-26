#!/usr/bin/env python3
"""Standalone sanity tests for GPTCore."""

import os
import sys
import types
import json

# Ensure repository root is on sys.path when run as a script
CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.dirname(CURRENT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Provide dummy dotenv and openai modules
sys.modules['dotenv'] = types.SimpleNamespace(load_dotenv=lambda: None)

class DummyChatCompletions:
    def create(self, model, messages):
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="dummy response"))])

class DummyOpenAI:
    def __init__(self, api_key=None):
        self.chat = types.SimpleNamespace(completions=DummyChatCompletions())

sys.modules['openai'] = types.SimpleNamespace(OpenAI=DummyOpenAI)

from gpt.gpt_core import GPTCore
from config.config_constants import DB_PATH


def test_build_payload():
    core = GPTCore(db_path=str(DB_PATH))
    payload = core.build_payload("test instructions")
    assert payload["instructions_for_ai"] == "test instructions", "Instruction mismatch"
    assert payload["current_snapshot"], "Missing current snapshot"
    print(json.dumps(payload, indent=2))
    print("test_build_payload passed")


def test_analyze():
    core = GPTCore(db_path=str(DB_PATH))
    result = core.analyze("test instructions")
    assert result == "dummy response", f"Unexpected reply: {result}"
    print("test_analyze passed")


if __name__ == "__main__":
    test_build_payload()
    test_analyze()
    print("All GPTCore tests passed")

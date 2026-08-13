# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Regression guards for the Amazon Bedrock providers.

Three already-landed fixes are pinned here:

* **F2**: :func:`_converse_messages` must preserve each turn's role and content.
  ``LLMMessage`` is a ``TypedDict``, so history entries arrive as plain dicts;
  the old attribute-access path silently relabelled every assistant turn as
  ``user``. This test round-trips a two-turn history and asserts the assistant
  turn survives as ``assistant``.
* **F3**: :meth:`BedrockLLM.ainvoke` hands the blocking botocore call to
  ``asyncio.to_thread`` so an outer ``asyncio.wait_for`` can actually fire.
  Before the fix the call ran inline on the event loop and the timeout could
  never cancel it. This test stubs a slow ``invoke`` and asserts the timeout
  raises rather than hanging.
* **F16**: both Bedrock clients are built with ``BEDROCK_CONFIG``, so every
  socket carries a ``read_timeout`` instead of hanging forever. This test
  asserts the config reaches both clients and pins the two numbers the retry
  budget is reasoned about with.

Run from inside this directory, which is where the lab's dependencies and its
``data/`` corpus are resolved from::

    cd 01-graph-build
    uv run --with pytest --with-requirements requirements.txt -m pytest

Add ``test_bedrock_providers.py`` to that command to collect this file alone.
"""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path

# ``graph_builder`` is Lab 1's own module, not part of the shared package, so
# the sibling directory has to be importable regardless of how the suite is
# launched (``unittest`` discovery, a direct path, or pytest).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from neo4j_graphrag.llm.base import LLMResponse  # noqa: E402
from neo4j_graphrag.message_history import InMemoryMessageHistory  # noqa: E402
from neo4j_graphrag.types import LLMMessage  # noqa: E402

from workshop.bedrock_providers import (  # noqa: E402
    BedrockEmbeddings,
    BedrockLLM,
    _converse_messages,
)

# ``DOC_TIMEOUT_SECONDS`` is imported lazily inside the one test that needs it:
# ``graph_builder`` pulls in ``workshop.graph_connection``, which raises at
# import when ``NEO4J_PASSWORD`` is unset. Importing it here would fail
# collection for the whole file, including the F2 and F3 guards that never
# touch Neo4j.


class TestConverseMessages(unittest.TestCase):
    """F2: a message history must round-trip with roles and content intact."""

    def test_typed_dict_history_preserves_roles_and_content(self) -> None:
        """A list of ``LLMMessage`` dicts survives conversion unchanged.

        ``LLMMessage`` is a ``TypedDict``, so entries are plain dicts. The old
        ``getattr(msg, "role", "user")`` path missed on dicts and relabelled the
        assistant turn as ``user``; this asserts it stays ``assistant``.
        """
        user_turn: LLMMessage = {"role": "user", "content": "book me a hotel"}
        assistant_turn: LLMMessage = {"role": "assistant", "content": "which city?"}

        converted = _converse_messages([user_turn, assistant_turn])

        self.assertEqual(
            converted,
            [
                {"role": "user", "content": [{"text": "book me a hotel"}]},
                {"role": "assistant", "content": [{"text": "which city?"}]},
            ],
        )
        # The heart of the regression: the second turn is still the assistant.
        self.assertEqual(converted[1]["role"], "assistant")
        self.assertEqual(converted[1]["content"][0]["text"], "which city?")

    def test_message_history_object_is_accepted(self) -> None:
        """The helper also reads a ``MessageHistory`` object via ``.messages``.

        ``_converse_messages`` does ``getattr(history, "messages", history)``,
        so a real ``InMemoryMessageHistory`` holding the same dicts must convert
        identically to the bare list.
        """
        history = InMemoryMessageHistory(
            messages=[
                {"role": "user", "content": "book me a hotel"},
                {"role": "assistant", "content": "which city?"},
            ]
        )

        converted = _converse_messages(history)

        self.assertEqual(
            converted,
            [
                {"role": "user", "content": [{"text": "book me a hotel"}]},
                {"role": "assistant", "content": [{"text": "which city?"}]},
            ],
        )
        self.assertEqual(converted[1]["role"], "assistant")


class TestAinvokeTimeout(unittest.TestCase):
    """F3: ``ainvoke`` runs off the event loop so ``wait_for`` can cancel it."""

    def test_wait_for_times_out_instead_of_hanging(self) -> None:
        """A slow synchronous ``invoke`` must not defeat an outer timeout.

        ``ainvoke`` delegates to ``asyncio.to_thread``, so a 1s ``wait_for``
        around a 5s call raises ``TimeoutError`` in about a second. Before the
        fix the blocking call ran inline and this hung for the full 5s.
        """
        provider = BedrockLLM()

        def slow_invoke(
            _input: str,
            _message_history: object = None,
            _system_instruction: object = None,
        ) -> LLMResponse:
            time.sleep(5)
            return LLMResponse(content="too late")

        # Stub the blocking round trip only; ``ainvoke`` (the code under test)
        # is left untouched.
        provider.invoke = slow_invoke  # type: ignore[method-assign]

        # A private loop closed with ``wait=False`` keeps the test near 1s: we
        # do not block on the orphaned worker thread's remaining sleep.
        loop = asyncio.new_event_loop()
        started = time.monotonic()
        try:
            with self.assertRaises(asyncio.TimeoutError):
                loop.run_until_complete(
                    asyncio.wait_for(provider.ainvoke("hello"), timeout=1.0)
                )
        finally:
            loop.close()

        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed,
            5.0,
            "wait_for should cancel around 1s, not wait out the full 5s sleep",
        )


class TestBedrockClientConfig(unittest.TestCase):
    """F16: both clients carry the same bounded, rate-limited config."""

    def test_both_clients_apply_bedrock_config(self) -> None:
        for provider in (BedrockLLM(), BedrockEmbeddings()):
            config = provider.client.meta.config
            with self.subTest(provider=type(provider).__name__):
                self.assertEqual(config.read_timeout, 45)
                # botocore reads ``max_attempts`` as a retry count and
                # normalises it to ``total_max_attempts``, the initial try plus
                # the retries, so 5 configured -> 6 total.
                self.assertEqual(config.retries["total_max_attempts"], 6)
                # Adaptive mode is the point of the setting: it adds a
                # client-side rate limiter, so a room full of simultaneous Lab 1
                # builds backs off against the shared per-region quota instead
                # of retrying into it at full speed.
                self.assertEqual(config.retries["mode"], "adaptive")

    def test_worst_case_retry_chain_is_the_documented_270_seconds(self) -> None:
        """Pin read_timeout x total_max_attempts at the number that was chosen.

        45 * 6 = 270, which is longer than ``DOC_TIMEOUT_SECONDS``. That is the
        trade the comment above ``BEDROCK_CONFIG`` records: throttling returns
        fast and costs backoff rather than a read timeout, so the extra attempts
        are cheap in the case they exist for, while six consecutive sockets each
        hanging the full 45s ends with the outer ``asyncio.wait_for`` firing and
        the build moving on. Raising ``DOC_TIMEOUT_SECONDS`` or lowering
        ``read_timeout`` are the two levers named there.

        The numbers are read off a live client's normalised config, since
        botocore exposes the raw ``BEDROCK_CONFIG.retries`` as
        ``{"max_attempts": 5}`` and only resolves ``total_max_attempts`` once a
        client is built.
        """
        try:
            from graph_builder import DOC_TIMEOUT_SECONDS
        except RuntimeError as exc:
            self.skipTest(f"graph_builder needs Neo4j config: {exc}")

        config = BedrockLLM().client.meta.config
        read_timeout = config.read_timeout
        total_max_attempts = config.retries["total_max_attempts"]

        self.assertEqual(read_timeout * total_max_attempts, 270)
        # One attempt still has to fit, or the per-document bound would cut off
        # a call that was never going to be retried.
        self.assertLess(read_timeout, DOC_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()

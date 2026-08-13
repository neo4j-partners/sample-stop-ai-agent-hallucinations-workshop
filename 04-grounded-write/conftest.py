# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Pytest configuration for the Lab 4 test set.

Nothing is configured here, and nothing needs to be. Lab 4 holds five
``test_*.py`` files and no staged deployment code, neither of its notebooks is
named ``test_*``, and pytest skips ``.venv`` by default,
so a bare ``pytest`` from this folder collects those five files and nothing
else. The deployment tests that import ``bedrock_agentcore`` live in Lab 5 and
are excluded there.
"""

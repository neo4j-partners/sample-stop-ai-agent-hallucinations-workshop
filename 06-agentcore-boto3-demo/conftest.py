# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Pytest configuration for the local Demo 06 test set.

The staged deployment code lives under ``deployment-deferred/`` and is not run
in this workshop pass. Its tests import ``bedrock_agentcore`` and ``strands``,
which are absent from the local participant environment, so we keep pytest from
collecting them here. Those tests run only in the deployment environment.
"""

collect_ignore_glob = ["deployment-deferred/*"]

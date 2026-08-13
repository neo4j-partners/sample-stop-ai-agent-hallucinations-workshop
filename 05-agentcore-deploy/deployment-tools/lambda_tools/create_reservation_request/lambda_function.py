# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lambda entry point for the sole Gateway command target.

The handler itself is `workshop.reservation_command.handler`, the same function
Lab 4 runs locally. The deployment package installs the shared `workshop`
package rather than flat-copying its files, so this import resolves the same way
here as it does in the notebook and in the tests.
"""

from workshop.reservation_command import handler

__all__ = ["handler"]

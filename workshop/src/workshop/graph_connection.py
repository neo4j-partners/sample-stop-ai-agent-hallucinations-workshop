# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Neo4j connection settings shared by every lab that opens a driver.

`NEO4J_USERNAME` defaults to `"neo4j"`, which is what Aura provisions; the older
`NEO4J_USER` spelling is not read. There is no default for `NEO4J_PASSWORD` — it
is required, and a missing value raises at import rather than silently sending a
bad credential the way a baked-in default password would.

That import-time raise is why this module is separate from `contracts` and from
`graph_schema`. Importing either of those must stay free of environment
requirements so the reservation Lambda and the offline tests can load them
without credentials.
"""

import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")

NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise RuntimeError(
        "NEO4J_PASSWORD is not set. Export it (see .env.example) before running "
        "the workshop labs; there is no default, so a missing password fails "
        "loudly here instead of silently sending a bad credential to Neo4j."
    )


def neo4j_auth() -> tuple[str, str]:
    """Return the (username, password) pair for the Neo4j driver."""
    return NEO4J_USERNAME, NEO4J_PASSWORD

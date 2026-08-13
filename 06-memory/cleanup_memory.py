# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Scoped cleanup for the inspectable Neo4j memory lab.

Removes, in this order:

1. Workshop-owned ``ABOUT_HOTEL`` relationships.
2. Conversations, messages, and users in the swept id namespace.
3. Preferences in the matching category namespace or tagged by this lab, but
   only once no user owns them.

**Cleanup is scoped to one run by default.** ``--run-prefix`` takes the run
prefix section 1 of the notebook prints, and nothing outside that run is
touched. This is the form to hand a room: on a Neo4j instance shared by thirty
participants, an instance-wide sweep run by whoever finishes first deletes
everybody else's in-flight records.

``--all`` widens the sweep to every Lab 6 run on the instance, which is what
makes an interrupted earlier run whose prefix nobody wrote down recoverable.
It requires a typed confirmation, and it is a facilitator action to take when
the room is finished rather than a participant one.

``--dry-run`` counts what either scope would delete and deletes nothing.

The hotel graph, its chunk indexes, and other labs' data are untouched.
The library-managed memory vector indexes stay in place: they are shared
infrastructure, they cost nothing while empty, and the smoke test checks
them.

Requires live Neo4j credentials but no AWS access. Without them the script
prints a skip message and exits 0.

Run with:
    uv run --with-requirements requirements.txt python cleanup_memory.py \
        --run-prefix demo08-xxxxxxxx-
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from memory_helpers import (
    DEMO_ID_PREFIX,
    HOTEL_RELATIONSHIP,
    PREFERENCE_CATEGORY_PREFIX,
    MemoryDemoConfig,
    WORKSHOP_OWNER,
    load_config,
    preference_category_prefix,
)

SKIP_MESSAGE = (
    "skipped: set NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD to clean up the "
    "memory lab records."
)

NO_SCOPE_MESSAGE = (
    "Nothing was deleted: cleanup needs a scope.\n"
    "  Your own run:   --run-prefix demo08-xxxxxxxx-\n"
    "                  Section 1 of 6.1_neo4j_agent_memory.ipynb prints the "
    "exact value.\n"
    "  Every Lab 6 run on this instance: --all, which asks for a typed "
    "confirmation first.\n"
    "Add --dry-run to either form to see the counts without deleting."
)

ALL_CONFIRMATION = "delete every lab 6 run"

# The hotel-link sweep starts at the Preference rather than at a bare pattern,
# because the category namespace is the only run handle an ABOUT_HOTEL edge
# has. Every edge this lab writes leaves a Preference, so nothing is missed.
DELETE_DEMO_HOTEL_LINKS = f"""
CYPHER 25
MATCH (p:Preference)-[r:{HOTEL_RELATIONSHIP}]->()
WHERE r.workshop_owner = $owner
  AND p.category STARTS WITH $category_prefix
DELETE r
"""

COUNT_DEMO_HOTEL_LINKS = f"""
CYPHER 25
MATCH (p:Preference)-[r:{HOTEL_RELATIONSHIP}]->()
WHERE r.workshop_owner = $owner
  AND p.category STARTS WITH $category_prefix
RETURN count(r) AS records
"""

DELETE_PREFIXED_SESSIONS = """
CYPHER 25
MATCH (c:Conversation)
WHERE c.session_id STARTS WITH $prefix
OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
DETACH DELETE c, m
"""

COUNT_PREFIXED_SESSIONS = """
CYPHER 25
MATCH (c:Conversation)
WHERE c.session_id STARTS WITH $prefix
OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
RETURN count(DISTINCT c) + count(DISTINCT m) AS records
"""

DELETE_PREFIXED_USERS = """
CYPHER 25
MATCH (u:User)
WHERE u.identifier STARTS WITH $prefix
DETACH DELETE u
"""

COUNT_PREFIXED_USERS = """
CYPHER 25
MATCH (u:User)
WHERE u.identifier STARTS WITH $prefix
RETURN count(u) AS records
"""

# Two handles, because either one alone leaks. The owner marker is stamped
# only by the notebook's second-to-last cell, so a run that died earlier never
# gets it. The category prefix is written with the Preference itself in
# section 3, and by the time this query runs the preceding sweeps have already
# detached every edge that could otherwise have found the node.
DELETE_ORPHANED_DEMO_PREFERENCES = """
CYPHER 25
MATCH (p:Preference)
WHERE (p.workshop_owner = $owner
       OR p.category STARTS WITH $category_prefix)
  AND NOT EXISTS { MATCH (:User)-[:HAS_PREFERENCE]->(p) }
DETACH DELETE p
"""

# The dry-run counterpart cannot ask for orphans, because the preferences are
# orphaned by the user sweep two queries earlier and nothing has run yet. It
# counts the preferences no user from outside the swept namespace owns, which
# is exactly the set the delete will find once the user sweep has happened.
COUNT_ORPHANED_DEMO_PREFERENCES = """
CYPHER 25
MATCH (p:Preference)
WHERE (p.workshop_owner = $owner
       OR p.category STARTS WITH $category_prefix)
  AND NOT EXISTS {
    MATCH (u:User)-[:HAS_PREFERENCE]->(p)
    WHERE NOT u.identifier STARTS WITH $prefix
  }
RETURN count(p) AS records
"""

# Defensive, and a no-op for anything this lab wrote: the only users that own
# a marked preference are the demo08- users, and they were detach-deleted two
# queries ago. It stays as a backstop for a preference some other application
# attached one of its own users to, where deleting the node would be wrong and
# leaving this lab's marker on it would also be wrong.
REMOVE_SHARED_PREFERENCE_MARKERS = """
CYPHER 25
MATCH (p:Preference)
WHERE p.workshop_owner = $owner
  AND p.category STARTS WITH $category_prefix
  AND EXISTS { MATCH (:User)-[:HAS_PREFERENCE]->(p) }
REMOVE p.workshop_owner
"""

COUNT_HOTELS = "CYPHER 25 MATCH (h:Hotel) RETURN count(h) AS hotels"

# Each sweep is a label, the delete that runs it, and the count a dry run
# reports instead. Order matters: preferences are orphaned by the user sweep.
SWEEPS = (
    (
        "workshop-owned ABOUT_HOTEL relationship",
        DELETE_DEMO_HOTEL_LINKS,
        COUNT_DEMO_HOTEL_LINKS,
    ),
    (
        "conversation and message",
        DELETE_PREFIXED_SESSIONS,
        COUNT_PREFIXED_SESSIONS,
    ),
    ("user", DELETE_PREFIXED_USERS, COUNT_PREFIXED_USERS),
    (
        "preference",
        DELETE_ORPHANED_DEMO_PREFERENCES,
        COUNT_ORPHANED_DEMO_PREFERENCES,
    ),
)


@dataclass(frozen=True)
class CleanupScope:
    """The id and category namespaces one cleanup run is allowed to touch.

    ``id_prefix`` bounds the session and user sweeps, ``category_prefix``
    bounds the preference and relationship sweeps, and the two always track
    each other because both are derived from the same prefix.
    """

    id_prefix: str
    category_prefix: str
    label: str

    @property
    def parameters(self) -> dict:
        """The parameter set every cleanup query is run with."""
        return {
            "owner": WORKSHOP_OWNER,
            "prefix": self.id_prefix,
            "category_prefix": self.category_prefix,
        }


def run_scope(run_prefix: str) -> CleanupScope:
    """Bound cleanup to the one run whose prefix the notebook printed."""
    return CleanupScope(
        id_prefix=run_prefix,
        category_prefix=preference_category_prefix(run_prefix),
        label=f"run {run_prefix}",
    )


def all_runs_scope() -> CleanupScope:
    """Bound cleanup to every Lab 6 run on the instance."""
    return CleanupScope(
        id_prefix=DEMO_ID_PREFIX,
        category_prefix=PREFERENCE_CATEGORY_PREFIX,
        label=f"every Lab 6 run on this instance, namespace {DEMO_ID_PREFIX}",
    )


def run_cleanup(
    config: MemoryDemoConfig,
    scope: CleanupScope,
    *,
    dry_run: bool = False,
) -> int:
    """Delete the scoped memory records without changing Hotel nodes."""
    driver = GraphDatabase.driver(
        config.uri, auth=(config.username, config.password)
    )
    parameters = scope.parameters
    try:
        with driver.session(database=config.database) as session:
            hotels_before = session.run(COUNT_HOTELS).single()["hotels"]

            if dry_run:
                print(f"Dry run over {scope.label}. Nothing is deleted.")
                for label, _, count_query in SWEEPS:
                    row = session.run(count_query, parameters).single()
                    records = row["records"] if row else 0
                    print(f"  would delete {records} {label} record(s)")
            else:
                nodes_deleted = 0
                relationships_deleted = 0
                for _, delete_query, _ in SWEEPS:
                    counters = (
                        session.run(delete_query, parameters).consume().counters
                    )
                    nodes_deleted += counters.nodes_deleted
                    relationships_deleted += counters.relationships_deleted
                print(
                    f"Deleted {nodes_deleted} memory node(s) and "
                    f"{relationships_deleted} relationship(s) "
                    f"from {scope.label}."
                )

                session.run(
                    REMOVE_SHARED_PREFERENCE_MARKERS, parameters
                ).consume()

            hotels_after = session.run(COUNT_HOTELS).single()["hotels"]
            if hotels_after != hotels_before:
                raise AssertionError(
                    f"Hotel count changed during cleanup: {hotels_before} "
                    f"before, {hotels_after} after. Investigate before "
                    "re-running."
                )
            print(f"Hotel graph intact: {hotels_after} Hotel node(s).")
    finally:
        driver.close()

    print("\nDry run finished." if dry_run else "\nMemory cleanup finished.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the cleanup scope from the command line."""
    parser = argparse.ArgumentParser(
        description=(
            "Delete this lab's memory records from Neo4j. Scoped to one run "
            "unless --all is given."
        )
    )
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--run-prefix",
        help=(
            "Delete only the run with this id prefix, as printed by section 1 "
            f"of the notebook. Must start with {DEMO_ID_PREFIX!r}."
        ),
    )
    scope_group.add_argument(
        "--all",
        action="store_true",
        help=(
            "Delete every Lab 6 run on the instance, including other "
            "participants' runs still in progress. Asks for a typed "
            "confirmation."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count what the chosen scope would delete, and delete nothing.",
    )
    return parser.parse_args(argv)


def confirm_all_runs() -> bool:
    """Ask for a typed confirmation before the instance-wide sweep."""
    print(
        "About to delete every Lab 6 memory record on this instance, "
        "including other participants' runs still in progress."
    )
    try:
        typed = input(f"Type {ALL_CONFIRMATION!r} to continue: ")
    except EOFError:
        print("\nNo confirmation could be read. Nothing was deleted.")
        return False
    if typed.strip() != ALL_CONFIRMATION:
        print("Confirmation did not match. Nothing was deleted.")
        return False
    return True


def resolve_scope(args: argparse.Namespace) -> CleanupScope | None:
    """Turn the parsed arguments into a scope, or print why there is none."""
    if args.run_prefix:
        if not args.run_prefix.startswith(DEMO_ID_PREFIX):
            print(
                f"Refusing to sweep {args.run_prefix!r}: a run prefix has to "
                f"start with {DEMO_ID_PREFIX!r}, so a typo cannot reach "
                "records this lab never wrote."
            )
            return None
        return run_scope(args.run_prefix)
    if args.all:
        if not args.dry_run and not confirm_all_runs():
            return None
        return all_runs_scope()
    print(NO_SCOPE_MESSAGE)
    return None


def main(argv: list[str] | None = None) -> int:
    """Check prerequisites and the scope, then run the cleanup."""
    args = parse_args(argv)

    try:
        config = load_config()
    except RuntimeError:
        print(SKIP_MESSAGE)
        return 0

    scope = resolve_scope(args)
    if scope is None:
        return 2

    try:
        return run_cleanup(config, scope, dry_run=args.dry_run)
    except AssertionError as exc:
        print(f"\nCleanup check failed: {exc}")
        return 1
    except (DriverError, Neo4jError) as exc:
        print(f"\nCleanup could not use Neo4j at {config.uri}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

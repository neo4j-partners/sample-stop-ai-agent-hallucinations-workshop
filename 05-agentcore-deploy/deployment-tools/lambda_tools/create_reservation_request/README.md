# Reservation-request Lambda

This is the only Lambda command in the workshop. `lambda_function.py` re-exports
`workshop.reservation_command.handler`, the same function Lab 4 runs locally. Its
deployment package installs the shared `workshop` package and the Neo4j driver,
then places this entry point at the zip root; `build_lambda_zip` in
`setup/provision_agentcore.py` builds it. Set `NEO4J_COMMAND_SECRET_ID` to a
secret containing `uri`, `username`, `password`, and `database`.

Use a separate Neo4j command user when the Aura tier supports custom users and
roles. Its effective access is limited to:

- reading the workshop-owned `Rule` with ID `demo-06-maximum-guests`;
- matching a `Hotel` by `hotel_id` and checking `demo6_fixture`;
- reading an existing workshop-owned `ReservationRequest` by `request_id`;
- creating a `ReservationRequest` with the seven properties in the frozen
  contract and a single outgoing `FOR_HOTEL` relationship.

Do not grant this user general hotel writes. The reviewed command contains no
query that sets, deletes, or creates canonical hotel data. Exact role and grant
commands depend on the Neo4j and Aura edition, so an operator must apply the
equivalent least-privilege role supported by the deployment tier.

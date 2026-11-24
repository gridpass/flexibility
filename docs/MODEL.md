# Screening model

For a constant site load L and event import limit I, the required reduction is max(0, L - I). An event lasting T hours requires that reduction times T MWh. The annual call count N and minimum interval R must fit into 8,760 hours: N*T + (N-1)*R <= 8760.

Flexible demand and generation are eligible only if the available notice meets preparation time and the resource can sustain the full event. Battery discharge is bounded by its power rating, usable discharge energy divided by T, and (for repeated events) the available charging power times R times round-trip efficiency divided by T. Available recharge power is capped by the battery power rating. For one event, initial usable battery energy is assumed full; a final recharge is not required for event feasibility.

The model allocates eligible sustained resources in increasing order of input variable cost; battery discharge cost accounts for recharge electricity and round-trip efficiency. All resources are treated as continuous, divisible and independent. Remaining reduction determines the modelled import during the event. Annual cost multiplies each resource's variable cost by its event energy and N; it is not total cost of ownership.

All power values are MW, energy MWh, time hours except notice/preparation in minutes, costs EUR/MWh, and efficiency percent. JSON schema is exported by the CLI. Invalid, non-finite and out-of-range values are rejected. Explicitly verify the input scenario: a feasible result is only conditional on the assumptions supplied.

## Wadi Watch - The flood layer that checks who was never reached

Cell broadcast already reaches every working phone in a cell. Wadi Watch is the layer on top that answers the question broadcast cannot: whose phone was off, out of battery or out of signal. It turns silence into an ordered search list with a last known area, and puts responders on a slice when the cell is saturated.

### The problem

Broadcast tells everyone. Wadi Watch finds out who never heard it, and hands the response team a short, ordered list instead of a city.

### What the prototype actually does

Wadi Watch is a working web application with an operator console, a REST API, and
a live WebSocket feed of the agent's reasoning. Open it, click a scenario, and
you watch the agent choose CAMARA calls one at a time and then justify its
decision with the network answers behind it.

It runs in three modes. `simulator` needs no credentials and answers every
CAMARA call in the real CAMARA response shape, which is how the organisers
recommend demonstrating and how the test suite stays deterministic. `live`
calls the Nokia Network-as-Code gateway with your own key. `hybrid` uses live
where credentials allow and falls back per call. Every answer is tagged with
its source in the UI, so a simulated result can never pass itself off as a real
network answer.

### The AI agent layer

The agent is a planner over a CAMARA tool registry, not a script with an LLM
bolted on. Each tool in the registry carries its price, its typical latency and
how much it reveals about a person, and the planner is judged on choosing well:

1. The planner proposes one call, with a stated reason.
2. The runtime, never the model, checks it against the tool allowlist, the
   consent ledger and the remaining budget.
3. The CAMARA answer is recorded with full provenance and turned into a fact.
4. Repeat until the planner submits a decision, or the budget runs out.

The planner is Google AI Studio (Gemini) through **Pydantic AI**'s typed,
structured-output path. It is enabled by setting `AGENT_PROVIDER=gemini`
alongside a `GEMINI_API_KEY`. A model turn may only propose a next CAMARA check
or a decision; it cannot execute a network call itself. The runtime remains the
only executor of consent, the tool allowlist, argument filtering and budget.

Gemini is opt-in on both counts deliberately: a key sitting in the environment
should not be enough to start spending on a model. Otherwise a deterministic
policy planner implementing the same escalation ladder takes over, so the
prototype is demonstrable offline and CI has something stable to assert. If a
configured model cannot complete a turn, the finished case is explicitly
labelled `policy-fallback` with a bounded error reason. It is never presented
as a successful Gemini-planned decision.

**The guardrail is the part worth looking at.** The policy computes a floor for
every case from the facts alone. If the model proposes something less cautious
than the floor, the floor wins and the disagreement is written into the
decision record. A language model should choose which checks to buy; it should
not be able to clear a case the evidence says to escalate. There is a test for
exactly this.

### Results from the shipped scenarios

7 scenarios ship with the prototype, and all 7 reach the
outcome they claim. The demo and the test suite assert the same thing, so a
scenario drifting from the pitch is a build failure.

- Outcome levels reached: `accounted`, `advise`, `warn`, `search`
- CAMARA calls per case: 1 to 6 (average 2.7)
- Total spend across all scenarios: 44 units, against 175 if
  every available check were called on every case, a saving of 74.9%

| Scenario | Outcome | CAMARA calls | Spend |
| --- | --- | --- | --- |
| Enrolled, but outside the risk area | `accounted` | 1 | 2 |
| Farm on the valley floor, phone answering | `warn` | 2 | 3 |
| Inside the alert, up the slope | `advise` | 2 | 3 |
| Basement flat, unreachable | `search` | 4 | 8 |
| Site worker unreachable and the cell is saturated | `search` | 6 | 22 |
| The network answers PARTIAL on the boundary | `warn` | 2 | 3 |
| Enrol a line from the co-operative's list | `accounted` | 2 | 3 |

The cheapest case, *Enrolled, but outside the risk area*, resolves in 1 call(s). The
most expensive, *Site worker unreachable and the cell is saturated*, earns 6. That gap is the product:
an agent that calls everything on everyone is safe, useless and unaffordable.

### CAMARA APIs on Nokia Network as Code

`location-verification`, `device-status`, `location-retrieval`, `congestion-insights`, `quality-on-demand`, `network-slice-device-attachment`, `geofencing-subscriptions`, `number-verification`

| CAMARA API | What the agent asks it | Cost | Reveals |
| --- | --- | --- | --- |
| `location-verification` | Is the line inside this area | 2 | boolean |
| `device-status` | Can the line be reached | 1 | enum |
| `location-retrieval` | Where is the line | 4 | area |
| `congestion-insights` | How loaded is the serving cell | 1 | enum |
| `quality-on-demand` | Reserve network quality for this line | 8 | mutates |
| `network-slice-device-attachment` | Put this line on a dedicated slice | 6 | mutates |
| `geofencing-subscriptions` | Notify me when the line leaves or enters an area | 2 | area |
| `number-verification` | Confirm the line on the phone | 1 | boolean |

### Consent

CAMARA identity, location and geofencing APIs are only lawful with the consent
of the line owner, so consent is enforced in the transport path rather than
described in a policy document. An ungranted call raises before a request is
built.

Consent is taken at enrolment, from lists cities, site owners and co-
operatives already keep, from the enrolled resident or worker, who owns the
line and agrees once. Checks run only while an alert is open for a zone that
person is enrolled in. There is no monitoring between alerts. Anyone can leave
the register at any time, which cancels their geofence subscription and every
future check.

You can prove this in the running app: press **Withdraw consent**, run the same
case again, and watch the agent get refused at the transport layer with zero
CAMARA calls made.

### What this does not do

- Wadi Watch does not replace cell broadcast and does not try to. Broadcast reaches everyone; this reaches the people who were enrolled, and only them.
- An unreachable line is not proof that someone is in trouble. It is proof that nobody knows, which is the honest claim and still enough to order a search list by.
- Coverage equals enrolment. The people most at risk are often the hardest to enrol, and no API changes that. It is outreach work, not engineering.
- Hydrology is not ours. The risk areas here come from the operator of the platform; Wadi Watch acts on a risk polygon, it does not predict one.

### Who pays

- Mines, farms, building sites and logistics firms paying per enrolled worker
- Civil defence bodies and city councils on an annual licence
- Mobile operators, who earn from every API call and can bundle the slice

### Verification

Run `pytest -q` in the repository. The suite covers the CAMARA transport and
its provenance, the consent gate, budget enforcement, the tool allowlist, the
guardrail floor overruling an over-confident model, the LLM planner loop
against a scripted model, the full HTTP surface, and every shipped scenario.

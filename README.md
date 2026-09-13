# Wadi Watch

> The flood layer that checks who was never reached

**MENA Ignite Hackathon - GSMA Open Gateway - Theme 6: Climate Resilience & Environmental Monitoring**

Broadcast tells everyone. Wadi Watch finds out who never heard it, and hands the response team a short, ordered list instead of a city.

Cell broadcast already reaches every working phone in a cell. Wadi Watch is the layer on top that answers the question broadcast cannot: whose phone was off, out of battery or out of signal. It turns silence into an ordered search list with a last known area, and puts responders on a slice when the cell is saturated.

---

## Quick start

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000. You need no credentials, because the app starts in
`simulator` mode and every answer is tagged with its source.

Full instructions, including the Gemini planner and the live Nokia gateway, are
in **INSTRUCTIONS.md**. The design is in **ARCHITECTURE.md**.

## What it is

An AI agent that decides *which* CAMARA network check is worth making for a
given case, spends against a budget, refuses calls it has no consent for, and
explains every decision with the network answers behind it.

- **7 scenarios** ship with it, all reaching the outcome they claim
- **8 CAMARA APIs** on the Nokia Network-as-Code platform
- **74.9% cheaper** than calling every available check on every case
- **1 to 6 calls** per case, depending on what the case deserves

## Scenarios

- Enrolled, but outside the risk area. A street 4 km up the hill from the valley floor (expects `accounted`)
- Farm on the valley floor, phone answering. High-risk zone, line reachable on data (expects `warn`)
- Inside the alert, up the slope. Same alert area, lower-risk zone (expects `advise`)
- Basement flat, unreachable. On the valley floor, network cannot reach the line at all (expects `search`)
- Site worker unreachable and the cell is saturated. Silent line plus a cell full of everyone else's calls (expects `search`)
- The network answers PARTIAL on the boundary. The line's uncertainty circle straddles the risk edge (expects `warn`)
- Enrol a line from the co-operative's list. Verify the number, then subscribe area-entered events for the wadi (expects `accounted`)

## CAMARA APIs used

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

## The agent

```
planner proposes one call  ->  runtime checks allowlist, consent, budget
      ^                                        |
      |                                        v
  answer becomes a fact   <-   CAMARA call recorded with provenance
      |
      +--> planner submits a decision  ->  policy floor applied  ->  ledger
```

The planner is Google AI Studio (Gemini) through Pydantic AI when
`AGENT_PROVIDER=gemini` and a `GEMINI_API_KEY` are both set, and a deterministic
policy ladder otherwise. Pydantic AI returns a typed proposal only; the runtime
still holds the budget, allowlist and consent gate, and the policy holds a floor
the model cannot talk its way under.

## Tests

```bash
pytest -q
```

## What this does not do

- Wadi Watch does not replace cell broadcast and does not try to. Broadcast reaches everyone; this reaches the people who were enrolled, and only them.
- An unreachable line is not proof that someone is in trouble. It is proof that nobody knows, which is the honest claim and still enough to order a search list by.
- Coverage equals enrolment. The people most at risk are often the hardest to enrol, and no API changes that. It is outreach work, not engineering.
- Hydrology is not ours. The risk areas here come from the operator of the platform; Wadi Watch acts on a risk polygon, it does not predict one.

## Layout

```
main.py            uvicorn entry point
app_spec.py        re-exports this product's spec
core/              shared platform: CAMARA client, agent, consent, ledger, UI
  camara.py        the eleven CAMARA API families, live + simulator
  simulator.py     deterministic network simulator
  agent.py         the agent loop, budget, guardrail
  tools.py         CAMARA tool registry with cost and reveal metadata
  consent.py       consent ledger enforced in the transport path
  ledger.py        SQLite decision ledger
  signals.py       CAMARA answers -> named facts
  server.py        FastAPI app
  webui.py         the operator console
idea/              this product: policy, scenarios, demo lines, copy
tests/             pytest suite
```

## Licence

MIT. See LICENSE.

"""Wadi Watch - the flood layer that checks who was never reached.

Cell broadcast already reaches every phone in a cell, and countries in the
region use it. That part is solved, and this product does not try to repeat it.

What is not solved is the answer coming back. Nobody knows whose phone was off,
out of battery or out of signal, so nobody knows who never heard the warning.
And one broadcast for a whole city is far too coarse for the people most at
risk: a valley farm, a building site, a basement flat.

So Wadi Watch is a second layer on top of broadcast, and it is built around a
constraint rather than against it. CAMARA geofencing works one line at a time
and needs that line owner's consent. There is no API that asks who is inside an
area. Enrolment is therefore not a compromise - it is the design, and it makes
the warning better, because an enrolled person has an address, a language and a
next of kin in the record that a broadcast never has.

The agent's job per enrolled line: establish whether this person is in the risk
area, whether they can be reached, and if not, put them at the top of an ordered
search list with somewhere for the team to start.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.agent import Case
from core.camara import ApiResult
from core.signals import read_signal

LEVELS = ["accounted", "advise", "warn", "search"]


class WadiWatchPolicy:
    name = "wadi-watch"
    kind = "flood_alert"
    levels = LEVELS
    budget_units = 24.0

    tool_names = [
        "verify_location",
        "check_reachability",
        "retrieve_location",
        "query_congestion",
        "reserve_quality",
        "attach_slice",
        "watch_area",
        "verify_number",
    ]

    def system_prompt(self, case: Case) -> str:
        return (
            "You are Wadi Watch, the agent inside a civil defence and site safety "
            "platform during a flash flood warning. You work one enrolled line at "
            "a time.\n\n"
            "You are not the broadcast. Cell broadcast already reached everyone "
            "with a working phone in the cell. Your job is the part broadcast "
            "cannot do: find out who was never reached, and give the response team "
            "an ordered list with somewhere to start.\n\n"
            "How to work:\n"
            "1. Ask the yes/no area question first. Most enrolled people are not "
            "in the risk area at all, and establishing that costs two units and "
            "reveals nothing.\n"
            "2. For anyone inside the area, the decisive question is reachability. "
            "Someone who answers gets a warning worded for their zone. Someone the "
            "network cannot reach at all is the person nobody knows about, and they "
            "go to the top of the search list.\n"
            "3. Only retrieve a position for a silent line. That is where the "
            "extra exposure is justified, because a team is about to walk there.\n"
            "4. Before promising the team video or telemetry, check whether the "
            "cell is saturated. Floods fill cells with calls at exactly the wrong "
            "moment. If it is saturated, put the responders on a slice.\n"
            "5. PARTIAL and UNKNOWN mean the line's uncertainty circle straddles "
            "the risk boundary. For flood risk, treat that as inside. This is the "
            "one place in this platform where the cautious reading wins, because "
            "the cost of being wrong is not symmetric.\n\n"
            "Every enrolled person consented and can leave at any time."
        )

    def describe_case(self, case: Case) -> str:
        f = case.facts
        return (
            "Flood alert: %s\n"
            "  person: %s, household of %s, speaks %s\n"
            "  enrolled zone: %s (risk: %s)\n"
            "  next of kin on record: %s\n"
            "  risk area: %s m radius\n"
            "  line: %s"
            % (
                f.get("event", "alert"),
                f.get("person", "unknown"),
                f.get("household", "unknown"),
                f.get("language", "unknown"),
                f.get("zone_name", "unknown"),
                f.get("zone_risk", "unknown"),
                "yes" if f.get("next_of_kin") else "no",
                case.radius_m,
                case.subject,
            )
        )

    def interpret(self, tool: str, result: ApiResult, facts: Dict[str, Any]) -> Dict[str, Any]:
        return read_signal(tool, result)

    def next_tool(
        self, case: Case, facts: Dict[str, Any], used: List[str]
    ) -> Optional[Tuple[str, Dict[str, Any], str]]:
        if case.facts.get("event") == "enrol":
            return self._enrol(case, facts)

        if "location_result" not in facts:
            return (
                "verify_location",
                {},
                "Two units to ask whether this enrolled line is inside the risk "
                "area at all. Most are not, and no coordinates come back.",
            )

        if facts.get("location_outside"):
            return None  # nothing further is worth buying

        if "reachability" not in facts:
            return (
                "check_reachability",
                {},
                "This line is in the risk area. Whether the network can reach it "
                "is the single thing broadcast cannot tell anyone, and it decides "
                "between a warning and a search.",
            )

        if facts.get("reachable"):
            return None  # they can be warned; stop spending

        if "has_last_known_point" not in facts:
            return (
                "retrieve_location",
                {},
                "Silent line inside the risk area. A team is about to walk to this "
                "person, so a last known area is now worth the extra exposure.",
            )

        if "congestion" not in facts:
            return (
                "query_congestion",
                {},
                "Find out whether the cell is saturated before the response team "
                "relies on it. A flood fills cells with calls at the worst moment.",
            )

        if facts.get("cell_saturated") and "slice_attachment_id" not in facts:
            return (
                "attach_slice",
                {"slice_id": case.params.get("slice_id", "civil-defence-slice")},
                "The cell is saturated. Put the responder line on the civil "
                "defence slice so their maps and video keep working while everyone "
                "else's calls fail.",
            )

        if facts.get("cell_crowded") and "qod_session_id" not in facts:
            return (
                "reserve_quality",
                {"profile": "QOS_L", "duration_s": 1200},
                "The cell is busy but not saturated, so a reserved quality session "
                "is proportionate and much cheaper than a slice.",
            )
        return None

    def _enrol(self, case: Case, facts: Dict[str, Any]):
        if "number_verified" not in facts:
            return (
                "verify_number",
                {},
                "Confirm the line before adding it to the register, so a typo does "
                "not put a stranger on a flood warning list.",
            )
        if not facts.get("number_verified"):
            return None
        if "geofence_id" not in facts:
            return (
                "watch_area",
                {"event": "entered", "radius_m": case.radius_m},
                "Subscribe this one consented line to area-entered events for the "
                "risk zone. This is the only shape CAMARA geofencing supports, and "
                "it is why the product enrols people instead of sweeping a map.",
            )
        return None

    # -- the floor -----------------------------------------------------------

    def decide(self, case: Case, facts: Dict[str, Any]) -> Tuple[str, str, str, float]:
        if case.facts.get("event") == "enrol":
            return self._decide_enrol(case, facts)

        f = case.facts
        person = f.get("person", "this person")
        zone = f.get("zone_name", "their zone")
        high_risk = str(f.get("zone_risk", "")).lower() == "high"
        language = f.get("language", "their language")

        if "location_result" not in facts:
            return (
                "advise",
                "Fall back to the cell broadcast for this person",
                "No network evidence was available for this line, so Wadi Watch "
                "cannot say whether they were reached. Broadcast is all there is.",
                0.35,
            )

        if facts.get("location_outside"):
            return (
                "accounted",
                "No action; this person is outside the risk area",
                "The network places this line outside the risk area, so %s does not "
                "need a targeted warning and no further checks were bought." % person,
                0.9,
            )

        if facts.get("silent"):
            detail = ""
            if facts.get("has_last_known_point"):
                detail = " A last known area is attached for the search team"
                if facts.get("slice_attachment_id"):
                    detail += ", and the responder line is on the civil defence slice because the cell is saturated"
                elif facts.get("qod_session_id"):
                    detail += ", with a reserved quality session for the team"
                detail += "."
            return (
                "search",
                "Put %s at the top of the search list for %s" % (person, zone),
                "This line is inside the risk area and the network cannot reach it "
                "at all. That is exactly the person a broadcast cannot account for, "
                "and the reason this layer exists. Household of %s, next of kin %s "
                "on record.%s"
                % (
                    f.get("household", "unknown size"),
                    "is" if f.get("next_of_kin") else "is not",
                    detail,
                ),
                0.92,
            )

        if facts.get("location_uncertain"):
            return (
                "warn",
                "Warn %s in %s and treat them as inside the area" % (person, language),
                "The network could not answer cleanly, which means this line sits on "
                "the risk boundary. For flood risk the cautious reading wins: the "
                "cost of a warning nobody needed is a minute of attention, and the "
                "cost of the other mistake is a person.",
                0.8,
            )

        if high_risk:
            return (
                "warn",
                "Send the %s warning for %s in %s, and confirm receipt" % (zone, person, language),
                "%s is inside the risk area, reachable, and enrolled in a high-risk "
                "zone. Because they are enrolled the warning can name their zone and "
                "their language instead of repeating a city-wide broadcast." % person,
                0.9,
            )

        return (
            "advise",
            "Send the informational notice for %s in %s" % (zone, language),
            "%s is inside the alerted area but enrolled in a lower-risk zone. A "
            "street on the hill and a farm on the valley floor should not get the "
            "same words, which is the whole reason for zone-level enrolment." % person,
            0.85,
        )

    def _decide_enrol(self, case: Case, facts: Dict[str, Any]):
        person = case.facts.get("person", "this person")
        if not facts.get("number_verified", True):
            return (
                "advise",
                "Re-check the number before enrolling",
                "The network would not confirm this line, so it should not go onto "
                "a flood warning register where a typo reaches a stranger.",
                0.8,
            )
        if facts.get("geofence_active"):
            return (
                "accounted",
                "%s is enrolled for %s" % (person, case.facts.get("zone_name", "their zone")),
                "The line is confirmed and an area-entered subscription is active "
                "for the risk zone. Consent was given once and can be withdrawn at "
                "any time, which cancels this subscription.",
                0.92,
            )
        return (
            "advise",
            "Retry the geofence subscription",
            "The line verified but the area subscription did not come back active.",
            0.6,
        )

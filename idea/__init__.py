"""Wadi Watch product spec: theme 6, climate resilience and environmental monitoring."""

from __future__ import annotations

from core.agent import Case
from core.idea import ConsentPlan, IdeaSpec, LevelStyle, Scenario, UiSpec
from core.simulator import LineProfile

from .policy import WadiWatchPolicy

POLICY = WadiWatchPolicy()

# A wadi north-east of Jeddah. The risk area is the valley floor, 1.5 km across.
WADI = (21.5200, 39.2400)
RISK_RADIUS_M = 1500
_M_PER_DEG_LAT = 111320.0


def _uphill(metres: float) -> tuple:
    return (WADI[0] + metres / _M_PER_DEG_LAT, WADI[1])


LINE_HILL = LineProfile(
    msisdn="+966570000401",
    label="Street on the hill, 4 km from the valley floor",
    latitude=_uphill(4000)[0],
    longitude=_uphill(4000)[1],
    location_accuracy_m=300,
    notes="Outside the risk area. One question, one answer, no spend.",
)

LINE_FARM = LineProfile(
    msisdn="+966570000402",
    label="Farm on the valley floor, phone answering",
    latitude=WADI[0],
    longitude=WADI[1],
    location_accuracy_m=400,
    notes="Reachable, so they get a warning worded for their zone.",
)

LINE_LOW_RISK = LineProfile(
    msisdn="+966570000403",
    label="Apartment inside the alerted area but up the slope",
    latitude=_uphill(900)[0],
    longitude=_uphill(900)[1],
    location_accuracy_m=300,
    notes="Same alert, different words. A hill street is not a valley farm.",
)

LINE_BASEMENT = LineProfile(
    msisdn="+966570000404",
    label="Basement flat on the valley floor, unreachable",
    latitude=_uphill(200)[0],
    longitude=_uphill(200)[1],
    location_accuracy_m=500,
    reachability="NOT_CONNECTED",
    congestion="low",
    notes="The person a broadcast can never account for.",
)

LINE_SITE = LineProfile(
    msisdn="+966570000405",
    label="Building site worker, unreachable, cell saturated",
    latitude=_uphill(600)[0],
    longitude=_uphill(600)[1],
    location_accuracy_m=600,
    reachability="NOT_CONNECTED",
    congestion="high",
    congestion_confidence=92,
    notes="Silent line plus a saturated cell: responders go on a slice.",
)

LINE_EDGE = LineProfile(
    msisdn="+966570000406",
    label="On the risk boundary, network answers PARTIAL",
    latitude=_uphill(1520)[0],
    longitude=_uphill(1520)[1],
    location_accuracy_m=700,
    force_verification="PARTIAL",
    notes="For flood risk, the cautious reading wins.",
)

LINE_ENROL = LineProfile(
    msisdn="+966570000407",
    label="New enrolment from the co-operative's own list",
    latitude=WADI[0],
    longitude=WADI[1],
    location_accuracy_m=400,
    notes="Verify the line, then subscribe area-entered events.",
)


def _alert(subject: str, person: str, zone: str, risk: str, household: int,
           language: str, label: str, next_of_kin: bool = True) -> Case:
    return Case(
        subject=subject,
        kind="flood_alert",
        label=label,
        facts={
            "event": "alert",
            "person": person,
            "zone_name": zone,
            "zone_risk": risk,
            "household": household,
            "language": language,
            "next_of_kin": next_of_kin,
        },
        latitude=WADI[0],
        longitude=WADI[1],
        radius_m=RISK_RADIUS_M,
        params={"slice_id": "civil-defence-slice", "qos_profile": "QOS_L"},
    )


SCENARIOS = [
    Scenario(
        id="hill-street-outside",
        title="Enrolled, but outside the risk area",
        subtitle="A street 4 km up the hill from the valley floor",
        expect_level="accounted",
        lines=[LINE_HILL],
        narrative="Most enrolled people are not in danger, and proving it is cheap.",
        teaches=(
            "One yes/no area question settles it. No position is retrieved, nothing "
            "about this household is learned, and the search list stays short."
        ),
        build_case=lambda: _alert(
            LINE_HILL.msisdn, "Mr Al-Harbi", "Hill Street", "low", 4, "Arabic",
            "Outside the risk area",
        ),
    ),
    Scenario(
        id="valley-farm-reachable",
        title="Farm on the valley floor, phone answering",
        subtitle="High-risk zone, line reachable on data",
        expect_level="warn",
        lines=[LINE_FARM],
        narrative="A warning that knows whose warning it is.",
        teaches=(
            "Because this person was enrolled rather than swept off a map, the "
            "warning can name their zone, their language and their household size. "
            "A broadcast cannot do any of that."
        ),
        build_case=lambda: _alert(
            LINE_FARM.msisdn, "Umm Yousef", "Wadi Floor", "high", 7, "Arabic",
            "Valley farm, reachable",
        ),
    ),
    Scenario(
        id="low-risk-advisory",
        title="Inside the alert, up the slope",
        subtitle="Same alert area, lower-risk zone",
        expect_level="advise",
        lines=[LINE_LOW_RISK],
        narrative="One alert, two different messages.",
        teaches=(
            "A city-wide broadcast gives a hill apartment and a valley farm the "
            "same words. Zone-level enrolment is what lets this one be an advisory "
            "while the farm gets an evacuation warning."
        ),
        build_case=lambda: _alert(
            LINE_LOW_RISK.msisdn, "Ms Rahma", "Upper Slope", "low", 2, "Arabic",
            "Inside the alert, low-risk zone",
        ),
    ),
    Scenario(
        id="basement-flat-silent",
        title="Basement flat, unreachable",
        subtitle="On the valley floor, network cannot reach the line at all",
        expect_level="search",
        lines=[LINE_BASEMENT],
        narrative="The reason this product exists.",
        teaches=(
            "Broadcast went out and nobody knows whether it landed. Reachability "
            "answers that: this line cannot be reached, so it goes to the top of "
            "the search list with a last known area, a household size and a next "
            "of kin the team can call."
        ),
        build_case=lambda: _alert(
            LINE_BASEMENT.msisdn, "Mr Idris", "Wadi Floor", "high", 5, "Amharic",
            "Basement flat, silent",
        ),
    ),
    Scenario(
        id="site-silent-saturated",
        title="Site worker unreachable and the cell is saturated",
        subtitle="Silent line plus a cell full of everyone else's calls",
        expect_level="search",
        lines=[LINE_SITE],
        narrative="When the network itself becomes the obstacle.",
        teaches=(
            "Same search outcome as the basement flat, but one extra finding "
            "changes what the responders get: a saturated cell means their maps and "
            "video would fail, so the agent attaches the responder line to the "
            "civil defence slice. Slices are expensive and only a declared incident "
            "earns one."
        ),
        build_case=lambda: _alert(
            LINE_SITE.msisdn, "Site worker 214", "Wadi Floor", "high", 1, "Bengali",
            "Site worker, silent, saturated cell", next_of_kin=False,
        ),
    ),
    Scenario(
        id="boundary-uncertain",
        title="The network answers PARTIAL on the boundary",
        subtitle="The line's uncertainty circle straddles the risk edge",
        expect_level="warn",
        lines=[LINE_EDGE],
        narrative="The one place the cautious reading should win.",
        teaches=(
            "Elsewhere in this platform an uncertain answer holds back an "
            "accusation. Here the costs are not symmetric: a warning nobody needed "
            "costs a minute, the other mistake costs a person. So PARTIAL is "
            "treated as inside."
        ),
        build_case=lambda: _alert(
            LINE_EDGE.msisdn, "Mr Osman", "Wadi Edge", "high", 3, "Arabic",
            "Boundary case, uncertain fix",
        ),
    ),
    Scenario(
        id="enrol-from-list",
        title="Enrol a line from the co-operative's list",
        subtitle="Verify the number, then subscribe area-entered events for the wadi",
        expect_level="accounted",
        lines=[LINE_ENROL],
        narrative="Where the consent and the constraint meet.",
        teaches=(
            "There is no CAMARA API that asks who is inside an area, so the product "
            "is built the only way it can be: one consented line at a time, from "
            "lists cities and co-operatives already keep."
        ),
        build_case=lambda: Case(
            subject=LINE_ENROL.msisdn,
            kind="flood_alert",
            label="Enrolment from the farm co-operative list",
            facts={
                "event": "enrol",
                "person": "Mr Sabri",
                "zone_name": "Wadi Floor",
                "zone_risk": "high",
                "household": 6,
                "language": "Arabic",
                "next_of_kin": True,
            },
            latitude=WADI[0],
            longitude=WADI[1],
            radius_m=RISK_RADIUS_M,
            params={"webhook_url": "https://wadiwatch.example/hooks/geofence"},
        ),
    ),
]

SPEC = IdeaSpec(
    slug="wadi-watch",
    name="Wadi Watch",
    tagline="The flood layer that checks who was never reached",
    theme_number=6,
    theme_name="Climate Resilience & Environmental Monitoring",
    submission_title="Wadi Watch - the flood layer that checks who was never reached",
    submission_description=(
        "Cell broadcast already reaches every working phone in a cell. Wadi Watch "
        "is the layer on top that answers the question broadcast cannot: whose "
        "phone was off, out of battery or out of signal. It turns silence into an "
        "ordered search list with a last known area, and puts responders on a "
        "slice when the cell is saturated."
    ),
    policy=POLICY,
    scenarios=SCENARIOS,
    lines=[
        LINE_HILL,
        LINE_FARM,
        LINE_LOW_RISK,
        LINE_BASEMENT,
        LINE_SITE,
        LINE_EDGE,
        LINE_ENROL,
    ],
    consent=ConsentPlan(
        moment="at enrolment, from lists cities, site owners and co-operatives already keep",
        scopes=[
            "identity:verify",
            "location:verify",
            "location:retrieve",
            "location:geofence",
            "device:status",
            "network:insights",
            "network:qod",
            "network:slice",
        ],
        who_consents="the enrolled resident or worker, who owns the line and agrees once",
        duration_note=(
            "Checks run only while an alert is open for a zone that person is "
            "enrolled in. There is no monitoring between alerts."
        ),
        revocation=(
            "Anyone can leave the register at any time, which cancels their "
            "geofence subscription and every future check."
        ),
    ),
    ui=UiSpec(
        accent="#2d7fb8",
        accent_soft="#e4f1f9",
        hero_kicker=(
            "Broadcast tells everyone. Wadi Watch finds out who never heard it, and "
            "hands the response team a short, ordered list instead of a city."
        ),
        subject_label="Enrolled line (MSISDN)",
        case_label="Flood alert case",
        run_all_label="Run all seven alert cases",
        ad_hoc_placeholder="+966570000404",
        ad_hoc_help=(
            "An ad-hoc case runs the alert path against the wadi risk area. "
            "Unregistered numbers get a stable derived profile."
        ),
        levels=[
            LevelStyle("accounted", "Accounted for", "calm",
                       "Outside the risk area, or enrolled and confirmed."),
            LevelStyle("advise", "Advisory notice", "watch",
                       "Inside the alert but in a lower-risk zone."),
            LevelStyle("warn", "Warn and confirm receipt", "warn",
                       "Inside the risk area and reachable."),
            LevelStyle("search", "Top of the search list", "alarm",
                       "Inside the risk area and unreachable."),
        ],
    ),
    honest_limits=[
        "Wadi Watch does not replace cell broadcast and does not try to. Broadcast "
        "reaches everyone; this reaches the people who were enrolled, and only them.",
        "An unreachable line is not proof that someone is in trouble. It is proof "
        "that nobody knows, which is the honest claim and still enough to order a "
        "search list by.",
        "Coverage equals enrolment. The people most at risk are often the hardest "
        "to enrol, and no API changes that. It is outreach work, not engineering.",
        "Hydrology is not ours. The risk areas here come from the operator of the "
        "platform; Wadi Watch acts on a risk polygon, it does not predict one.",
    ],
    buyers=[
        "Mines, farms, building sites and logistics firms paying per enrolled worker",
        "Civil defence bodies and city councils on an annual licence",
        "Mobile operators, who earn from every API call and can bundle the slice",
    ],
    repo_name="wadi-watch-nac-agent",
    demo_notes=(
        "Run the basement flat and the site worker back to back. Same outcome, but "
        "the saturated cell in the second one earns a network slice."
    ),
)

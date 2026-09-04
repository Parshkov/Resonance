"""Prose extraction benchmark v0.2: short paragraphs with gold Thought Graphs.

Gold is authored by hand (agent parshkov-anthropic-fable51-uutj4x) and needs
independent review before external claims. Node matching in the evaluator is
by stem overlap, so gold labels are short content phrases; edges are
(source label, type, target label, assertion, modality).
"""

CASES = [
    {
        "id": "X01-battery", "domain": "battery",
        "text": "Batteries overheat under sustained load. The heat builds up because the cooling is undersized, "
                "which leads to electrolyte degradation and eventually cell failure. Active cooling prevents the "
                "buildup, but the charging speed limit constrains how aggressive cooling can be.",
        "nodes": [("cooling is undersized", "method"), ("heat builds up", "state"), ("electrolyte degradation", "state"),
                  ("cell failure", "outcome"), ("active cooling", "method"), ("buildup", "state"),
                  ("charging speed limit", "constraint"), ("aggressive cooling", "method")],
        "edges": [("cooling is undersized", "causes", "heat builds up", "asserted", "actual"),
                  ("heat builds up", "causes", "electrolyte degradation", "asserted", "actual"),
                  ("heat builds up", "causes", "cell failure", "asserted", "actual"),
                  ("active cooling", "prevents", "buildup", "asserted", "actual"),
                  ("charging speed limit", "constrains", "aggressive cooling", "asserted", "actual")],
    },
    {
        "id": "X02-retry-storm", "domain": "software",
        "text": "Slow responses cause client retries, which cause a request storm, and the storm causes the outage. "
                "Exponential backoff limits the retries. The root cause of the outage was never found.",
        "nodes": [("slow responses", "state"), ("client retries", "mechanism"), ("request storm", "state"),
                  ("outage", "outcome"), ("exponential backoff", "method")],
        "edges": [("slow responses", "causes", "client retries", "asserted", "actual"),
                  ("client retries", "causes", "request storm", "asserted", "actual"),
                  ("request storm", "causes", "outage", "asserted", "actual"),
                  ("exponential backoff", "constrains", "client retries", "asserted", "actual")],
    },
    {
        "id": "X03-fever", "domain": "medicine",
        "text": "The fever might be caused by a bacterial infection; the blood culture results support that hypothesis "
                "and contradict the viral hypothesis. Running the culture requires laboratory capacity.",
        "nodes": [("fever", "state"), ("bacterial infection", "problem"), ("blood culture results", "evidence"),
                  ("hypothesis", "state"), ("viral hypothesis", "state"), ("running the culture", "method"),
                  ("laboratory capacity", "resource")],
        "edges": [("bacterial infection", "causes", "fever", "asserted", "possible"),
                  ("blood culture results", "supports", "hypothesis", "asserted", "actual"),
                  ("blood culture results", "contradicts", "viral hypothesis", "asserted", "actual"),
                  ("running the culture", "requires", "laboratory capacity", "asserted", "actual")],
    },
    {
        "id": "X04-breaker", "domain": "software",
        "text": "If the error rate crosses the alert threshold, the circuit breaker trips. This prevents the downstream "
                "service from being overloaded. The breaker requires an accurate error-rate metric.",
        "nodes": [("error rate crosses the alert threshold", "state"), ("circuit breaker trips", "method"),
                  ("downstream service overloaded", "outcome"), ("accurate error-rate metric", "evidence")],
        "edges": [("error rate crosses the alert threshold", "causes", "circuit breaker trips", "asserted", "conditional"),
                  ("circuit breaker trips", "prevents", "downstream service overloaded", "asserted", "actual"),
                  ("circuit breaker trips", "requires", "accurate error-rate metric", "asserted", "actual")],
    },
    {
        "id": "X05-negation", "domain": "organization",
        "text": "More meetings do not prevent the coordination breakdown. The breakdown stems from scattered teams, "
                "and it results in duplicated effort.",
        "nodes": [("more meetings", "method"), ("coordination breakdown", "state"), ("scattered teams", "state"),
                  ("duplicated effort", "outcome")],
        "edges": [("more meetings", "prevents", "coordination breakdown", "negated", "actual"),
                  ("scattered teams", "causes", "coordination breakdown", "asserted", "actual"),
                  ("coordination breakdown", "causes", "duplicated effort", "asserted", "actual")],
    },
    {
        "id": "X06-fishery", "domain": "ecology",
        "text": "Growing fishing demand depletes the spawning stock. The protected reserve is part of the recovery plan "
                "and prevents further depletion. Declining catch records indicate that the stock is collapsing.",
        "nodes": [("growing fishing demand", "state"), ("spawning stock", "resource"), ("protected reserve", "method"),
                  ("recovery plan", "method"), ("further depletion", "state"), ("declining catch records", "evidence"),
                  ("stock is collapsing", "outcome")],
        "edges": [("growing fishing demand", "prevents", "spawning stock", "asserted", "actual"),
                  ("protected reserve", "part_of", "recovery plan", "asserted", "actual"),
                  ("protected reserve", "prevents", "further depletion", "asserted", "actual"),
                  ("declining catch records", "supports", "stock is collapsing", "asserted", "actual")],
        "notes": "'depletes' is read as a prevents-class cue (reduces); gold accepts prevents for it.",
    },
    {
        "id": "X07-tech-debt", "domain": "software",
        "text": "Release deadline pressure drives quick hacks instead of proper design. The hacks accumulate as technical "
                "debt, and the debt slows every later change. Paying down the debt requires a refactoring budget.",
        "nodes": [("release deadline pressure", "constraint"), ("quick hacks", "method"), ("technical debt", "state"),
                  ("later change", "state"), ("paying down the debt", "method"), ("refactoring budget", "resource")],
        "edges": [("release deadline pressure", "causes", "quick hacks", "asserted", "actual"),
                  ("technical debt", "prevents", "later change", "asserted", "actual"),
                  ("paying down the debt", "requires", "refactoring budget", "asserted", "actual")],
        "notes": "'slows' maps to prevents-class (reduces); 'accumulate as' has no cue and is abstained.",
    },
    {
        "id": "X08-grid", "domain": "power",
        "text": "A transformer fault in one substation triggered a cascading blackout because the transmission lines are "
                "tightly interconnected. Islanding the grid sections would have prevented the cascade, but islanding "
                "depends on spare generation capacity.",
        "nodes": [("transformer fault", "problem"), ("cascading blackout", "outcome"), ("transmission lines interconnected", "mechanism"),
                  ("islanding the grid sections", "method"), ("cascade", "mechanism"), ("spare generation capacity", "resource")],
        "edges": [("transformer fault", "causes", "cascading blackout", "asserted", "actual"),
                  ("transmission lines interconnected", "causes", "cascading blackout", "asserted", "actual"),
                  ("islanding the grid sections", "prevents", "cascade", "asserted", "conditional"),
                  ("islanding the grid sections", "requires", "spare generation capacity", "asserted", "actual")],
    },
    {
        "id": "X09-sleep", "domain": "health",
        "text": "Exam week pressure makes students skip sleep. Sleep debt accumulates and causes sluggish thinking, "
                "which in turn slows their studying. Rest days reduce the debt.",
        "nodes": [("exam week pressure", "constraint"), ("students skip sleep", "method"), ("sleep debt", "state"),
                  ("sluggish thinking", "state"), ("studying", "state"), ("rest days", "method")],
        "edges": [("exam week pressure", "causes", "students skip sleep", "asserted", "actual"),
                  ("sleep debt", "causes", "sluggish thinking", "asserted", "actual"),
                  ("sluggish thinking", "prevents", "studying", "asserted", "actual"),
                  ("rest days", "prevents", "sleep debt", "asserted", "actual")],
    },
    {
        "id": "X10-thermostat", "domain": "control",
        "text": "When the room temperature passes the set point, the thermostat switches the cooling on, which stops "
                "the room from overheating. The thermostat relies on the temperature sensor reading.",
        "nodes": [("room temperature passes the set point", "state"), ("thermostat switches the cooling on", "method"),
                  ("room overheating", "outcome"), ("temperature sensor reading", "evidence")],
        "edges": [("room temperature passes the set point", "causes", "thermostat switches the cooling on", "asserted", "conditional"),
                  ("thermostat switches the cooling on", "prevents", "room overheating", "asserted", "actual"),
                  ("thermostat switches the cooling on", "requires", "temperature sensor reading", "asserted", "actual")],
    },
    {
        "id": "X11-startup", "domain": "finance",
        "text": "Rapid spending growth is draining the cash runway, and the company could go bankrupt as a result. "
                "An emergency reserve fund would prevent the shortfall. The burn rate dashboard shows the runway shrinking.",
        "nodes": [("rapid spending growth", "state"), ("cash runway", "resource"), ("company could go bankrupt", "outcome"),
                  ("emergency reserve fund", "method"), ("shortfall", "state"), ("burn rate dashboard", "evidence"),
                  ("runway shrinking", "state")],
        "edges": [("emergency reserve fund", "prevents", "shortfall", "asserted", "conditional"),
                  ("burn rate dashboard", "supports", "runway shrinking", "asserted", "actual")],
        "notes": "'is draining' and 'as a result' with a pronoun subject are hard; gold only requires the two explicit ones.",
    },
    {
        "id": "X12-coral", "domain": "science",
        "text": "The cause of the coral die-off is unclear. A controlled temperature experiment produced bleaching "
                "measurements that support the heat stress hypothesis and rule out the pollution hypothesis. The "
                "experiment required research vessel time.",
        "nodes": [("controlled temperature experiment", "method"), ("bleaching measurements", "evidence"),
                  ("heat stress hypothesis", "state"), ("pollution hypothesis", "state"), ("research vessel time", "resource")],
        "edges": [("controlled temperature experiment", "causes", "bleaching measurements", "asserted", "actual"),
                  ("bleaching measurements", "supports", "heat stress hypothesis", "asserted", "actual"),
                  ("bleaching measurements", "contradicts", "pollution hypothesis", "asserted", "actual"),
                  ("controlled temperature experiment", "requires", "research vessel time", "asserted", "actual")],
    },
    {
        "id": "X13-warehouse", "domain": "logistics",
        "text": "An inbound surge causes staging pile-ups, and the pile-ups cause dock congestion. Congestion leads to "
                "missed SLAs. Wave planning reduces the pile-ups, but the labor cap limits wave planning.",
        "nodes": [("inbound surge", "problem"), ("staging pile-ups", "state"), ("dock congestion", "state"),
                  ("missed SLAs", "outcome"), ("wave planning", "method"), ("labor cap", "constraint")],
        "edges": [("inbound surge", "causes", "staging pile-ups", "asserted", "actual"),
                  ("staging pile-ups", "causes", "dock congestion", "asserted", "actual"),
                  ("dock congestion", "causes", "missed SLAs", "asserted", "actual"),
                  ("wave planning", "prevents", "staging pile-ups", "asserted", "actual"),
                  ("labor cap", "constrains", "wave planning", "asserted", "actual")],
    },
    {
        "id": "X14-hospital-handoff", "domain": "medicine",
        "text": "Care is split across separate departments, so handoff notes go missing between shifts. Missing notes "
                "result in conflicting medication orders. A structured handoff protocol prevents the conflicts, and "
                "the discharge time limit constrains the protocol.",
        "nodes": [("care is split across separate departments", "state"), ("handoff notes go missing", "problem"),
                  ("conflicting medication orders", "state"), ("structured handoff protocol", "method"),
                  ("conflicts", "state"), ("discharge time limit", "constraint")],
        "edges": [("care is split across separate departments", "causes", "handoff notes go missing", "asserted", "actual"),
                  ("handoff notes go missing", "causes", "conflicting medication orders", "asserted", "actual"),
                  ("structured handoff protocol", "prevents", "conflicts", "asserted", "actual"),
                  ("discharge time limit", "constrains", "structured handoff protocol", "asserted", "actual")],
    },
    {
        "id": "X15-pii", "domain": "organization",
        "text": "My manager bob@acme.com blocks every proposal. The blocking causes low morale, and low morale leads to "
                "attrition.",
        "nodes": [("manager", "agent"), ("every proposal", "state"), ("blocking", "mechanism"), ("low morale", "state"),
                  ("attrition", "outcome")],
        "edges": [("manager", "prevents", "every proposal", "asserted", "actual"),
                  ("blocking", "causes", "low morale", "asserted", "actual"),
                  ("low morale", "causes", "attrition", "asserted", "actual")],
        "forbidden_label_text": ["acme", "bob@"],
    },
    {
        "id": "X16-modality", "domain": "software",
        "text": "Garbage collection pauses probably cause the latency spikes. Profiling could confirm the GC hypothesis. "
                "Unless we add memory, the pauses will keep growing.",
        "nodes": [("garbage collection pauses", "mechanism"), ("latency spikes", "state"), ("profiling", "method"),
                  ("GC hypothesis", "state"), ("add memory", "method"), ("pauses will keep growing", "state")],
        "edges": [("garbage collection pauses", "causes", "latency spikes", "asserted", "possible"),
                  ("profiling", "supports", "GC hypothesis", "asserted", "possible"),
                  ("add memory", "causes", "pauses will keep growing", "asserted", "conditional")],
    },
    {
        "id": "X17-composition", "domain": "manufacturing",
        "text": "The assembly line consists of three welding cells and a paint station. Skipping maintenance on the "
                "welding cells increases the defect rate, and a high defect rate causes scrap.",
        "nodes": [("assembly line", "resource"), ("three welding cells", "resource"), ("paint station", "resource"),
                  ("skipping maintenance", "method"), ("defect rate", "state"), ("scrap", "outcome")],
        "edges": [("three welding cells", "part_of", "assembly line", "asserted", "actual"),
                  ("paint station", "part_of", "assembly line", "asserted", "actual"),
                  ("skipping maintenance", "causes", "defect rate", "asserted", "actual"),
                  ("defect rate", "causes", "scrap", "asserted", "actual")],
    },
    {
        "id": "X18-trust", "domain": "organization",
        "text": "Repeated billing errors erode customer trust. Eroded trust leads to churn, and churn reduces revenue. "
                "An audit of the billing code would prevent the errors, but the audit needs two engineers for a month.",
        "nodes": [("repeated billing errors", "problem"), ("customer trust", "state"), ("churn", "state"),
                  ("revenue", "resource"), ("audit of the billing code", "method"), ("errors", "problem"),
                  ("two engineers", "resource")],
        "edges": [("customer trust", "causes", "churn", "asserted", "actual"),
                  ("churn", "prevents", "revenue", "asserted", "actual"),
                  ("audit of the billing code", "prevents", "errors", "asserted", "conditional"),
                  ("audit of the billing code", "requires", "two engineers", "asserted", "actual")],
        "notes": "'erode' is not a cue in v0.2; the first sentence is abstained.",
    },
    {
        "id": "X19-irrigation", "domain": "ecology",
        "text": "Canal silt load produces a sediment cascade that shoals the channel. Shoaling limits the irrigation "
                "quota. A flushing schedule counteracts the shoaling, and the depth gauge readings show the channel "
                "recovering.",
        "nodes": [("canal silt load", "problem"), ("sediment cascade", "mechanism"), ("channel", "state"),
                  ("shoaling", "state"), ("irrigation quota", "constraint"), ("flushing schedule", "method"),
                  ("depth gauge readings", "evidence"), ("channel recovering", "outcome")],
        "edges": [("canal silt load", "causes", "sediment cascade", "asserted", "actual"),
                  ("shoaling", "constrains", "irrigation quota", "asserted", "actual"),
                  ("flushing schedule", "prevents", "shoaling", "asserted", "actual"),
                  ("depth gauge readings", "supports", "channel recovering", "asserted", "actual")],
    },
    {
        "id": "X20-noise", "domain": "software",
        "text": "Nothing happened this week. We had lunch, and the weather was nice.",
        "nodes": [], "edges": [],
        "notes": "No relational content: an empty graph is the correct answer.",
    },
    {
        "id": "X21-because-chain", "domain": "education",
        "text": "Students plateau because the course skips prerequisites. The plateau is not caused by low motivation; "
                "the mastery quizzes show steady effort. Scaffolded practice prevents the plateau but requires "
                "contact hours.",
        "nodes": [("students plateau", "state"), ("course skips prerequisites", "problem"), ("low motivation", "state"),
                  ("mastery quizzes", "evidence"), ("steady effort", "state"), ("scaffolded practice", "method"),
                  ("contact hours", "resource")],
        "edges": [("course skips prerequisites", "causes", "students plateau", "asserted", "actual"),
                  ("low motivation", "causes", "students plateau", "negated", "actual"),
                  ("mastery quizzes", "supports", "steady effort", "asserted", "actual"),
                  ("scaffolded practice", "prevents", "students plateau", "asserted", "actual"),
                  ("scaffolded practice", "requires", "contact hours", "asserted", "actual")],
    },
    {
        "id": "X22-bank-run", "domain": "finance",
        "text": "A rumor about bad loans triggered withdrawals, and the withdrawals drained the bank's liquidity. "
                "Because the banks are entangled through interbank lending, one failure spreads to others. "
                "Ring-fencing retail deposits would block the contagion.",
        "nodes": [("rumor about bad loans", "problem"), ("withdrawals", "state"), ("liquidity", "resource"),
                  ("banks are entangled", "mechanism"), ("one failure spreads to others", "outcome"),
                  ("ring-fencing retail deposits", "method"), ("contagion", "mechanism")],
        "edges": [("rumor about bad loans", "causes", "withdrawals", "asserted", "actual"),
                  ("banks are entangled", "causes", "one failure spreads to others", "asserted", "actual"),
                  ("ring-fencing retail deposits", "prevents", "contagion", "asserted", "conditional")],
        "notes": "'drained' is not a cue; the liquidity edge is abstained.",
    },
]

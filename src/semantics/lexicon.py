"""Hand-authored lexicon of abstract relational concepts.

This is the deterministic, inspectable replacement for "ask an embedding model
whether two labels mean the same thing". Every concept class names a
domain-independent *relational* notion (accumulation, depletion, cascade,
constraint, ...) and lists the surface forms that realise it in ordinary
prose. Matching is done on Porter stems, so only base forms are needed.

The lexicon is versioned; changing it changes fingerprint/config hashes.

Design rule: a class is admitted only if it is *the kind of thing* that can
correspond across domains in an analogy. Domain nouns (battery, hospital)
belong to the DOMAIN classes at the end and never carry analogical weight;
they only support same-domain (direct) resonance.
"""

from __future__ import annotations

from .stem import stem

LEXICON_VERSION = "resonance-lexicon/0.2.1"

# concept -> (role_hint | None, terms)
# role_hint feeds extraction and soft role compatibility; None = no hint.
CONCEPTS: dict[str, tuple[str | None, tuple[str, ...]]] = {
    # ---- accumulation / depletion dynamics -------------------------------
    "ACCUMULATION": ("state", ("accumulate", "accumulation", "buildup", "build up", "build-up", "pile up",
                               "pileup", "backlog", "stockpile", "amass", "hoard", "gather", "mount up",
                               "mounting", "heap", "overflow", "glut", "excess", "surplus", "congest",
                               "congestion", "clog", "silt up", "sediment", "residue")),
    "DEPLETION": ("state", ("deplete", "depletion", "exhaust", "exhaustion", "drain", "run out", "shortage",
                            "scarcity", "scarce", "starve", "starvation", "deficit", "dwindle", "erode",
                            "erosion", "attrition", "run dry", "burn through", "underfund")),
    "GROWTH": ("state", ("grow", "growth", "increase", "rise", "rising", "expand", "expansion", "escalate",
                         "escalation", "surge", "spike", "swell", "inflate", "climb", "boom", "scale up",
                         "proliferate", "proliferation", "multiply")),
    "DECLINE": ("state", ("decline", "decrease", "drop", "fall", "falling", "shrink", "contract",
                          "contraction", "slump", "diminish", "reduce", "reduction", "lower", "wane",
                          "recede", "taper", "slow down", "slowdown", "downturn")),
    "DEGRADATION": ("state", ("degrade", "degradation", "deteriorate", "deterioration", "decay", "wear",
                              "wear out", "worn", "corrode", "corrosion", "rot", "fatigue", "weaken",
                              "weakening", "impair", "impairment", "breakdown", "break down", "fray",
                              "rust", "aging", "ageing", "obsolescence", "erosion of")),
    "SATURATION": ("state", ("saturate", "saturation", "full", "at capacity", "maxed out", "overload",
                             "overloaded", "overwhelm", "overwhelmed", "swamped", "oversubscribed",
                             "exceed capacity", "tipping point", "critical mass")),
    "LEAK": ("mechanism", ("leak", "leakage", "seep", "seepage", "escape", "spill", "spillage", "bleed",
                           "loss of", "drip", "lossy")),
    # ---- flow / throughput --------------------------------------------------
    "FLOW": ("mechanism", ("flow", "stream", "throughput", "traffic", "circulate", "circulation", "transfer",
                           "transmission", "transmit", "pass through", "conduct", "conduction", "pipeline",
                           "channel", "movement of")),
    "BOTTLENECK": ("constraint", ("bottleneck", "chokepoint", "choke point", "single point", "narrow",
                                  "constriction", "queue", "queueing", "waiting line", "backpressure",
                                  "back pressure", "contention", "serialization point")),
    "BLOCKAGE": ("state", ("block", "blockage", "blocked", "obstruct", "obstruction", "jam", "stall",
                           "stalled", "stuck", "deadlock", "gridlock", "halt", "freeze", "frozen",
                           "clot", "impasse", "standstill")),
    "DELAY": ("state", ("delay", "latency", "lag", "slow", "slowness", "wait", "waiting", "postpone",
                        "postponement", "late", "lateness", "overdue", "response time", "turnaround",
                        "sluggish", "backlog of requests", "time to", "slower", "slowing", "slows", "slowed", "sluggish thinking", "slow progress")),
    "ACCELERATION": ("mechanism", ("accelerate", "acceleration", "speed up", "faster", "hasten", "expedite",
                                   "quicken", "rush", "fast track", "fast-track")),
    # ---- feedback / propagation -------------------------------------------
    "FEEDBACK": ("mechanism", ("feedback", "feedback loop", "loop", "self-reinforcing", "self reinforcing",
                               "vicious cycle", "virtuous cycle", "vicious circle", "reinforce",
                               "reinforcement", "recursive", "compounding", "compound", "snowball",
                               "spiral", "runaway", "positive feedback", "negative feedback")),
    "AMPLIFICATION": ("mechanism", ("amplify", "amplification", "magnify", "magnification", "multiplier",
                                    "multiply", "intensify", "intensification", "exacerbate", "worsen",
                                    "aggravate", "boost", "leverage", "gain", "amplifier")),
    "CASCADE": ("mechanism", ("cascade", "cascading", "domino", "chain reaction", "knock-on", "knock on",
                              "ripple", "ripple effect", "contagion", "spread", "spreading", "propagate",
                              "propagation", "spillover", "spill over", "avalanche", "run on", "bank run",
                              "panic", "stampede", "herd", "sequential failure", "chain of failures")),
    "DAMPING": ("mechanism", ("damp", "damping", "dampen", "attenuate", "attenuation", "absorb", "absorption",
                              "cushion", "buffer against", "smooth", "smoothing", "stabilize", "stabilise",
                              "stabilization", "mitigate", "mitigation", "soften", "moderate", "temper",
                              "suppress", "suppression", "dissipate", "dissipation", "counteract",
                              "counterbalance", "offset", "hedge", "insulate", "insulation")),
    "OSCILLATION": ("state", ("oscillate", "oscillation", "swing", "fluctuate", "fluctuation", "volatile",
                              "volatility", "cycle", "cyclical", "periodic", "boom and bust", "seesaw",
                              "overshoot", "undershoot", "hunting", "instability", "unstable", "wobble",
                              "ringing")),
    # ---- load / stress / heat --------------------------------------------
    "LOAD": ("state", ("load", "demand", "burden", "workload", "traffic load", "request volume", "volume",
                       "peak", "peak load", "rush", "burst", "spike in", "strain", "usage", "utilization",
                       "utilisation", "throughput demand", "pressure of work", "caseload", "inflow", "influx", "intake", "incoming")),
    "STRESS": ("state", ("stress", "strain", "tension", "pressure", "force", "overexertion", "exertion",
                         "overwork", "overuse", "wear and tear", "duress", "pressurize")),
    "HEAT": ("state", ("heat", "heating", "hot", "thermal", "temperature", "overheat", "overheating",
                       "warm", "warming", "fever", "burn", "burning", "thermal runaway", "hotspot",
                       "hot spot")),
    "COOLING": ("method", ("cool", "cooling", "cold", "chill", "refrigerate", "refrigeration", "ventilate",
                           "ventilation", "heat sink", "heatsink", "radiator", "dissipate heat",
                           "thermal management", "thermal control", "cool down", "airflow")),
    "FRICTION": ("mechanism", ("friction", "drag", "resistance", "resistive", "impedance", "viscosity",
                               "inertia", "sticking", "hysteresis", "overhead", "red tape", "bureaucracy", "drag on", "interest drag")),
    # ---- capacity / limits / constraints ---------------------------------
    "CAPACITY": ("resource", ("capacity", "bandwidth", "headroom", "slack", "throughput limit",
                              "quota", "allowance", "carrying capacity", "seat", "seats",
                              "slots", "supply of", "availability")),
    "LIMIT": ("constraint", ("limit", "limitation", "cap", "bound", "boundary", "threshold", "maximum",
                             "minimum", "constraint", "restriction", "restrict",
                             "hard limit", "rate limit", "budget cap", "cutoff", "cut-off", "tolerance",
                             "envelope", "upper bound", "lower bound", "capacity limit", "spillway")),
    "BUDGET": ("constraint", ("budget", "allocation", "allowance", "funding", "funds", "money", "cost",
                              "expense", "spending", "price", "pricing", "fee", "cash", "capital",
                              "financial", "afford", "affordability", "runway")),
    "DEADLINE": ("constraint", ("deadline", "time limit", "timeline", "schedule", "due date", "cutoff date",
                                "time budget", "time window", "timebox", "sprint", "quarter end",
                                "expiry", "expiration", "expire", "end of quarter", "launch date", "ship date", "release date", "quarterly earnings", "exam week", "reporting date", "completion deadline", "shipping deadline", "release deadline", "cutoff")),
    "SCARCITY": ("constraint", ("scarce", "scarcity", "limited supply", "shortage", "rare", "rarity",
                                "insufficient", "lack", "lacking", "not enough", "too few", "understaffed",
                                "shorthanded", "short-handed", "constrained supply")),
    "REDUNDANCY": ("method", ("redundancy", "redundant", "backup", "spare", "failover", "fallback",
                              "replica", "replication", "duplicate", "mirror", "reserve", "reserves",
                              "safety margin", "margin of safety", "slack capacity", "buffer stock",
                              "buffer", "cushion", "contingency", "insurance")),
    # ---- coupling / structure --------------------------------------------
    "DEPENDENCY": ("constraint", ("depend", "dependency", "dependence", "dependent", "rely", "reliance",
                                  "prerequisite", "precondition", "requirement", "require", "need", "needs",
                                  "contingent on", "hinge on", "hinges on", "predicated on", "upstream",
                                  "downstream", "chain of")),
    "COUPLING": ("mechanism", ("couple", "coupling", "coupled", "tightly coupled", "interlock",
                               "interlocked", "entangle", "entanglement", "interdependent", "interdependence",
                               "linked", "link", "connection", "connected", "bind", "binding", "tie",
                               "tied", "wired together", "monolith", "monolithic", "integration", "interconnected", "interconnect", "interconnection", "shared", "sharing", "monoculture", "uniform", "homogeneous", "single shared", "entangled")),
    "ISOLATION": ("method", ("isolate", "isolation", "isolated", "decouple", "decoupling", "separate",
                             "separation", "partition", "quarantine", "compartment", "compartmentalize",
                             "bulkhead", "firewall", "silo", "sandbox", "containment", "contain", "modular",
                             "modularity", "loosely coupled", "ring fencing", "ring fence", "ring fenced", "islanding", "island", "diversification", "diversify", "diversified", "segregate", "segregation", "air gap", "airgap", "buffer zone", "buffer zones")),
    "FRAGMENTATION": ("state", ("fragment", "fragmentation", "fragmented", "scattered", "dispersed",
                                "dispersion", "splinter", "split", "divided", "division", "disjoint",
                                "siloed", "sprawl", "sprawling", "uncoordinated", "disorganized")),
    "COORDINATION": ("mechanism", ("coordinate", "coordination", "synchronize", "synchronization", "sync",
                                   "align", "alignment", "orchestrate", "orchestration", "cooperate",
                                   "cooperation", "collaborate", "collaboration", "consensus", "agreement",
                                   "handoff", "hand-off", "hand off", "scheduling", "arbitration",
                                   "consistency", "coherence", "coherent", "teamwork", "registry", "shared registry", "contract", "single source of truth", "handoff protocol", "sync meeting", "alignment sync", "alignment meeting")),
    "MISALIGNMENT": ("problem", ("misalign", "misalignment", "misaligned", "mismatch", "mismatched",
                                 "inconsistent", "inconsistency", "incoherent", "incoherence", "out of sync",
                                 "desync", "drift apart", "divergence", "diverge", "contradiction",
                                 "conflict", "conflicting", "clash", "disagreement", "disagree",
                                 "skew", "skewed", "discrepancy", "different directions", "pulling apart", "at odds", "cross purposes", "clashing", "clash")),
    "NOISE": ("problem", ("noise", "noisy", "interference", "distortion", "jitter", "static", "clutter",
                          "spurious", "false alarm", "false positive", "garbage", "junk", "irrelevant",
                          "distraction", "distract", "chatter")),
    "SIGNAL": ("evidence", ("signal", "indicator", "symptom", "marker", "cue", "sign", "warning",
                            "warning sign", "early warning", "alarm", "alert", "telemetry", "metric",
                            "reading", "measurement", "measure", "sensor", "gauge", "detect", "detection",
                            "observation", "observe", "monitor", "monitoring", "records", "statistics", "dashboard", "burn rate", "valuation", "mark to market", "appraisal", "readings", "report", "reports")),
    "UNCERTAINTY": ("state", ("uncertain", "uncertainty", "ambiguous", "ambiguity", "unknown", "unclear",
                              "vague", "fuzzy", "unpredictable", "unpredictability", "variance",
                              "randomness", "random", "stochastic", "guess", "guessing", "doubt")),
    "ERROR": ("problem", ("error", "mistake", "bug", "defect", "fault", "faulty", "flaw", "flawed",
                          "glitch", "malfunction", "incorrect", "wrong", "inaccurate", "inaccuracy",
                          "miscalculation", "misread", "typo", "corruption", "corrupt", "invalid", "bad loan", "bad debt", "nonperforming loan", "non performing loan")),
    "DRIFT": ("state", ("drift", "drifting", "creep", "gradual shift", "slippage", "slip", "deviation",
                        "deviate", "wander", "scope creep", "shift over time", "bias", "biased")),
    "VARIATION": ("state", ("variation", "vary", "variability", "variant", "diversity", "diverse",
                            "heterogeneity", "heterogeneous", "mutation", "mutate", "distribution", "dispersion", "different", "difference", "deviation")),
    "SELECTION": ("mechanism", ("select", "selection", "filter", "filtering", "screen", "screening",
                                "prune", "pruning", "cull", "weed out", "triage", "prioritize",
                                "prioritization", "rank", "ranking", "choose", "choice", "pick",
                                "survival", "survive", "winnow", "gating", "triage routine")),
    "ADAPTATION": ("mechanism", ("adapt", "adaptation", "adjust", "adjustment", "tune", "tuning",
                                 "calibrate", "calibration", "learn", "learning", "evolve", "evolution",
                                 "iterate", "iteration", "improve", "improvement", "optimize",
                                 "optimization", "refine", "refinement", "retrain", "fine-tune",
                                 "fine tune", "correction", "correct", "compensate", "compensation")),
    "MEMORY": ("resource", ("memory", "remember", "recall", "retention", "retain", "record", "history",
                            "log", "archive", "cache", "store", "storage", "persist", "persistence",
                            "state", "snapshot", "checkpoint", "journal", "ledger")),
    "FORGETTING": ("state", ("forget", "forgetting", "amnesia", "lose track", "lost", "loss of context",
                             "context loss", "evict", "eviction", "expire", "stale", "staleness",
                             "outdated", "obsolete", "decay of memory", "fade", "fading")),
    "ATTENTION": ("resource", ("attention", "focus", "concentration", "concentrate", "awareness",
                               "vigilance", "alertness", "mindshare", "bandwidth of", "cognitive load",
                               "notice", "noticing", "salience", "salient", "priority")),
    "FATIGUE": ("state", ("fatigue", "tired", "tiredness", "exhausted", "burnout", "burn out", "burned out",
                          "weary", "weariness", "overworked", "drained", "depleted energy", "alert fatigue",
                          "decision fatigue", "worn down")),
    "MOTIVATION": ("state", ("motivation", "motivate", "incentive", "incentivize", "reward", "drive",
                             "morale", "engagement", "engaged", "enthusiasm", "commitment", "willingness",
                             "desire", "goal", "ambition", "encourage", "encouragement", "discourage")),
    "TRUST": ("state", ("trust", "trusted", "confidence", "credibility", "credible", "reputation",
                        "reliability", "reliable", "faith", "legitimacy", "assurance", "distrust",
                        "mistrust", "suspicion", "suspicious", "skepticism", "sceptic")),
    "RISK": ("state", ("risk", "risky", "hazard", "hazardous", "danger", "dangerous", "threat", "exposure",
                       "vulnerable", "vulnerability", "fragile", "fragility", "liability", "peril",
                       "jeopardy", "susceptible", "susceptibility", "attack surface", "weakness")),
    "DEBT": ("state", ("debt", "technical debt", "tech debt", "liability", "owe", "arrears", "borrow",
                       "borrowing", "leverage", "leveraged", "margin", "margin call", "loan", "credit",
                       "deferred cost", "shortcut", "shortcuts", "kludge", "hack", "skipping", "skip", "skipped", "deferred", "defer", "deferral", "sleep debt", "cut corners", "corner cutting", "quick fix", "quick fixes", "quick hack", "quick hacks", "hacks", "workaround", "workarounds", "skipping maintenance", "postponed maintenance")),
    "INVESTMENT": ("method", ("invest", "investment", "fund", "funding", "spend", "spending", "allocate",
                              "allocation", "commit resources", "capital", "effort", "put in", "input",
                              "upfront cost", "sunk cost", "pay down", "paying down", "repay", "repayment", "rest days", "catch up rest", "catch-up", "catch up", "planned maintenance", "maintenance investment")),
    "SURGE_EVENT": ("state", ("burst", "surge", "spike", "rush", "stampede", "run on", "wave", "flood",
                              "influx", "flurry", "selloff", "sell-off", "sell off", "fire sale",
                              "panic selling", "panic buying", "frenzy", "swarm", "onslaught", "deluge",
                              "sudden demand", "thundering herd", "storm", "retry storm")),
    # ---- outcomes ---------------------------------------------------------
    "FAILURE": ("outcome", ("fail", "failure", "failing", "collapse", "collapsed", "crash", "crashed",
                            "outage", "breakdown", "break", "broken", "death", "die", "dying", "loss",
                            "lose", "ruin", "wreck", "meltdown", "blackout", "downtime", "shutdown",
                            "shut down", "bankrupt", "bankruptcy", "insolvency", "insolvent", "default",
                            "catastrophe", "catastrophic", "disaster", "abort", "aborted", "dropout",
                            "drop out", "give up", "quit", "extinction", "demise", "unavailable", "closure", "wipeout", "wipe out", "crisis", "damage", "damaged", "harm", "injury", "fall behind", "falling behind", "lose ground", "losing ground")),
    "SUCCESS": ("outcome", ("succeed", "success", "successful", "win", "winning", "achieve", "achievement",
                            "accomplish", "goal met", "complete",
                            "completion", "finish", "thrive", "thriving", "flourish", "prosper",
                            "prosperity", "victory", "healthy", "health")),
    "RECOVERY": ("outcome", ("recover", "recovery", "restore", "restoration", "heal", "healing", "repair",
                             "rebuild", "rebound", "bounce back", "resume", "resumption", "revive",
                             "revival", "rehabilitate", "remediate", "remediation", "fix", "fixed",
                             "roll back", "rollback", "reset", "restart", "reboot")),
    "RESILIENCE": ("state", ("resilient", "resilience", "robust", "robustness", "durable", "durability",
                             "hardy", "tolerant", "tolerance", "fault tolerant", "fault-tolerant",
                             "graceful degradation", "withstand", "endure", "endurance", "survivable",
                             "antifragile", "sturdy")),
    "STABILITY": ("state", ("stable", "stability", "steady", "steady state", "equilibrium", "balance",
                            "balanced", "homeostasis", "settle", "settled", "converge", "convergence",
                            "consistent", "calm", "constant", "level")),
    "QUALITY": ("state", ("quality", "accuracy", "accurate", "precision", "precise", "fidelity",
                          "correctness", "integrity", "soundness", "reliability", "performance",
                          "effectiveness", "efficacy", "efficiency", "efficient")),
    "EFFICIENCY_LOSS": ("problem", ("waste", "wasted", "wasteful", "inefficient", "inefficiency",
                                    "overhead", "rework", "duplication", "duplicate effort", "churn",
                                    "thrash", "thrashing", "idle", "idling", "underutilized", "redundant tests", "redundant work", "double work", "duplicated effort", "duplicate work", "repeated work", "wasted rework", "wasted demolition")),
    # ---- epistemic / methods ---------------------------------------------
    "EVIDENCE": ("evidence", ("evidence", "data", "dataset", "proof", "prove", "finding", "findings",
                              "result", "results", "observation", "observed", "experiment", "experimental",
                              "measurement", "measured", "study", "survey", "sample", "statistic",
                              "statistics", "record", "log entry", "report", "trace", "audit trail",
                              "benchmark", "test result")),
    "HYPOTHESIS": ("problem", ("hypothesis", "hypothesize", "conjecture", "assumption", "assume",
                               "theory", "premise", "claim", "proposition", "guess", "expectation",
                               "expect", "prediction", "predict", "belief", "believe", "suspect")),
    "MODEL": ("method", ("model", "modeling", "modelling", "simulation", "simulate", "representation",
                         "abstraction", "schema", "framework", "mapping", "diagram", "formula",
                         "equation", "algorithm", "estimator", "estimate", "approximation")),
    "METHOD": ("method", ("method", "methodology", "technique", "approach", "strategy", "tactic",
                          "procedure", "protocol", "process", "practice", "routine", "recipe", "playbook",
                          "policy", "rule", "heuristic", "workflow", "pipeline", "mechanism", "scheme",
                          "plan", "planning", "design", "architecture", "solution", "intervention",
                          "treatment", "therapy", "regimen", "remedy", "countermeasure", "safeguard")),
    "TOOL": ("resource", ("tool", "tooling", "instrument", "device", "equipment", "machine", "machinery",
                          "apparatus", "software", "library", "platform", "infrastructure", "system",
                          "service", "utility", "facility", "hardware")),
    "RESOURCE": ("resource", ("resource", "resources", "supply", "supplies", "inventory", "stock",
                              "asset", "assets", "material", "materials", "input", "inputs", "raw material",
                              "fuel", "energy", "power", "water", "food", "staff", "personnel", "labor",
                              "labour", "manpower", "headcount", "compute", "storage space", "roster", "pool", "credit line", "line of credit", "credit facility", "vessel time", "ship time", "cluster time", "compute time", "lab time", "machine time", "beam time", "zone", "reserve zone", "protected area", "sanctuary", "set aside", "land set aside")),
    "INFORMATION": ("resource", ("information", "info", "knowledge", "insight", "context", "documentation",
                                 "document", "docs", "message", "messages", "communication", "communicate",
                                 "news", "update", "updates", "notification", "report", "reporting",
                                 "signal", "feed", "content", "email", "emails", "chat", "meeting",
                                 "meetings", "memo", "spec", "specification")),
    "REQUEST": ("state", ("request", "requests", "query", "queries", "call", "calls", "ask", "order",
                          "orders", "demand", "ticket", "tickets", "job", "jobs", "task", "tasks",
                          "transaction", "transactions", "submission", "application", "claim", "claims",
                          "inquiry", "inquiries", "customer", "customers", "user", "users", "patient",
                          "patients", "client", "clients", "visitor", "visitors")),
    "RETRY": ("mechanism", ("retry", "retries", "retrying", "re-try", "resend", "repeat", "repeated",
                            "repetition", "reattempt", "again", "redo", "resubmit", "reissue",
                            "loop back", "keep trying", "try again", "polling", "poll", "repeatedly", "again and again", "re present", "re send", "re try", "re submit", "come back", "coming back", "return visit", "return visits")),
    "TIMEOUT": ("state", ("timeout", "time out", "timed out", "expire", "expired", "expiry", "deadline miss",
                          "missed deadline", "give up waiting", "abandon", "abandonment", "drop",
                          "dropped", "cancel", "cancellation", "walk away", "churn")),
    "THRESHOLD_EVENT": ("state", ("trigger", "triggered", "trip", "tripped", "breach", "breached", "cross",
                                  "crossing", "exceed", "exceeded", "violate", "violation", "overrun",
                                  "overstep", "hit the limit", "reach the limit", "critical", "spill point", "passing the", "past the", "beyond the", "over the line", "breaching")),
    "CONTROL": ("method", ("control", "controller", "regulate", "regulation", "regulator", "govern",
                           "governance", "throttle", "throttling", "rate limiting", "limiter", "valve",
                           "brake", "braking", "moderate", "moderation", "manage", "management",
                           "supervise", "supervision", "oversight", "steer", "steering", "thermostat",
                           "circuit breaker", "breaker", "backoff", "back off", "back-off", "shed load",
                           "load shedding", "admission control", "quota enforcement", "cap enforcement", "liquidation", "liquidate", "stop loss", "stop-loss", "kill switch", "shutoff", "shut off", "automatic shutdown", "pump", "dosing", "release valve", "controlled release", "halt rule", "trading halt")),
    "BLOCKING_ACTION": ("method", ("prevent", "prevention", "block", "stop", "halt", "avoid", "avoidance",
                                   "forbid", "prohibit", "prohibition", "ban", "veto", "reject", "rejection",
                                   "deny", "denial", "refuse", "refusal", "inhibit", "inhibition",
                                   "deter", "deterrent", "guard", "shield", "protect", "protection",
                                   "defend", "defense", "defence", "immunize", "immunity", "vaccinate")),
    "ENABLING_ACTION": ("method", ("enable", "enabling", "allow", "permit", "unlock", "facilitate",
                                   "facilitation", "support", "supporting", "empower", "grant", "authorize",
                                   "authorization", "license", "open up", "make possible", "afford")),
    "TESTING": ("method", ("test", "testing", "verify", "verification", "validate", "validation", "check",
                           "checking", "inspect", "inspection", "review", "audit", "assess", "assessment",
                           "evaluate", "evaluation", "diagnose", "diagnosis", "diagnostic", "probe",
                           "screen", "examine", "examination", "trial", "pilot", "canary", "rehearsal",
                           "dry run", "drill", "experiment", "experimental", "benchmark", "benchmark run", "a b", "a/b", "culture test", "blood test", "lab test", "field trial", "survey pilot", "survey")),
    # ---- agents / social ----------------------------------------------------
    "AGENT": ("agent", ("person", "people", "team", "teams", "individual", "employee", "employees",
                        "worker", "workers", "manager", "managers", "leader", "leadership", "engineer",
                        "engineers", "developer", "developers", "operator", "operators", "doctor",
                        "nurse", "clinician", "staff", "crew", "organization", "organisation", "company",
                        "firm", "department", "group", "community", "population", "society", "government",
                        "agency", "committee", "board", "founder", "founders", "student", "students",
                        "teacher", "family", "household", "actor", "actors", "participant", "participants",
                        "stakeholder", "stakeholders", "member", "members", "agent", "agents", "bank",
                        "banks", "investor", "investors", "trader", "traders", "market participant", "fleet", "clinic", "clinics", "desk", "application", "applications", "vendor", "vendors", "supplier", "suppliers", "trawler", "subcontractor", "subcontractors")),
    "INCENTIVE_MISMATCH": ("problem", ("moral hazard", "perverse incentive", "misaligned incentive",
                                       "free rider", "free-rider", "tragedy of the commons", "gaming",
                                       "game the", "goodhart", "principal agent", "principal-agent",
                                       "conflict of interest", "rent seeking", "rent-seeking")),
    "COMMUNICATION_GAP": ("problem", ("miscommunication", "misunderstanding", "misunderstand", "unclear",
                                      "ambiguous instruction", "lost in translation", "silence",
                                      "no visibility", "opaque", "opacity", "hidden", "invisible",
                                      "blind spot", "unaware", "ignorance", "ignorant", "out of the loop",
                                      "information asymmetry", "asymmetry", "notes missing", "information lost", "missing handoff", "not passed along", "not passed on", "not communicated", "never told", "no one told", "unshared", "not shared", "uninformed", "hidden changes", "hidden change", "nothing passed on")),
    # ---- generic problem / goal words (weak, role-carrying) ----------------
    "PROBLEM": ("problem", ("problem", "issue", "trouble", "difficulty", "difficult", "challenge",
                            "obstacle", "pain", "pain point", "friction point", "concern", "worry",
                            "complaint", "symptom", "incident", "crisis", "emergency", "bottleneck", "disease", "blight", "infection", "outbreak", "bad loan", "bad debt", "nonperforming", "non performing")),
    "GOAL": ("outcome", ("goal", "objective", "target", "aim", "purpose", "intent", "intention", "mission",
                         "outcome", "result", "desired", "want", "wanted", "need to", "should", "must",
                         "milestone", "deliverable", "kpi", "okr", "metric of success")),
    # ---- domain anchors: same-domain support only, no analogical weight ----
    "DOMAIN_ELECTROCHEMISTRY": (None, ("battery", "batteries", "cell", "cells", "electrolyte", "anode",
                                       "cathode", "lithium", "li-ion", "charge", "charging", "discharge",
                                       "voltage", "current", "resistance", "ohm", "capacity fade",
                                       "dendrite", "dendrites", "electrode", "separator", "pack")),
    "DOMAIN_SOFTWARE": (None, ("server", "servers", "service", "microservice", "api", "database", "db",
                               "cache", "queue", "cluster", "node", "pod", "container", "deploy",
                               "deployment", "release", "commit", "merge", "pull request", "code",
                               "codebase", "bug", "latency", "cpu", "memory", "disk", "network", "packet",
                               "thread", "process", "lock", "mutex", "garbage collection", "gc",
                               "connection pool", "retry storm", "thundering herd")),
    "DOMAIN_FINANCE": (None, ("market", "markets", "stock", "stocks", "asset", "price", "prices", "trader",
                              "traders", "bank", "banks", "loan", "loans", "credit", "liquidity", "margin",
                              "margin call", "collateral", "selloff", "sell-off", "sell off", "deposit",
                              "deposits", "withdrawal", "withdrawals", "portfolio", "investor", "investors",
                              "bond", "bonds", "interest rate", "inflation", "currency", "leverage")),
    "DOMAIN_ORGANIZATION": (None, ("team", "teams", "organization", "organisation", "company", "manager",
                                   "management", "meeting", "meetings", "hiring", "onboarding", "process",
                                   "department", "headcount", "roadmap", "priority", "priorities",
                                   "stakeholder", "decision", "decisions", "reorg", "reorganization")),
    "DOMAIN_MEDICINE": (None, ("patient", "patients", "hospital", "clinic", "doctor", "nurse", "clinician",
                               "diagnosis", "treatment", "therapy", "dose", "dosage", "drug", "medication",
                               "symptom", "symptoms", "infection", "immune", "immune system", "inflammation",
                               "tumor", "tumour", "blood", "heart", "cardiac", "kidney", "liver", "cell",
                               "cells", "virus", "bacteria", "antibiotic", "resistance to antibiotics")),
    "DOMAIN_ECOLOGY": (None, ("ecosystem", "species", "population", "predator", "prey", "habitat",
                              "biodiversity", "forest", "fishery", "fish", "overfishing", "soil",
                              "nutrient", "nutrients", "algae", "bloom", "river", "lake", "ocean", "climate",
                              "drought", "rainfall", "crop", "crops", "harvest", "farm", "farming",
                              "livestock", "grazing", "pasture")),
    "DOMAIN_INFRASTRUCTURE": (None, ("bridge", "road", "roads", "highway", "traffic", "grid", "power grid",
                                     "transformer", "substation", "pipe", "pipes", "pipeline", "water supply",
                                     "sewer", "reservoir", "dam", "levee", "rail", "railway", "train",
                                     "airport", "runway", "port", "harbor", "harbour", "warehouse",
                                     "supply chain", "logistics", "shipping", "container ship", "truck")),
    "DOMAIN_EDUCATION": (None, ("student", "students", "homework", "assignment", "assignments", "exam",
                                "exams", "grade", "grades", "course", "courses", "lecture", "class",
                                "classroom", "teacher", "teachers", "school", "university", "study",
                                "studying", "procrastination", "procrastinate", "semester", "tuition")),
    "DOMAIN_MANUFACTURING": (None, ("factory", "plant", "assembly line", "assembly", "production line",
                                    "machine", "machines", "tooling", "defect rate", "scrap", "yield",
                                    "inventory", "supplier", "suppliers", "lead time", "batch", "batches",
                                    "shift", "shifts", "maintenance", "downtime", "conveyor", "robot",
                                    "welding", "casting", "quality control")),
    "DOMAIN_COOKING": (None, ("dough", "sourdough", "bread", "oven", "bake", "baking", "yeast", "starter",
                              "flour", "ferment", "fermentation", "proof", "proofing", "kitchen", "recipe",
                              "ingredient", "ingredients", "sauce", "boil", "simmer", "knead", "rise of dough")),
}

# Domain classes never carry analogical weight.
DOMAIN_PREFIX = "DOMAIN_"

# Soft neighbourhood between abstract classes: partial credit when two labels
# realise *related* relational notions (amplification ~ cascade). Symmetric.
RELATED: dict[frozenset[str], float] = {}


def _rel(a: str, b: str, w: float) -> None:
    RELATED[frozenset((a, b))] = w


for _a, _b, _w in (
    ("AMPLIFICATION", "CASCADE", 0.7), ("AMPLIFICATION", "FEEDBACK", 0.7), ("CASCADE", "FEEDBACK", 0.6),
    ("CASCADE", "SURGE_EVENT", 0.6), ("SURGE_EVENT", "LOAD", 0.6), ("SURGE_EVENT", "GROWTH", 0.4),
    ("ACCUMULATION", "SATURATION", 0.6), ("ACCUMULATION", "LOAD", 0.5), ("ACCUMULATION", "GROWTH", 0.5),
    ("ACCUMULATION", "DEBT", 0.4), ("SATURATION", "LOAD", 0.6), ("SATURATION", "BOTTLENECK", 0.4),
    ("DEGRADATION", "DECLINE", 0.6), ("DEGRADATION", "FAILURE", 0.5), ("DECLINE", "DEPLETION", 0.5),
    ("DEGRADATION", "FATIGUE", 0.5), ("DEGRADATION", "ERROR", 0.3), ("DEGRADATION", "QUALITY", 0.3),
    ("DEPLETION", "SCARCITY", 0.8), ("DEPLETION", "FATIGUE", 0.5), ("DEPLETION", "LEAK", 0.4),
    ("DELAY", "BLOCKAGE", 0.5), ("DELAY", "BOTTLENECK", 0.6), ("BLOCKAGE", "BOTTLENECK", 0.6),
    ("DELAY", "TIMEOUT", 0.5), ("BLOCKAGE", "FRICTION", 0.4), ("DELAY", "FRICTION", 0.4),
    ("CONTROL", "DAMPING", 0.6), ("CONTROL", "BLOCKING_ACTION", 0.5), ("DAMPING", "COOLING", 0.6),
    ("DAMPING", "REDUNDANCY", 0.4), ("DAMPING", "ISOLATION", 0.4), ("CONTROL", "LIMIT", 0.4),
    ("LIMIT", "CAPACITY", 0.6), ("LIMIT", "BUDGET", 0.5), ("LIMIT", "DEADLINE", 0.5), ("LIMIT", "SCARCITY", 0.4),
    ("CAPACITY", "RESOURCE", 0.5), ("BUDGET", "RESOURCE", 0.4), ("BUDGET", "INVESTMENT", 0.5),
    ("THRESHOLD_EVENT", "LIMIT", 0.5), ("THRESHOLD_EVENT", "SATURATION", 0.5),
    ("STRESS", "LOAD", 0.7), ("STRESS", "HEAT", 0.4), ("STRESS", "FATIGUE", 0.5), ("HEAT", "LOAD", 0.3),
    ("COUPLING", "DEPENDENCY", 0.6), ("ISOLATION", "FRAGMENTATION", 0.3), ("COUPLING", "CASCADE", 0.4),
    ("COORDINATION", "MISALIGNMENT", 0.3), ("MISALIGNMENT", "COMMUNICATION_GAP", 0.6),
    ("MISALIGNMENT", "INCENTIVE_MISMATCH", 0.5), ("FRAGMENTATION", "COMMUNICATION_GAP", 0.5),
    ("NOISE", "SIGNAL", 0.3), ("NOISE", "UNCERTAINTY", 0.5), ("ERROR", "NOISE", 0.4),
    ("SIGNAL", "EVIDENCE", 0.6), ("SIGNAL", "TESTING", 0.4), ("EVIDENCE", "TESTING", 0.5),
    ("HYPOTHESIS", "MODEL", 0.5), ("MODEL", "METHOD", 0.5), ("METHOD", "TOOL", 0.4),
    ("METHOD", "CONTROL", 0.4), ("METHOD", "ADAPTATION", 0.4), ("ADAPTATION", "SELECTION", 0.5),
    ("ADAPTATION", "RECOVERY", 0.4), ("RECOVERY", "RESILIENCE", 0.6), ("RESILIENCE", "STABILITY", 0.6),
    ("RESILIENCE", "REDUNDANCY", 0.5), ("STABILITY", "OSCILLATION", 0.3), ("OSCILLATION", "FEEDBACK", 0.4),
    ("FAILURE", "TIMEOUT", 0.4), ("FAILURE", "RISK", 0.4), ("RISK", "UNCERTAINTY", 0.4),
    ("RISK", "DEBT", 0.4), ("DEBT", "INVESTMENT", 0.3), ("SUCCESS", "GOAL", 0.5), ("SUCCESS", "QUALITY", 0.4),
    ("PROBLEM", "ERROR", 0.4), ("PROBLEM", "RISK", 0.3), ("FLOW", "REQUEST", 0.4), ("FLOW", "INFORMATION", 0.3),
    ("REQUEST", "LOAD", 0.5), ("RETRY", "FEEDBACK", 0.4), ("RETRY", "AMPLIFICATION", 0.4),
    ("RETRY", "LOAD", 0.4), ("MEMORY", "FORGETTING", 0.3), ("ATTENTION", "FATIGUE", 0.3),
    ("ATTENTION", "MOTIVATION", 0.3), ("MOTIVATION", "TRUST", 0.3), ("TRUST", "RISK", 0.3),
    ("ENABLING_ACTION", "BLOCKING_ACTION", 0.2), ("EFFICIENCY_LOSS", "FRICTION", 0.5),
    ("EFFICIENCY_LOSS", "DEPLETION", 0.3), ("SELECTION", "TESTING", 0.4), ("GROWTH", "DECLINE", 0.2),
    ("LEAK", "FLOW", 0.4), ("FRICTION", "STRESS", 0.3), ("VARIATION", "DRIFT", 0.5),
    ("VARIATION", "NOISE", 0.4), ("DRIFT", "MISALIGNMENT", 0.4), ("AGENT", "COORDINATION", 0.2),
):
    _rel(_a, _b, _w)


def relatedness(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return RELATED.get(frozenset((a, b)), 0.0)


def _phrase_key(phrase: str) -> tuple[str, ...]:
    return tuple(stem(tok) for tok in _split(phrase))


def _split(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out


def _build() -> tuple[dict[tuple[str, ...], set[str]], int, dict[str, str | None]]:
    index: dict[tuple[str, ...], set[str]] = {}
    longest = 1
    hints: dict[str, str | None] = {}
    for concept, (role_hint, terms) in CONCEPTS.items():
        hints[concept] = role_hint
        for term in terms:
            key = _phrase_key(term)
            if not key:
                continue
            index.setdefault(key, set()).add(concept)
            longest = max(longest, len(key))
    return index, longest, hints


PHRASE_INDEX, LONGEST_PHRASE, ROLE_HINTS = _build()


def is_domain_concept(concept: str) -> bool:
    return concept.startswith(DOMAIN_PREFIX)

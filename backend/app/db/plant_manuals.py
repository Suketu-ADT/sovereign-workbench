"""
Standard Operating Procedures (SOPs) and technical manuals for plant units.
Each document chunk is tagged with min_clearance and equipment unit for
zero-leakage RBAC pre-filtering at the vector database index layer.
"""

PLANT_MANUAL_CHUNKS = [
    # ── Level 1: boiler-102 (Clearance Level 1 - Operator) ────────────────
    {
        "id": "boiler-102-sop-1",
        "unit": "boiler-102",
        "sop_id": "SOP-102-1",
        "title": "Boiler Feedwater Regulation & Operating Pressure Envelope",
        "min_clearance": 1,
        "content": (
            "Boiler 102 Operating Standard: Normal steam drum operating pressure is 18.5 bar "
            "(nominal operating range 16.0 to 21.0 bar). Normal steam outlet temperature is 350°C. "
            "Feedwater inlet pressure must maintain a minimum 2.5 bar differential above drum pressure. "
            "Deaerator storage tank pressure is maintained at 1.5 bar. If steam pressure exceeds 22.0 bar, "
            "the high-pressure alarm triggers and operator must verify modulating blowdown valve position."
        ),
    },
    {
        "id": "boiler-102-sop-2",
        "unit": "boiler-102",
        "sop_id": "SOP-102-2",
        "title": "Dual-Fuel Burner Safety Interlocks & Purge Checklist",
        "min_clearance": 1,
        "content": (
            "Boiler 102 Burner Management System (BMS): Prior to burner ignition, the combustion "
            "chamber must complete an automated 5-minute pre-ignition air purge at 70% airflow damper opening. "
            "Flame scanner ultraviolet sensors FS-101 and FS-102 must indicate dark status during purge. "
            "Emergency fuel shutoff double block and bleed valves must close within 1.0 second upon loss of "
            "flame signal or forced draft fan trip."
        ),
    },
    {
        "id": "boiler-102-sop-3",
        "unit": "boiler-102",
        "sop_id": "SOP-102-3",
        "title": "Low Water Cut-Off (LWCO) & Auxiliary Pump Protocol",
        "min_clearance": 1,
        "content": (
            "Boiler 102 Emergency Water Levels: Normal drum water level setpoint is 0 mm (centerline). "
            "At -30 mm, low water alarm activates. At -50 mm, primary Low Water Cut-Off (LWCO) trips burner "
            "firing circuits and auto-starts standby auxiliary electric feedwater pump P-102B. "
            "If level drops below -75 mm, immediate emergency manual trip of boiler is required."
        ),
    },

    # ── Level 2: turbine-gen-4 (Clearance Level 2 - Senior Tech) ─────────
    {
        "id": "turbine-gen-4-sop-1",
        "unit": "turbine-gen-4",
        "sop_id": "SOP-204-1",
        "title": "Turbine-Gen-4 Rotor Dynamics & Vibration Velocity Boundaries",
        "min_clearance": 2,
        "content": (
            "Turbine Generator 4 Dynamic Tolerances: Synchronous operating speed is 3000 RPM (50 Hz grid). "
            "Continuous vibration velocity across bearings B1 through B4: Normal is < 2.8 mm/s RMS (Zone A). "
            "Advisory alert threshold is 4.5 mm/s RMS (Zone B/C boundary). Immediate turbine trip threshold "
            "is 7.1 mm/s RMS (ISO 10816-3 Zone D limit). When alert threshold is breached, inspect shaft balance "
            "and record proximity probe phase angles."
        ),
    },
    {
        "id": "turbine-gen-4-sop-2",
        "unit": "turbine-gen-4",
        "sop_id": "SOP-204-2",
        "title": "Hydrodynamic Bearing Lubrication Conditioning & Temperature Limits",
        "min_clearance": 2,
        "content": (
            "Turbine Generator 4 Lube Oil System: Oil supply pressure at bearing manifold must remain between "
            "2.2 bar and 2.8 bar. Oil cooler outlet temperature setpoint is 42°C to 45°C. Bearing babbitt metal "
            "temperature alarm activates at 95°C. Emergency turbine trip interlock activates if any bearing metal "
            "temperature reaches 105°C or lube oil supply pressure drops below 1.2 bar."
        ),
    },
    {
        "id": "turbine-gen-4-sop-3",
        "unit": "turbine-gen-4",
        "sop_id": "SOP-204-3",
        "title": "Electro-Hydraulic Governor (EHC) & Overspeed Protection",
        "min_clearance": 2,
        "content": (
            "Turbine Generator 4 Governor System: High-pressure electro-hydraulic control (EHC) fluid operating "
            "pressure is 110 bar. Overspeed protection incorporates dual triple-redundant magnetic pickups. "
            "Primary electronic overspeed trip occurs at 110% of rated speed (3300 RPM). Backup mechanical "
            "emergency trip bolt engages at 112% (3360 RPM). Governor throttle valves must fully stroke from "
            "100% open to tight shutoff in < 150 milliseconds during trip actuation."
        ),
    },

    # ── Level 3: reactor-core-aux (Clearance Level 3 - Control Engineer / Chief)
    {
        "id": "reactor-core-aux-sop-1",
        "unit": "reactor-core-aux",
        "sop_id": "SOP-301-1",
        "title": "Control Rod Drive Mechanism (CRDM) Stepping & SCRAM Timing",
        "min_clearance": 3,
        "content": (
            "Reactor Core Auxiliary Systems: Control rod cluster assembly stepping speed is 72 steps/minute "
            "during regulated power changes. Emergency SCRAM actuation de-energizes CRDM gripper coils allowing "
            "gravity insertion. Total rod insertion time to 90% core depth must not exceed 1.80 seconds. "
            "Sub-criticality shutdown margin must maintain at least 1.6% delta k/k across all operational "
            "temperature envelopes."
        ),
    },
    {
        "id": "reactor-core-aux-sop-2",
        "unit": "reactor-core-aux",
        "sop_id": "SOP-301-2",
        "title": "Chemical and Volume Control System (CVCS) Boron Titration",
        "min_clearance": 3,
        "content": (
            "Reactor Core Chemical Shim: Primary coolant boron concentration is titrated via CVCS demineralizers "
            "and boric acid storage tanks. Minimum emergency boration delivery rate is 300 gpm at 7000 ppm boron. "
            "Differential boron worth curves must be recalibrated following every 100 EFPD (Effective Full Power Days) "
            "fuel burnup interval."
        ),
    },
    {
        "id": "reactor-core-aux-sop-3",
        "unit": "reactor-core-aux",
        "sop_id": "SOP-301-3",
        "title": "Emergency Core Cooling System (ECCS) Passive Accumulator Sequencing",
        "min_clearance": 3,
        "content": (
            "Reactor Core Auxiliary Safety Injection: Four passive ECCS cold-leg accumulators are pressurized "
            "with nitrogen blanket gas at 45.0 bar. If reactor primary loop pressure drops below 42.0 bar due to a "
            "loss-of-coolant incident, dual swing check valves open passively to inject borated water. Containment "
            "isolation Phase A valves must achieve complete seal within 3.0 seconds."
        ),
    },
]

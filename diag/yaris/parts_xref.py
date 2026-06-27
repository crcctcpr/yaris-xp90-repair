"""Comprehensive parts cross-reference catalog.

Every wear / service part for the 2011 Yaris 1NR-FE, cross-referenced between
major manufacturers. Searchable by ANY part number — enter a Wix number and
find the Toyota OEM, or vice versa.

Sources:
  - Toyota parts catalog / TIS
  - Manufacturer cross-reference sites (Fram, Wix, Mann, K&N, Denso, Aisin, etc)
  - RockAuto application lookup
"""
from dataclasses import dataclass


@dataclass
class CrossRef:
    category: str
    description: str
    toyota_oem: str
    price_oem: tuple[int, int]  # USD range
    # manufacturer → [part numbers]
    equivalents: dict[str, list[str]]
    notes: str = ""


CATALOG: list[CrossRef] = [
    # ── Engine oil filters ──────────────────────────────────────────
    CrossRef(
        category="Oil filter",
        description="Engine oil filter — cartridge style, 1NR-FE",
        toyota_oem="04152-YZZA1",
        price_oem=(10, 18),
        equivalents={
            "Denso": ["150-3011"],
            "Fram": ["CH9911"],
            "Wix": ["57212"],
            "K&N": ["HP-7016"],
            "Bosch": ["3330"],
            "Mann": ["HU712/7x"],
            "Mahle": ["OX 339D"],
        },
        notes="Cartridge style with paper element. Includes new O-rings. Torque 10 Nm.",
    ),

    # ── Engine air filters ──────────────────────────────────────────
    CrossRef(
        category="Air filter",
        description="Engine air filter — panel style, 1NR-FE airbox",
        toyota_oem="17801-40020",
        price_oem=(18, 28),
        equivalents={
            "Denso": ["143-3008"],
            "Fram": ["CA10159"],
            "Wix": ["49159"],
            "K&N": ["33-2417"],
            "AEM": ["28-20425"],
            "Purolator": ["A36087"],
            "Mann": ["C 2774/3"],
        },
        notes="AVOID oiled filters (K&N style) — oil migrates onto MAF element.",
    ),

    # ── Cabin air filter ─────────────────────────────────────────────
    CrossRef(
        category="Cabin air filter",
        description="Cabin / pollen filter",
        toyota_oem="87139-0F010",
        price_oem=(15, 25),
        equivalents={
            "Fram": ["CF11173"],
            "Wix": ["24861"],
            "K&N": ["VF2000"],
            "Denso": ["453-6022"],
            "Mann": ["CUK 2440"],
            "Bosch": ["M2046"],
        },
        notes="Located behind glove box. Change every 30,000 km.",
    ),

    # ── Spark plugs ──────────────────────────────────────────────────
    CrossRef(
        category="Spark plug",
        description="Iridium, pre-gapped 1.0-1.1mm — 1NR-FE uses 3",
        toyota_oem="90919-01235 (reseller ID)",
        price_oem=(30, 45),
        equivalents={
            "NGK": ["ILKAR7L11", "DF7H-11B (JDM)"],
            "Denso": ["VCH16", "SC16HR11"],
            "Bosch": ["YR8NII332W"],
            "Champion": ["RER8MCX4"],
        },
        notes="Torque 18 Nm. Do NOT adjust iridium electrode.",
    ),

    # ── Ignition coil ────────────────────────────────────────────────
    CrossRef(
        category="Ignition coil",
        description="Coil-on-plug, 1 per cylinder (3 total)",
        toyota_oem="90919-02240",
        price_oem=(50, 90),
        equivalents={
            "Denso": ["673-1303"],
            "Standard Motor Products": ["UF-596"],
            "NGK": ["U5166"],
            "Delphi": ["GN10328"],
        },
    ),

    # ── Water pump ───────────────────────────────────────────────────
    CrossRef(
        category="Water pump",
        description="Engine water pump with gasket",
        toyota_oem="16100-80004",
        price_oem=(60, 110),
        equivalents={
            "Aisin": ["WPT-181", "WPT-181A"],
            "Gates": ["41190P"],
            "Airtex": ["AW6297"],
            "GMB": ["170-2100"],
        },
        notes="Belt-driven on 1NR-FE (despite chain timing). Check weep hole for seep.",
    ),

    # ── Thermostat ───────────────────────────────────────────────────
    CrossRef(
        category="Thermostat",
        description="Engine thermostat w/ gasket",
        toyota_oem="90916-03084",
        price_oem=(20, 40),
        equivalents={
            "Aisin": ["THT-019"],
            "Gates": ["33956"],
            "Motorad": ["464-170"],
            "Stant": ["14558"],
        },
        notes="Opens ~82°C. Install with spring facing engine.",
    ),

    # ── Brake pads front ─────────────────────────────────────────────
    CrossRef(
        category="Brake pads (front)",
        description="Front disc pads, ceramic or semi-metallic",
        toyota_oem="04465-52260",
        price_oem=(40, 80),
        equivalents={
            "Akebono": ["ACT908", "ACT885"],
            "Brembo": ["P 83 140N"],
            "Wagner": ["ZD908"],
            "Raybestos": ["EHT885H"],
            "Bosch QuietCast": ["BC908"],
            "StopTech": ["309.09080"],
        },
        notes="Min rotor thickness 17.0 mm. Replace pads below 2.0 mm.",
    ),

    # ── Brake rotor front ────────────────────────────────────────────
    CrossRef(
        category="Brake rotor (front)",
        description="Front disc rotor, OD 255 mm",
        toyota_oem="43512-52180",
        price_oem=(50, 100),
        equivalents={
            "Brembo": ["09.9766.10"],
            "Centric": ["120.44195"],
            "Raybestos": ["780700"],
            "Wagner": ["BD180180E"],
        },
        notes="Min thickness 17.0 mm. Resurface only if within spec.",
    ),

    # ── Brake shoes rear ─────────────────────────────────────────────
    CrossRef(
        category="Brake shoes (rear)",
        description="Rear drum brake shoes, ID 200 mm",
        toyota_oem="04495-52030",
        price_oem=(30, 60),
        equivalents={
            "Akebono": ["AN-785BR"],
            "Wagner": ["Z785"],
            "Raybestos": ["785SGR"],
        },
    ),

    # ── MAF sensor ───────────────────────────────────────────────────
    CrossRef(
        category="MAF sensor",
        description="Mass airflow sensor, hot-wire",
        toyota_oem="22204-21010",
        price_oem=(90, 150),
        equivalents={
            "Denso": ["197-6020"],
            "Hitachi": ["MAF0054"],
            "Delphi": ["AF10125"],
            "Bosch": ["0 280 218 196"],
        },
        notes="Clean with CRC 05110 first before replacing. Aftermarket $40-80 works but OEM is safest.",
    ),

    # ── O2 sensors ───────────────────────────────────────────────────
    CrossRef(
        category="O2 sensor upstream (A/F ratio)",
        description="Wideband air/fuel ratio sensor, bank 1 sensor 1",
        toyota_oem="89467-52040",
        price_oem=(130, 200),
        equivalents={
            "Denso": ["234-9040"],
            "NTK": ["24668"],
            "Bosch": ["17190"],
        },
        notes="Wideband — reads lambda, not mV.",
    ),
    CrossRef(
        category="O2 sensor downstream",
        description="Narrowband post-cat O2, bank 1 sensor 2",
        toyota_oem="89465-52380",
        price_oem=(50, 90),
        equivalents={
            "Denso": ["234-4209"],
            "NTK": ["24330"],
            "Bosch": ["15716"],
        },
        notes="Always cheaper than replacing the cat for P0420. Try this first.",
    ),

    # ── Battery ──────────────────────────────────────────────────────
    CrossRef(
        category="Battery",
        description="12V lead-acid, group 35 (US) / 55B24L (JDM)",
        toyota_oem="(N/A — any replacement)",
        price_oem=(100, 180),
        equivalents={
            "Interstate": ["MT-35"],
            "Optima": ["REDTOP 35"],
            "ACDelco": ["35AGMF"],
            "Duralast Gold": ["35-DLG"],
            "AutoCraft": ["35-2"],
        },
        notes="Min 400 CCA; typical 500-600 CCA. 5-year warranty common.",
    ),

    # ── Alternator ───────────────────────────────────────────────────
    CrossRef(
        category="Alternator",
        description="~80A alternator",
        toyota_oem="27060-47140",
        price_oem=(200, 350),
        equivalents={
            "Denso": ["210-0656"],
            "Remy (reman)": ["22015"],
            "Bosch (reman)": ["AL0832X"],
            "Quality-Built": ["11259"],
        },
        notes="Remanufactured ~$80-150, new ~$200-300. Check charging V 13.4-14.5V.",
    ),

    # ── Starter ──────────────────────────────────────────────────────
    CrossRef(
        category="Starter motor",
        description="Planetary reduction starter",
        toyota_oem="28100-40051",
        price_oem=(150, 260),
        equivalents={
            "Denso": ["280-0389"],
            "Remy": ["16918"],
            "Bosch": ["SR7532X"],
        },
    ),

    # ── VVT-i OCV solenoid ──────────────────────────────────────────
    CrossRef(
        category="VVT-i OCV solenoid",
        description="Oil control valve for variable valve timing",
        toyota_oem="15330-40011",
        price_oem=(45, 90),
        equivalents={
            "Standard": ["VVT230"],
            "Delphi": ["CCS1012"],
            "Dorman": ["917-010"],
        },
        notes="Clean with brake cleaner first — screen clogs with sludge.",
    ),

    # ── Timing chain kit ─────────────────────────────────────────────
    CrossRef(
        category="Timing chain kit",
        description="Chain + tensioner + guides + damper",
        toyota_oem="1356X-40xxx family",
        price_oem=(180, 350),
        equivalents={
            "Aisin": ["TKT-019"],
            "Cloyes": ["9-4202S"],
            "Melling": ["3-SHM168"],
        },
        notes="Major procedure — 5+ hours. See walkthrough on timing chain rattle.",
    ),

    # ── PCV valve ───────────────────────────────────────────────────
    CrossRef(
        category="PCV valve",
        description="Positive crankcase ventilation",
        toyota_oem="12204-37010",
        price_oem=(15, 30),
        equivalents={
            "Motorad": ["MV9511"],
            "Standard": ["V488"],
            "Fram": ["FV333"],
        },
    ),

    # ── Engine mount (right side dogbone) ────────────────────────────
    CrossRef(
        category="Engine mount (upper right / dog-bone)",
        description='Upper "dog-bone" torque strut mount',
        toyota_oem="12363-40010",
        price_oem=(45, 85),
        equivalents={
            "Anchor": ["9864"],
            "DEA": ["A62029"],
            "MTC": ["12363-40010"],
        },
        notes="Common failure at 100k+ km → vibration at idle in D.",
    ),

    # ── Brake fluid ──────────────────────────────────────────────────
    CrossRef(
        category="Brake fluid",
        description="DOT 3 or DOT 4 hydraulic fluid",
        toyota_oem="08823-80014",
        price_oem=(8, 15),
        equivalents={
            "Valvoline": ["SynBrake DOT 3/4"],
            "Prestone": ["AS800"],
            "Castrol": ["DOT 4"],
            "ATE": ["TYP 200"],
            "Motul": ["DOT 5.1 (compatible)"],
        },
        notes="Never mix DOT 3 / 4 / 5.1 with DOT 5 (silicone).",
    ),

    # ── Coolant ─────────────────────────────────────────────────────
    CrossRef(
        category="Coolant",
        description="Super Long Life Coolant — Toyota SLLC",
        toyota_oem="00272-SLLC2",
        price_oem=(20, 35),
        equivalents={
            "Prestone": ["AF-6100 (Asian Vehicle Formula)"],
            "Zerex": ["Asian Vehicle Red"],
            "Peak": ["Long Life Asian Red"],
        },
        notes="Bright pink/red color. Never mix with green IAT coolant.",
    ),
]


def search(query: str) -> list[dict]:
    q = (query or "").lower().strip()
    if not q:
        return []
    results = []
    for c in CATALOG:
        hay = [c.category, c.description, c.toyota_oem, c.notes]
        for mfr, nums in c.equivalents.items():
            hay.append(mfr); hay.extend(nums)
        if any(q in h.lower() for h in hay):
            # Find which part number(s) matched for highlighting
            matched_numbers = []
            if q in c.toyota_oem.lower():
                matched_numbers.append(("Toyota OEM", c.toyota_oem))
            for mfr, nums in c.equivalents.items():
                for n in nums:
                    if q in n.lower() or q in mfr.lower():
                        matched_numbers.append((mfr, n))
            results.append({
                "category": c.category,
                "description": c.description,
                "toyota_oem": c.toyota_oem,
                "price_oem": list(c.price_oem),
                "equivalents": {mfr: list(nums) for mfr, nums in c.equivalents.items()},
                "notes": c.notes,
                "matched": matched_numbers,
            })
    return results


def by_category() -> dict[str, list[CrossRef]]:
    out: dict[str, list[CrossRef]] = {}
    for c in CATALOG:
        out.setdefault(c.category, []).append(c)
    return out

"""Shopping list generator.

Given an issue slug, assemble a practical parts/tools shopping list with
direct search URLs for AutoZone, RockAuto, Amazon. Prints a printable
checklist for a trip to the parts store.
"""
from urllib.parse import quote_plus
from .knowledge import ISSUES, PROCEDURES, PARTS


RETAILER_SEARCH = {
    "RockAuto":   "https://www.rockauto.com/en/catalog/,,,,,,,,,,,,,{q}",
    "AutoZone":   "https://www.autozone.com/searchresult?searchText={q}",
    "Amazon":     "https://www.amazon.com/s?k={q}",
    "eBay":       "https://www.ebay.com/sch/i.html?_nkw={q}",
    "ToyotaPartsDeal": "https://www.toyotapartsdeal.com/search?search_query={q}",
}


def search_url(retailer: str, query: str) -> str:
    tmpl = RETAILER_SEARCH.get(retailer)
    if not tmpl:
        return "#"
    return tmpl.format(q=quote_plus(query))


def list_for_issue(slug: str) -> dict:
    """Assemble a shopping list for a given issue."""
    issue = ISSUES.get(slug)
    if not issue:
        return {"error": f"no issue {slug}"}
    items = []
    total_low = 0
    total_high = 0

    # Parts directly referenced on the issue
    for part_slug in issue.related_parts:
        p = PARTS.get(part_slug)
        if not p:
            continue
        queries = [p.oem] if p.oem else []
        for mfr, num in p.aftermarket.items():
            queries.append(f"{mfr} {num}")
        items.append({
            "slug": part_slug,
            "name": p.name,
            "system": p.system,
            "oem": p.oem,
            "aftermarket": p.aftermarket,
            "price_usd": list(p.price_usd),
            "notes": p.notes,
            "search": {
                r: search_url(r, queries[0] if queries else p.name)
                for r in RETAILER_SEARCH
            } if queries else {r: search_url(r, p.name) for r in RETAILER_SEARCH},
        })
        total_low += p.price_usd[0]
        total_high += p.price_usd[1]

    # Parts from the referenced procedures (not already in related_parts)
    for proc_slug in issue.related_procedures:
        proc = PROCEDURES.get(proc_slug)
        if not proc:
            continue
        for part_name, part_desc in proc.parts.items():
            # Avoid duplicates
            already = any(part_name.lower() in i["name"].lower() for i in items)
            if already:
                continue
            items.append({
                "slug": None,
                "name": f"{part_name} ({proc.name})",
                "system": proc.system,
                "oem": part_desc,
                "aftermarket": {},
                "price_usd": [0, 0],
                "notes": f"From procedure: {proc.name}",
                "search": {r: search_url(r, part_desc) for r in RETAILER_SEARCH},
            })

    return {
        "issue_slug": slug,
        "issue_name": issue.name,
        "total_low": total_low,
        "total_high": total_high,
        "items": items,
        "difficulty": issue.difficulty,
        "related_procedures": [
            {"slug": ps, "name": PROCEDURES[ps].name, "time_min": PROCEDURES[ps].time_minutes}
            for ps in issue.related_procedures if ps in PROCEDURES
        ],
    }


def list_for_procedure(slug: str) -> dict:
    """Shopping list for a specific procedure."""
    p = PROCEDURES.get(slug)
    if not p:
        return {"error": f"no procedure {slug}"}
    items = []
    for part_name, part_desc in p.parts.items():
        items.append({
            "name": part_name,
            "description": part_desc,
            "search": {r: search_url(r, part_desc) for r in RETAILER_SEARCH},
        })
    return {
        "procedure_slug": slug,
        "procedure_name": p.name,
        "items": items,
        "tools": p.tools,
        "torque_specs": p.torque_specs,
        "time_min": p.time_minutes,
        "difficulty": p.difficulty,
    }

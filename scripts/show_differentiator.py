"""Print legality + rebooking on seeded data (rendered into README, checked in CI)."""
from airops import crewlegality, demo_helpers

s = demo_helpers.disruption_summary()
print("by cause:", {r["delay_code"]: r["n"] for r in s["by_cause"]})
print("illegal pairings:", s["illegal_pairings"], "| rebooking backlog:", s["rebooking_backlog"])
crew = {"crew_id": "C-EXAMPLE", "role": "fo", "assigned_flight": "MA-310",
        "duty_minutes": 700, "flight_minutes": 300, "rest_hours": 12.0, "consec_days": 2}
print("now:", crewlegality.find_illegal_pairings([crew]))
print("with MA-310 165 min late:", crewlegality.find_illegal_pairings([crew], {"MA-310": 165})[0]["violations"])
top = demo_helpers.rebook_demo("PAX-M207-00")["options"][0]
print("best rebooking:", top["rec_id"], top["score"], top["breakdown"])

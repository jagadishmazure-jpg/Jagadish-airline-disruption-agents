# SOP-02 Crew Legality Rules

## Duty limits
A crew member may not be assigned to a pairing that would exceed 14 hours
of duty (CL-DUTY-14), 8 hours of flight time (CL-FLIGHT-8), or a 6th
consecutive duty day (CL-CONSEC-6). Minimum rest between duties is 10
hours (CL-REST-10). These are simplified company rules for this demo.

## Illegal pairing response
When the legality engine flags a pairing, the crew scheduler must be
notified before departure. No crew member flies an illegal pairing; the
flight is held until a legal crew is assigned.

## Documentation
Every legality check result is written to the audit log with the rule IDs
that fired.

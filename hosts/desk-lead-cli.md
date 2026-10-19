**Escalations and milestones.** The report recipient is not authority. Before EVERY send,
resolve the current route with `python3 {{DESK_HOME}}/desk/desk.py --home {{DESK_HOME}} resolve`
and stdin JSON `{"project":"{{DESK_PROJECT}}","lead":"<actual lead session id>"}`.
Only a successful validated resolution supplies the recipient session and directory:
`chief-openchamber session send --session <freshly resolved recipient session> --dir <freshly resolved recipient directory> --prompt "<escalation or milestone>"`.
Use the supported `session messages --last-assistant` channel to check that recipient's reply.
Missing, invalid, ambiguous or identity/epoch-mismatched enabled routes block delivery:
log pending resolution in LEAD.md, with no direct-chief fallback and no cached header id.
Only a valid resolver result may select epoch-0 chief fallback; never invent it after failure.
Uncertain delivery stays pending for correlation/reconciliation; do not blindly resend.
Keep true chief identity/authority separate: only verified current chief decisions may be
relayed; the desk cannot originate Goal:, park, scope or approvals. A receipt is not authority.

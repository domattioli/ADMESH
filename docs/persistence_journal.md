# Persistence journal

Append-only log of interrupts across persistent ADMESH sessions.
Populated by `/log-interrupt`; rolled up at each session's WS-final
retro into actionable plan/constitution edits.

Schema (pipe-separated): `time | session | trigger_class | ws_at_interrupt | what_i_was_doing | user_verbatim_or_N/A | resumption_cost | lesson`.

See `.claude/skills/log-interrupt/SKILL.md` for triggers and
classifications.

---

| time | session | trigger | ws | was_doing | user_said | cost | lesson |
|------|---------|---------|----|-----------|-----------|------|--------|

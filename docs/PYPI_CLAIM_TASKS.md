# Issue #13 Task Breakdown: PyPI Package Name Claim

**Issue**: #13  
**Status**: Planning phase  
**Acceptance**: Email drafted; contact plan & PEP 541 fallback documented  

---

## Atomic Task List (in order)

### Task 1: Email Draft Review & Finalization
**Objective**: Validate email tone, accuracy, and completeness  
**Acceptance**: Email approved for sending (check against tone, evidence, timeline)  
**Depends on**: None  
**Owner**: [Human review by project lead]  
**Effort**: 15 min (review only, no code)  

**Checklist**:
- [ ] Email tone is professional & non-threatening
- [ ] Evidence links are correct (GitHub, PyPI, historical context)
- [ ] Proposed timelines are reasonable (21-day response window)
- [ ] Fallback (PEP 541) is explained clearly
- [ ] Contact info (reply email) is correct

---

### Task 2: Send Email to Maintainer
**Objective**: Initiate contact with hroncok (miro@hroncok.cz)  
**Acceptance**: Email delivery confirmed; timestamp logged in CONTACT_LOG.md  
**Depends on**: Task 1 (approval)  
**Owner**: [Project lead or delegated reviewer]  
**Effort**: 5 min (copy/paste, send, log)  

**Checklist**:
- [ ] Email sent to miro@hroncok.cz
- [ ] CC'd any relevant PyPI/open-source contacts if available
- [ ] Timestamp recorded: `[DATE HH:MM]`
- [ ] Response deadline recorded: `[DATE + 21 days]`
- [ ] Entry added to CONTACT_LOG.md outcome table

---

### Task 3: Monitor & Document Response
**Objective**: Track maintainer response; update decision log  
**Acceptance**: Response (or lack thereof) logged within 24h of receipt  
**Depends on**: Task 2 (email sent)  
**Owner**: [Assigned reviewer or auto-check]  
**Effort**: 5 min per check (up to 21 days)  

**Checklist**:
- [ ] Check email for reply daily (or set calendar reminder)
- [ ] If response received: log date, summary, decision (rename vs. cede vs. refuse)
- [ ] If case 1 or 2 (positive): update CONTACT_LOG.md, proceed to Task 4
- [ ] If case 3 (no response): proceed to Task 5 on day 22
- [ ] If case 4 (refusal): proceed to Task 5

---

### Task 4: Execute Positive Outcome (Cases 1 & 2)
**Objective**: Coordinate with maintainer on namespace transition  
**Acceptance**: Agreement finalized; PR or timeline established  
**Depends on**: Task 3 (positive response received)  
**Owner**: [Project lead]  
**Effort**: 30 min (coordination emails, documentation)  

**Checklist**:
- [ ] Confirm exact rename or cede procedure with maintainer
- [ ] If rename: request they update PyPI distribution name to `python-admesh` or `admesh-stl`
- [ ] If cede: coordinate transition timeline (do they want to keep a final release? auto-redirect?)
- [ ] Log agreement in CONTACT_LOG.md
- [ ] Confirm `admesh` is available on PyPI
- [ ] Proceed to v0.1.0 release when ready

---

### Task 5: File PEP 541 Fallback (Cases 3 & 4)
**Objective**: Escalate to PyPI if no positive response or refusal  
**Acceptance**: PEP 541 request filed at github.com/pypi/support; case reference logged  
**Depends on**: Task 3 (no response after 21 days OR refusal)  
**Owner**: [Project lead]  
**Effort**: 20 min (fill template, file issue, track)  

**Checklist**:
- [ ] Review PEP 541 template in CONTACT_LOG.md
- [ ] Customize with actual contact date & response status
- [ ] File issue at https://github.com/pypi/support
- [ ] Get ticket/reference number
- [ ] Log in CONTACT_LOG.md outcome table
- [ ] Update issue #13 with status & link to PEP 541 request
- [ ] Wait ~7 days for PyPI response
- [ ] If approved: proceed to v0.1.0 release
- [ ] If denied: comment on #13 with decision + next steps (possibly re-open discussion)

---

### Task 6: Update Issue #13 & Cleanup
**Objective**: Close or update GitHub issue with final status  
**Acceptance**: Issue comment posted; PR or tracking link added  
**Depends on**: Task 4 (positive) OR Task 5 (PEP 541 outcome)  
**Owner**: [Project lead]  
**Effort**: 10 min  

**Checklist**:
- [ ] Post comment on #13 with final status (approved, escalated, etc.)
- [ ] Link to CONTACT_LOG.md in repo
- [ ] Close issue if resolved (positive outcome)
- [ ] Leave open if awaiting PEP 541 response
- [ ] Add label: `status:contact-phase` → `status:resolved` or `status:escalated-pep541`

---

## Dependency Graph

```
Task 1 (Review)
    ↓
Task 2 (Send)
    ↓
Task 3 (Monitor)
    ├→ Task 4 (Positive: coordinate)
    │   ↓
    │ Task 6 (Close as resolved)
    │
    └→ Task 5 (PEP 541: escalate)
        ↓
      Task 6 (Update as escalated)
```

---

## Success Criteria Summary

✓ **Planning phase complete** when:
- Email draft is reviewed and approved
- CONTACT_LOG.md is committed to `daily-issue-fixing` branch
- Task breakdown is documented

✓ **Issue resolved** when:
- Either: Maintainer agrees to rename/cede (Case 1/2) → claim `admesh`, ship v0.1.0
- Or: PEP 541 approved (Case 5) → claim `admesh`, ship v0.1.0
- Or: Escalation documented (Case 4, denied) → open design discussion on #13

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Email bounces | Delayed contact | Use GitHub contact if email fails; search for alt email |
| No response after 21 days | Escalate to PEP 541 | Automatic; PEP 541 well-established process |
| Maintainer refuses | Escalate to PyPI | PEP 541 provides arbitration; cite prior art & inactive status |
| PyPI denies PEP 541 | Blocked v0.1.0 | Unlikely (evidence is strong); discuss alternatives (e.g., admesh2d) |

---

## Timeline Estimate

- **Task 1**: 15 min (review)
- **Task 2**: 5 min (send) + 5 min (log)
- **Task 3**: 5 min/check, up to 21 days (passively waiting)
- **Task 4 or 5**: 20–30 min (execute outcome or file PEP 541)
- **Task 6**: 10 min (close)

**Total active time**: ~1 hour (spread over ~3 weeks)  
**Critical path**: Tasks 1→2→3→(4 or 5)→6

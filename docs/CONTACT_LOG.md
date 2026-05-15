# PyPI Package Name Claim: Contact Log & Decision Tree

**Issue**: #13  
**Status**: Initial contact phase  
**Last updated**: 2026-05-14  

---

## Contact Timeline

### Attempt 1: Email to Maintainer (Miro Hrončok)

**Target**: miro@hroncok.cz  
**Package**: admesh (https://pypi.org/project/admesh/)  
**Current maintainer**: hroncok  
**Last release**: June 24, 2018 (~7 years inactive)  
**Current usage**: ~935 downloads/month (declining)  

**Scheduled date**: [TBD — to be sent]  
**Response deadline**: [TBD + 21 days]  

#### Email Draft

```
Subject: Request to rename PyPI package "admesh" (STL tools) — namespace reuse for newer project

Hello Miro,

I'm writing on behalf of the ADMESH project (automatic, distributed mesh generator for 
shallow-water and hydrodynamic domains). We've been reviving and modernizing a 2012 MATLAB 
mesh generator under the name "ADMESH" and are preparing our first PyPI release (v0.1.0) 
in the coming weeks.

Unfortunately, the PyPI namespace "admesh" is already claimed by your STL manipulation 
library (last released June 24, 2018). We'd like to work with you to find a solution that 
minimizes disruption for both projects.

**Our proposal** (in order of preference):
1. Rename your package distribution to `python-admesh` or `admesh-stl` while keeping the 
   importable module name as `admesh`. This preserves your users' import statements and 
   makes room for our project.
2. If that's not feasible, could you cede the `admesh` namespace to us? We can offer to:
   - Maintain an import alias for your old code if your users still depend on it.
   - Coordinate the transition on your PyPI release notes and GitHub.

**Context**:
- Our project: https://github.com/domattioli/ADMESH (Python port of the 2012 MATLAB original)
- Your project: https://pypi.org/project/admesh/ (Python bindings for STL tools)
- Historical use: "ADMESH" as a mesh-generation name predates the PyPI package by several years.
- Current adoption: Your package sees ~935 downloads/month (mostly legacy); ours will be new.

**Timeline**: We're targeting v0.1.0 release on [DATE TBD]. If we don't hear from you by 
[DATE + 21 days], we'll proceed with a PEP 541 request to PyPI for namespace reclamation.

No hard feelings either way — just wanted to reach out first! Feel free to reply here or 
open an issue on our repo if you'd like to discuss.

Cheers,
[Domi — domattioli@github]
```

---

## Decision Tree

```
┌─ Email sent (date: __________)
│
├─ CASE 1: Maintainer agrees to rename (✓ best outcome)
│  └─ They rename to `python-admesh` or `admesh-stl`
│     └─ We claim `admesh`, test, ship v0.1.0
│
├─ CASE 2: Maintainer partially agrees (? acceptable)
│  └─ They agree to cede namespace
│     └─ We provide import alias or transition docs
│        └─ We claim `admesh`, ship v0.1.0
│
├─ CASE 3: No response after 21 days
│  └─ File PEP 541 request (github.com/pypi/support)
│     └─ Wait ~7 days for PyPI decision
│        ├─ Approved: We claim `admesh`
│        └─ Denied: Escalate to issue #13 for discussion
│
└─ CASE 4: Maintainer refuses / hostile response
   └─ File PEP 541 request as evidence of good-faith attempt
      └─ Let PyPI arbitrate
```

---

## PEP 541 Fallback Template

*(Prepared for use if Cases 3 or 4 occur)*

```
Title: Namespace reclamation request — "admesh" PyPI package

Package: admesh (https://pypi.org/project/admesh/)
Current maintainer: hroncok
Last release: June 24, 2018
Monthly downloads: ~935 (declining)
Current usage: Deprecated; wheel support only for Python 3.6-3.7

Requesting organization: domattioli (GitHub)
Requesting project: ADMESH mesh generator (https://github.com/domattioli/ADMESH)
Expected release: v0.1.0 (May 2026)

Evidence:
- Email contact attempt sent [DATE], no response after [N days]
- "ADMESH" as a mesh-generation name has prior art dating to 2012 MATLAB codebase
- Our project is a direct continuation of the 2012 original, not a fork of the PyPI package
- The existing PyPI package is unmaintained and incompatible with modern Python (no wheels post-3.7)

Proposed resolution:
- Maintainer to rename their distribution to `python-admesh` or `admesh-stl` 
  (keeping module name as `admesh` to minimize user disruption)
- OR reclaim `admesh` namespace for the ADMESH mesh-generator project
```

---

## Follow-up Actions

- [ ] **Draft email**: Review & finalize the template above
- [ ] **Send email**: Copy to miro@hroncok.cz + CC [maintainers list]
- [ ] **Log date**: Record send timestamp in this file
- [ ] **Set reminder**: 21-day follow-up (auto-calendar or GitHub Actions)
- [ ] **Issue comment**: Post contact-log link as comment on issue #13
- [ ] **Evaluate response**: Update this file with outcome within 24h of receiving reply
- [ ] **PEP 541 decision**: If needed, file request and track at github.com/pypi/support

---

## Outcome Log

*(To be updated as contact progresses)*

| Date | Event | Details | Owner |
|------|-------|---------|-------|
| 2026-05-14 | Plan drafted | Email draft + decision tree prepared | Claude |
| [TBD] | Email sent | Contact to hroncok | [To be assigned] |
| [TBD] | Response received | Document here | [To be assigned] |
| [TBD] | Final decision | Update issue #13 | [To be assigned] |

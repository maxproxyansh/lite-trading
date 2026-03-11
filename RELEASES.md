# Release Log

## 2026-03-11 — `8533515`

**Latest:** feat: add reusable brand logo and icon set
**Author:** codex
**Stats:**  81 files changed, 13842 insertions(+), 1540 deletions(-)

### Features
- feat: add reusable brand logo and icon set (8533515)
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore public signup on login page (955b3ef)
- fix: UI polish — delete ticker bar, fix portfolio dropdown, add ₹ prefix, keyboard shortcuts, option chart UX, disable public signup (8e043b6)
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for ddf174c (b494c8f)
- audit: harden runtime flows and finalize docs (ddf174c)
- docs: update release log for 3682e4c (9af01f1)
- Track CLAUDE.md in repo — contains project docs, not secrets (3682e4c)
- docs: update release log for 003690d (d7eb5c6)
- chore: gitignore root CLAUDE.md (contains local testing instructions) (003690d)
- docs: update release log for 955b3ef (8f4af51)
- docs: update release log for 8e043b6 (ef081cd)
- docs: update release log for 1980bc6 (31037a0)
- docs: mark Railway auto-deploy as fixed in platform audit (1980bc6)
- docs: update release log for 649d5b7 (d2503d0)
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `ddf174c`

**Latest:** audit: harden runtime flows and finalize docs
**Author:** codex
**Stats:**  69 files changed, 13741 insertions(+), 1522 deletions(-)

### Features
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore public signup on login page (955b3ef)
- fix: UI polish — delete ticker bar, fix portfolio dropdown, add ₹ prefix, keyboard shortcuts, option chart UX, disable public signup (8e043b6)
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- audit: harden runtime flows and finalize docs (ddf174c)
- docs: update release log for 3682e4c (9af01f1)
- Track CLAUDE.md in repo — contains project docs, not secrets (3682e4c)
- docs: update release log for 003690d (d7eb5c6)
- chore: gitignore root CLAUDE.md (contains local testing instructions) (003690d)
- docs: update release log for 955b3ef (8f4af51)
- docs: update release log for 8e043b6 (ef081cd)
- docs: update release log for 1980bc6 (31037a0)
- docs: mark Railway auto-deploy as fixed in platform audit (1980bc6)
- docs: update release log for 649d5b7 (d2503d0)
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `3682e4c`

**Latest:** Track CLAUDE.md in repo — contains project docs, not secrets
**Author:** codex
**Stats:**  65 files changed, 13447 insertions(+), 1417 deletions(-)

### Features
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore public signup on login page (955b3ef)
- fix: UI polish — delete ticker bar, fix portfolio dropdown, add ₹ prefix, keyboard shortcuts, option chart UX, disable public signup (8e043b6)
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- Track CLAUDE.md in repo — contains project docs, not secrets (3682e4c)
- docs: update release log for 003690d (d7eb5c6)
- chore: gitignore root CLAUDE.md (contains local testing instructions) (003690d)
- docs: update release log for 955b3ef (8f4af51)
- docs: update release log for 8e043b6 (ef081cd)
- docs: update release log for 1980bc6 (31037a0)
- docs: mark Railway auto-deploy as fixed in platform audit (1980bc6)
- docs: update release log for 649d5b7 (d2503d0)
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `003690d`

**Latest:** chore: gitignore root CLAUDE.md (contains local testing instructions)
**Author:** codex
**Stats:**  65 files changed, 13351 insertions(+), 1417 deletions(-)

### Features
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore public signup on login page (955b3ef)
- fix: UI polish — delete ticker bar, fix portfolio dropdown, add ₹ prefix, keyboard shortcuts, option chart UX, disable public signup (8e043b6)
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- chore: gitignore root CLAUDE.md (contains local testing instructions) (003690d)
- docs: update release log for 955b3ef (8f4af51)
- docs: update release log for 8e043b6 (ef081cd)
- docs: update release log for 1980bc6 (31037a0)
- docs: mark Railway auto-deploy as fixed in platform audit (1980bc6)
- docs: update release log for 649d5b7 (d2503d0)
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `955b3ef`

**Latest:** fix: restore public signup on login page
**Author:** codex
**Stats:**  64 files changed, 13297 insertions(+), 1417 deletions(-)

### Features
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore public signup on login page (955b3ef)
- fix: UI polish — delete ticker bar, fix portfolio dropdown, add ₹ prefix, keyboard shortcuts, option chart UX, disable public signup (8e043b6)
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 8e043b6 (ef081cd)
- docs: update release log for 1980bc6 (31037a0)
- docs: mark Railway auto-deploy as fixed in platform audit (1980bc6)
- docs: update release log for 649d5b7 (d2503d0)
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `8e043b6`

**Latest:** fix: UI polish — delete ticker bar, fix portfolio dropdown, add ₹ prefix, keyboard shortcuts, option chart UX, disable public signup
**Author:** codex
**Stats:**  64 files changed, 13254 insertions(+), 1456 deletions(-)

### Features
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: UI polish — delete ticker bar, fix portfolio dropdown, add ₹ prefix, keyboard shortcuts, option chart UX, disable public signup (8e043b6)
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 1980bc6 (31037a0)
- docs: mark Railway auto-deploy as fixed in platform audit (1980bc6)
- docs: update release log for 649d5b7 (d2503d0)
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `1980bc6`

**Latest:** docs: mark Railway auto-deploy as fixed in platform audit
**Author:** codex
**Stats:**  62 files changed, 13107 insertions(+), 1273 deletions(-)

### Features
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: mark Railway auto-deploy as fixed in platform audit (1980bc6)
- docs: update release log for 649d5b7 (d2503d0)
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `649d5b7`

**Latest:** Add bracket orders and detailed agent analytics (#10)
**Author:** Max
**Stats:**  62 files changed, 13060 insertions(+), 1273 deletions(-)

### Features
- Add bracket orders and detailed agent analytics (#10) (649d5b7)
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 12312b6 (53a47d5)
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `12312b6`

**Latest:** Add order pagination, rate limit headers, and webhooks (#9)
**Author:** Max
**Stats:**  61 files changed, 11215 insertions(+), 1227 deletions(-)

### Features
- Add order pagination, rate limit headers, and webhooks (#9) (12312b6)
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 055b87f (b06abe6)
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `055b87f`

**Latest:** Add agent alerts, order modification, and partial close (#8)
**Author:** Max
**Stats:**  58 files changed, 9559 insertions(+), 1239 deletions(-)

### Features
- Add agent alerts, order modification, and partial close (#8) (055b87f)
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 9c3e7a9 (a7e1b07)
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `9c3e7a9`

**Latest:** feat: add weekly and monthly chart timeframes (#11)
**Author:** Max
**Stats:**  56 files changed, 9016 insertions(+), 1193 deletions(-)

### Features
- feat: add weekly and monthly chart timeframes (#11) (9c3e7a9)
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 4e6c651 (4bc84db)
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `4e6c651`

**Latest:** docs: add platform audit with deployment issues and fixes
**Author:** codex
**Stats:**  56 files changed, 8870 insertions(+), 1191 deletions(-)

### Features
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: add platform audit with deployment issues and fixes (4e6c651)
- docs: update release log for bf953c6 (4232f29)
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `bf953c6`

**Latest:** fix: default portfolio selection to manual instead of agent
**Author:** codex
**Stats:**  55 files changed, 8730 insertions(+), 1191 deletions(-)

### Features
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: default portfolio selection to manual instead of agent (bf953c6)
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 95de577 (be4dce1)
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `95de577`

**Latest:** fix: add missing OrderModifyRequest schema and alert scopes
**Author:** codex
**Stats:**  55 files changed, 8694 insertions(+), 1190 deletions(-)

### Features
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: add missing OrderModifyRequest schema and alert scopes (95de577)
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for de7fdfb (3729d15)
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `de7fdfb`

**Latest:** Merge pull request #7 from maxproxyansh/codex/option-chart-history
**Author:** Max
**Stats:**  55 files changed, 8653 insertions(+), 1190 deletions(-)

### Features
- feat: add option contract chart history (3cd9c87)
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 5c9360e (1e9c3aa)
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `5c9360e`

**Latest:** Merge pull request #6 from maxproxyansh/codex/chart-history-artifacts
**Author:** Max
**Stats:**  55 files changed, 7789 insertions(+), 1169 deletions(-)

### Features
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 5d2471a (a40213e)
- chore: remove accidentally committed worktree submodule (5d2471a)
- chore: sync generated OpenAPI artifacts (9e32db9)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `5d2471a`

**Latest:** chore: remove accidentally committed worktree submodule
**Author:** codex
**Stats:**  55 files changed, 6627 insertions(+), 1126 deletions(-)

### Features
- Add candles before filter (129a7f0)
- feat: close agent market access and docs gaps (c112efa)
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: restore candles pagination, add unauth market test (cde1673)
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- chore: remove accidentally committed worktree submodule (5d2471a)
- docs: update release log for 2c72400 (c353a73)
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `2c72400`

**Latest:** fix: add has_more and next_before to CandleResponse schema
**Author:** codex
**Stats:**  55 files changed, 6099 insertions(+), 1007 deletions(-)

### Features
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: add has_more and next_before to CandleResponse schema (2c72400)
- fix: align final latency review tweaks (c59820b)
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- perf: cut quote latency across backend and frontend (092adc8)
- docs: update release log for aca2c20 (95aeb04)
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `aca2c20`

**Latest:** fix: cosmetic polish — padding, ATM default, alerts panel close button
**Author:** codex
**Stats:**  28 files changed, 3898 insertions(+), 432 deletions(-)

### Features
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Fixes
- fix: cosmetic polish — padding, ATM default, alerts panel close button (aca2c20)

### Other
- docs: update release log for 1b2e7e3 (0ede45a)
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `1b2e7e3`

**Latest:** feat: redesign toasts to match chart alerts glass-morphism style
**Author:** codex
**Stats:**  22 files changed, 3844 insertions(+), 414 deletions(-)

### Features
- feat: redesign toasts to match chart alerts glass-morphism style (1b2e7e3)
- feat: add autonomous agent trading platform (c118a77)

### Other
- docs: update release log for 5a49a5d (daa380c)
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

## 2026-03-11 — `5a49a5d`

**Latest:** ci: add auto-deploy and release notes workflows
**Author:** codex
**Stats:**  2 files changed, 167 insertions(+)

### Other
- ci: add auto-deploy and release notes workflows (5a49a5d)

---

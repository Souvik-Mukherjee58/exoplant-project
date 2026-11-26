# Archives of historical material

Byte-exact copies with one SHA-256 manifest each. Formatting hooks would alter 50 of the 69 original documents (they would
also break the context lines of patch files), so the originals are kept in archives instead of being reformatted.
Everything inside is **history, not current**; `.agent/ERRATA.md` lists the corrections.

| Archive                              | Files | SHA-256 of the archive                                             | Where             | Publication                                           |
| :----------------------------------- | ----: | :----------------------------------------------------------------- | :---------------- | :---------------------------------------------------- |
| `history-open-2026-11-24.zip`        |    16 | `fbbc0b33cc9b30930707bc5b1d3b4feaba0cf2c0552d9e180f0da258efb0813a` | `.agent/archive/` | With the other repairs                                |
| `history-withheld-2026-11-24.zip`    |    62 | `4ac79147c09d00845f7aee2e6be2387fb785d9d2da90873976973aecf0fd7354` | Private backup    | After the guard repair is live and the owner approves |
| `repair-logs-2026-11-25.zip`         |    29 | `bd4270f805888993effbb6b0ebc2283711bc615c18f861ff08fc6abcbef6cf75` | `.agent/archive/` | With the other repairs                                |
| `guard-logs-withheld-2026-11-25.zip` |    25 | `94dd7b59230a72b4d5c57eac643c12dfbc9cb252c8cd7244688b7bb67b8c5f61` | Private backup    | After the guard repair is live                        |

## Contents

| Archive  | Content                                                                                                                                      | Provenance                                                            |
| :------- | :------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------- |
| Open     | Phase 2 verification, plans and patches; eclipse design; ADR 0006 diffs; ADR 0006 and `.gitignore` as of the backup                          | Written in the audits of 2026-11-23/24; working copies at backup time |
| Withheld | Guard audit, guard designs v2–v3.2, maintenance and enforcement proposals, PLAN comparison and proposal, progress proposals, owner decisions | Written in the same audits                                            |
| Logs     | Test, hook, mutation and fresh-clone logs of this repair, including runs marked invalid; the scripts that produced them                      | This repair, 2026-11-24/25                                            |
| Withheld | Recovered earlier work                                                                                                                       | Preserved private material                                            |

## Why the second archive is withheld

1. It describes, with reproductions, weaknesses of the guard that protects `main` **today**. Publishing it before the fix is
   live would be a set of working instructions.
2. Three files describe operational details of the development setup. They contain no secret.
3. Five files contain synthetic secret-like test strings in full. They are test data; an archive keeps them byte-exact
   without weakening the secret detection for ordinary files.

Nothing is dropped. The withheld archive is complete, hashed and stored privately.

In the published logs, local directory names are replaced by `<repo>`, `<scratch>` and `<private>`; the unchanged logs are kept
privately.

## How to check

```bash
sha256sum .agent/archive/history-open-2026-11-24.zip
mkdir check && cd check && unzip -q ../.agent/archive/history-open-2026-11-24.zip && sha256sum -c MANIFEST.sha256
```

# Licence audit, 10 October 2026

What `NOTICE.md` could not settle, and why. The audit was written on 10 October 2026, when the repository was private
(`LorenzoBottaccioli/InteligentBuidlingOptimizationEDU`); most of it is a risk that starts when it is made public, or when a copy
of the files is given to students. The notes below the first section are **as of 10 October**; the section "Decided on 13 October"
says what changed.

## Decided on 13 October 2026

- **New repository, one clean commit** (`IntelligentBuildingOptimizationEDU`), instead of rewriting the history of the private one,
  which keeps the 4 IWEC/Meteonorm weather blobs in two commits and stays as an archive. Points 2 and 3 below are therefore settled
  for this repository: no weather file that may not be redistributed is in it or in its history.
- **The folders `Simulation examples/` and `Surrogate modeling examples/` are not published** (they held the 13 Meteonorm files, the
  22 TensorBoard logs with a private computer's name, and the old example notebooks). Point 5 is therefore settled for the TensorBoard
  logs; the DesignBuilder path in the headers of the three copies of `tutorials/test.idf` remains.
- **The documentation PDF of the first version (A. Orellana, July 2025) is not published**, until his permission is obtained.
- **Licence of the platform's own code: Apache-2.0** (point 1). Not checked against Politecnico di Torino's policy.
- **Teacher solutions are not published**: `reference/` and `course_notebooks_bdopt/Laboratory_solution.ipynb` were left out of the single commit.
- Not decided: the BESOS-derived tutorial notebooks (point 4).

## Decided on 10 October 2026

- **IWEC and Meteonorm files (points 2 and 3 below): ignored by git.** `.gitignore` has `*IWEC*.epw` and `*-hour.epw`; the 4 IWEC and 13
  Meteonorm files were removed from the index (`git rm --cached`) and stay on disk. `tests/tutorials/fetch_iwec.py` downloads the IWEC
  file again (checked: byte-identical to the one that was in git). Not done: the two commits that contained them (`156398c`, `c9283f9`)
  still do; the repository is private, and removing them from history means rewriting it. The Meteonorm files have no way to be fetched.
- **BESOS (point 4): accepted by the author.** bdopt: its licence is being handled with its author.

## Decisions for the authors

1. **Licence of the platform's own code.** None is declared. Options and consequences depend on PoliTo's policy on software
   produced at the university; this audit does not choose one.
2. **ASHRAE IWEC file** (`ITA_Torino.160590_IWEC.epw`, 4 copies). The licence allows use on a single machine and backup copies, and says
   "Distribution to third parties without ASHRAE's permission is expressly forbidden". The EnergyPlus site is licensed to host it; this
   repository is not. Options: ask ASHRAE; or have the platform download it from energyplus.net when a session is created (the
   weather page already does this) and keep it out of git. Whether a student's own download through the platform counts as
   distribution by the platform is not answered by the licence.
3. **Meteonorm files** (13 EPW, header "METEONORM Version 8.2.0.24079"). The Meteonorm 8 licence forbids transferring generated data to
   third parties, including "distribution of the data by making available to third parties results based on the data (e.g. through
   web applications, simulation software)", without a written agreement with Meteotest. No education-specific redistribution clause
   was found. Options: written agreement with Meteotest; or replace them with Open-Meteo, PVGIS or EnergyPlus-list files for the same places
   (the platform builds all three).
4. **BESOS-derived tutorial material.** BESOS and its examples are GPL-3.0. A notebook or figure copied or adapted from them, when published,
   must carry a modification notice with date, the BESOS copyright and licence notice, and be licensed as a whole under the GPL (§5).
   A re-implementation that copies no BESOS expression is not covered. The ports in `course_notebooks_bdopt/` and the four tutorials were
   made from the course notebooks (7 copies, README of that folder); the course notebooks are **not** in besos-examples under those names
   (the closest there are `ExamplesOverview`, `SMOverview`, `FitGPAdaptive`, `BuildingOptimization`), so which text is copied from BESOS
   and which is the course's own is for the author of the course notebooks to say. Two figures are byte-identical or derived from
   GPL-3.0 BESOS files.
5. **Personal data in the repository.** The 22 TensorBoard event files under `Surrogate modeling examples/*/runs/` carry the name of a
   private computer (`Andres-Orellana-Pc`), and the IDF headers carry the path `C:\Users\chiesa\Dropbox (Personale)\...`. Neither is a
   licence matter; remove or keep as the people concerned prefer.
6. **Who to credit.** Andres Orellana (the first version of the platform: documentation July 2025), the author(s) of the IDF models
   (user `chiesa` in the DesignBuilder headers), the author(s) of the course notebooks. `NOTICE.md` names only what the files say.

## Could not be verified

- Original source and licence of `LOLA-Voronoi.jpg` and of the course's `surrogate_overview.png` (neither is in the BESOS repositories).
- How energyplus.net asks users to cite EnergyPlus (the site is a JavaScript application the tools could not read).
- Whether Expat is linked into a particular FMU generated by EnergyPlusToFMU.
- Per-file licence of the two openHAB sounds (they are in the openHAB distribution under its EPL-2.0 licence; no per-file notice found).
- Whether the EC licence (CC BY 4.0) formally governs PVGIS TMY output (no PVGIS page names a licence for it); whether JRC asks to cite Huld et al. 2012.
- Terms of Open-Meteo on redistributing stored files beyond what CC BY 4.0 allows.
- Licence of `torch 1.13.1+cpu` specifically (only the current release and the repository licence were read).
- Fanger (1970) from a publisher; the status page of ISO 7730:2025.
- ERA5-Ensemble and IFS Assimilation Long-Window attribution texts (none published by Open-Meteo); not used by the platform.
- The licence line of the Zenodo record of BESOS (`gpl-2.0`) disagrees with the repository's GPLv3 text; the repository text was taken.

## Method

Two research passes read the official pages (Open-Meteo, Copernicus/ECMWF, JRC, energyplus.net, Climate.OneBuilding, ASHRAE,
Meteotest; BESOS and EnergyPlus repositories, PyPI/npm, Crossref); package licences were read from the installed metadata of
`backend:latest`, `jupyter:smartbuilding-unified` and `jupyter:smartbuilding-surrogate-plotly`; files in the repository were
compared by hash with the BESOS files.

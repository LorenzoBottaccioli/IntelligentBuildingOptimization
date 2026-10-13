# Credits, licences and citations

This platform is built on the work of others. This file lists what is used, under which terms, and how to credit it.
Every licence and every reference below was read from the source named (the project's own repository, publisher, DOI
record or data provider) on 10 October 2026; where a point could not be confirmed it says so. It is not legal advice.
The same information, shorter, is on the page **Credits & licences** of the platform.

Full texts that must accompany redistributed files are in [`licenses/`](licenses/).

## 1. The platform

- **Smart Building Educational Platform**, Politecnico di Torino. Lorenzo Bottaccioli.
- The first version of the platform was documented by **Andres Orellana** (*Smart Building Educational Platform source code
  documentation*, July 2025; the document is not part of this repository). His exact contribution is to be confirmed by the authors.
- Licence of the platform's own code: **Apache License 2.0** ([`LICENSE`](LICENSE)). Chosen by the author on 13 October 2026; whether
  Politecnico di Torino's policy on software produced at the university requires a different licence has not been checked.
  Third-party material below keeps its own licence whatever is chosen, and the BESOS-derived tutorial notebooks are a separate
  case (section 4).
- The logo of Politecnico di Torino (`frontend/public/polito_logo.png`) belongs to the university and is not covered by any
  licence of this repository.

## 2. Weather data

| Source | Terms | What the platform does | Credit to show |
| --- | --- | --- | --- |
| **Open-Meteo** (real years) | Data: CC BY 4.0 (<https://open-meteo.com/en/licence>). Free API: non-commercial only, fewer than 10,000 calls per day, 5,000 per hour, 600 per minute; "incorporating our service into educational content" and "public research conducted at public institutions" are listed as non-commercial (<https://open-meteo.com/en/terms>) | Builds annual EPW files from the archive; the converted files are changes to the data | "Weather data by Open-Meteo.com" with a link to <https://open-meteo.com/>, a link to the licence, and a statement that the data were changed |
| **ERA5, ERA5-Land, CERRA, ECMWF IFS** (under Open-Meteo, PVGIS-ERA5) | CC BY since 2 July 2025 (before it, the Copernicus licence with the same wording below) | as above | "Contains modified Copernicus Climate Change Service information [year]". "Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains." |
| **PVGIS** typical year | "Free for public use if the source is acknowledged (PVGIS © European Communities, 2001-2026)" (data download page of the JRC). No licence name is stated for the TMY output. | Downloads a TMY as EPW | "PVGIS © European Communities, 2001-[year]" and the Copernicus notice above (the TMY is built on ERA5 or on the PVGIS solar databases) |
| **EnergyPlus weather list** (3,033 locations) | Per source (<https://energyplus.net/weather/sources>); there is no blanket licence. IWEC: DOE may distribute the EPW conversion free of charge; users have a single-machine licence from ASHRAE | Downloads the file the student chooses; its header keeps the copyright line | The header of each file (COMMENTS 1) |
| **Climate.OneBuilding.org** | "Copyright © 2014-2026 Climate.OneBuilding. All Rights Reserved." No licence; no redistribution terms | Link only; the platform does not download from it | Lawrie, Linda K, Drury B Crawley. 2026. *Development of Global Typical Meteorological Years (TMYx).* <https://climate.onebuilding.org> |

References: ERA5 — Hersbach, H. et al. (2018) *ERA5 hourly data on single levels from 1940 to present.* Copernicus Climate Change
Service (C3S) Climate Data Store (CDS), DOI 10.24381/cds.adbb2d47. ERA5-Land — DOI 10.24381/cds.e2161bac (Muñoz Sabater 2019).
CERRA — DOI 10.24381/cds.622a565a (Schimanke et al. 2021). Open-Meteo — Zippenfenig, P. (2023). *Open-Meteo.com Weather API*
[Computer software]. Zenodo. <https://doi.org/10.5281/ZENODO.7970649> (citation is encouraged, not required). PVGIS TMY method —
Huld, T., Paietta, E., Zangheri, P., Pinedo Pascua, I. (2018) *Assembling Typical Meteorological Year Data Sets for Building Energy
Performance Using Reanalysis and Satellite-Based Data.* Atmosphere 9, <https://doi.org/10.3390/atmos9020053>.

### Weather files that are not in git

The two kinds of file below may not be redistributed, so they are **ignored by git** (`.gitignore`: `*IWEC*.epw`, `*-hour.epw`) and removed
from its index; they stay on the disk of whoever has them. This repository was started on 13 October 2026 from a single clean commit,
so no history contains them (the earlier private repository, which does, is kept as an archive). A fresh clone gets the IWEC file with `tests/tutorials/fetch_iwec.py` (a copy for each user, from the
EnergyPlus site); the Meteonorm files cannot be fetched, so the examples that use them need those files from their owner.

| Files | Terms | Status |
| --- | --- | --- |
| `ITA_Torino.160590_IWEC.epw` (2 places: `tutorials/`, the demo seed in `backend/seed_sessions/bdopt-demo/`) | ASHRAE IWEC licence: use on a single machine, copies for backup; "Distribution to third parties without ASHRAE's permission is expressly forbidden" (<https://energyplus-weather.s3.amazonaws.com/europe_wmo_region_6/ITA/ITA_Torino.160590_IWEC/ASHRAE_Copyright_and_IWEC_License.txt>) | Not in git. Would not be covered by the licence if the repository were public or the files handed to students |
| 13 EPW files of the former example folders `Simulation examples/` and `Surrogate modeling examples/` (Torino, Larnaca, Paris), header "METEONORM Version 8.2.0.24079"; those folders are no longer part of this repository | Meteonorm 8 licence: "the transfer of data generated using the Software to third parties without the written agreement of Meteotest is not allowed"; credit "Data source Meteonorm [version]" (<https://meteonorm.com/assets/downloads/mn8_eula.pdf>) | Not in git. Would need a written agreement with Meteotest to be distributed |

## 3. Simulation and building models

| Item | Licence | Obligation |
| --- | --- | --- |
| **EnergyPlus** version 9.6 (run in the image `nrel/energyplus:9.6.0`; not redistributed by this repository) | BSD-3-like, Copyright (c) 1996-present The Board of Trustees of the University of Illinois, The Regents of the University of California (LBNL), Oak Ridge National Laboratory, Alliance for Energy Innovation, LLC and other contributors ([text](licenses/EnergyPlus-LICENSE.txt)) | Say "EnergyPlus version 9.6" when referring to the software; do not use "EnergyPlus" or "E+" in a product name without DOE's consent |
| **EnergyPlus Reference Data Sets** `backend/datasets/WindowGlassMaterials.idf`, `WindowGasMaterials.idf`, `WindowConstructs.idf` | The EnergyPlus licence (the files carry no notice of their own) | Keep [`licenses/EnergyPlus-LICENSE.txt`](licenses/EnergyPlus-LICENSE.txt) with them |
| **EnergyPlusToFMU** v3.1.0 (cloned into the `eptofmu` image) and the FMUs it generates (`backend/seed_sessions/bdopt-demo/state/field/*.fmu`) | Modified 3-clause BSD, Copyright (c) 2021 The Regents of the University of California, LBNL ([text](licenses/EnergyPlusToFMU-LICENSE.txt)); the FMU wrapper also contains QTronic FmuSdk (BSD, Copyright 2008-2011 QTronic GmbH) and MODELISAR headers (BSD-3-clause); Expat (MIT) is part of its source, but whether it is linked into a given FMU was not verified | Reproduce the notices when FMUs are redistributed as binaries |
| **IDF models** `tutorials/test.idf` (and its copies in the demo seed) and `tests/fixtures/platform/*.idf` | Most are generated with DesignBuilder (5.5.0 and 7.0.2, from the course's model folder, per the file headers); `lab_building.idf` and `E1_RES1.idf` have no header | Credit of the model authors: to be completed by the authors of the course |

Citation of EnergyPlus: Crawley, D.B., Lawrie, L.K., Winkelmann, F.C., Buhl, W.F., Huang, Y.J., Pedersen, C.O., Strand, R.K.,
Liesen, R.J., Fisher, D.E., Witte, M.J., Glazer, J. (2001). EnergyPlus: creating a new-generation building energy simulation
program. *Energy and Buildings* 33(4), 319-331. <https://doi.org/10.1016/S0378-7788(00)00114-6>.
(No citation request was found in the EnergyPlus repository; the energyplus.net pages could not be read. This is the paper its users conventionally cite.)

## 4. Teaching material

- **The four tutorial notebooks** (`tutorials/`, and the copy inside the demo session) are adapted from the course notebooks, which
  were written for **BESOS**. BESOS (<https://gitlab.com/energyincities/besos>) and its example notebooks
  (<https://gitlab.com/energyincities/besos-examples>) are **GPL-3.0**; `docs/conf.py` has "copyright = 2020, Ralph Evins". The
  GPL requires a work adapted from BESOS material, when conveyed, to carry a notice that it was modified (with date), the BESOS
  copyright and licence notice, and to be licensed as a whole under the GPL. Each notebook says in its last cell that it was
  rewritten in October 2026 for bdopt. **Which of the notebooks' text and code is copied from BESOS has not been established**
  (see `docs/licence_audit.md`).
- **Figures.** `setting_up_the_evaluator.PNG` is byte-identical to the BESOS documentation file (GPL-3.0); `flow_diagram.PNG` is
  the BESOS file with the toolbox names changed. `surrogate_overview.png` and `LOLA-Voronoi.jpg` come from the course notebooks;
  neither is in the BESOS repositories and their original source has not been found. A line under each figure says where it comes from.
- **bdopt** — MIT, <https://github.com/LorenzoBottaccioli/bdopt>.
- Citation of BESOS: Westermann, P., Christiaanse, T.V., Beckett, W., Kovacs, P., Evins, R. (2021). besos: Building and Energy
  Simulation, Optimization and Surrogate Modelling. *Journal of Open Source Software* 6(60), 2677.
  <https://doi.org/10.21105/joss.02677>.

### References for the methods used in the tutorials

- Latin hypercube — McKay, Beckman, Conover (1979), *Technometrics* 21(2), 239-245, <https://doi.org/10.1080/00401706.1979.10489755>.
- Sobol' indices — Sobol' (2001), *Mathematics and Computers in Simulation* 55(1-3), 271-280, <https://doi.org/10.1016/S0378-4754(00)00270-6>;
  estimators: Saltelli (2002), *Computer Physics Communications* 145(2), 280-297, <https://doi.org/10.1016/S0010-4655(02)00280-1>.
- Gaussian-process surrogate — Rasmussen & Williams (2006), *Gaussian Processes for Machine Learning*, MIT Press, ISBN 0-262-18253-X.
- Surrogate modelling in building design — Westermann & Evins (2019), *Energy and Buildings* 198, 170-186, <https://doi.org/10.1016/j.enbuild.2019.05.057>.
- NSGA-II — Deb, Pratap, Agarwal, Meyarivan (2002), *IEEE Trans. Evolutionary Computation* 6(2), 182-197, <https://doi.org/10.1109/4235.996017>.
- LOLA-Voronoi — Crombecq, Gorissen, Deschrijver, Dhaene (2011), *SIAM J. Sci. Comput.* 33(4), 1948-1974, <https://doi.org/10.1137/090761811>;
  fuzzy version: van der Herten, Couckuyt, Deschrijver, Dhaene (2015), *SIAM J. Sci. Comput.* 37(2), A1020-A1039, <https://doi.org/10.1137/140962437>;
  in building design: Westermann & Evins (2019), *Proceedings of Building Simulation 2019*, <https://doi.org/10.26868/25222708.2019.211232>.
- Thermal comfort (PMV/PPD, in the Model editor) — Fanger, P.O. (1970), *Thermal Comfort*, Danish Technical Press, Copenhagen
  (from library catalogues, not from the publisher); ISO 7730 (the 2005 edition is historical; 2025 edition exists, not read).

## 5. Software run unmodified in containers

| Component | Licence |
| --- | --- |
| Eclipse Mosquitto 2.0 | EPL-2.0 OR EDL-1.0 (BSD-3-Clause) |
| InfluxDB 1.11 | MIT (Copyright (c) 2013-2018 InfluxData Inc) |
| Grafana 12.0.0 | AGPL-3.0 (parts Apache-2.0). Unmodified and not offered as a modified service: no source obligation |
| openHAB 4.3.5 | EPL-2.0 ([text](licenses/openHAB-LICENSE-EPL-2.0.txt)). `openhab/conf/sounds/*.mp3`, `transform/*.map`, `html/index.html` and `html/readme.txt` are byte-identical to the openHAB 4.3.5 distribution files and are redistributed here under it. `services/*.cfg`, the items, sitemap and things are the platform's own |
| Home Assistant 2026.10.1 | Apache-2.0 |
| Jupyter docker-stacks | BSD-3-Clause |

## 6. Libraries

Licences read from the installed packages of the three images and from each project's repository. Notable ones:

- **LGPL-3.0**: PyFMI, Assimulo (the FMU co-simulation); moocore (LGPL-2.1+, used by pymoo). Used as unmodified libraries; if an image
  containing them is ever redistributed, ship their licence text.
- **MPL-2.0**: certifi, tqdm, fqdn; eppy's `epconversions.py` (eppy 0.6.7; the backend pins 0.5.63, MIT only).
- **GPL-3.0**: BESOS, only when the BESOS engine is chosen (`SURROGATE_ENGINE=BESOS`); not in the unified image.
- **MIT, BSD, Apache-2.0, ISC and similar**: everything else — eppy, geomeppy, pyepw (Apache-2.0), Flask and its extensions,
  SQLAlchemy, paho-mqtt (EPL-2.0 OR BSD-3-Clause; the BSD option applies), influxdb-client, scikit-learn, pymoo (Apache-2.0),
  stable-baselines3, gymnasium, gym, plotly, ipywidgets, FMPy (BSD-2-Clause), torch (BSD-style); React, React-Bootstrap, Bootstrap,
  axios, React Router (MIT), lucide-react (ISC, some icons MIT), react-activation (ISC).

Requested citations: scikit-learn — Pedregosa et al. (2011), *JMLR* 12, 2825-2830. pymoo — Blank & Deb (2020), *IEEE Access* 8,
89497-89509, <https://doi.org/10.1109/ACCESS.2020.2990567>. Stable-Baselines3 — Raffin et al. (2021), *JMLR* 22(268), 1-8.
PyFMI — Andersson, C., Akesson, J. & Fuhrer, C. (2016), *PyFMI: A Python Package for Simulation of Coupled Dynamic Models with the Functional
Mock-up Interface*, Lund University Technical Report in Mathematical Sciences 2016(2). GeomEppy — Bull J, et al. GeomEppy, 2016-,
<https://github.com/jamiebull1/geomeppy>.

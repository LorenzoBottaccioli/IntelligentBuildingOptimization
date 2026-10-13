// Credits & licences: what the platform is built on, under which terms, how to credit it.
// The complete text, with every reference, is NOTICE.md in the repository; this page is the summary the students see.
import React from 'react';
import './Credits.css';

const ext = (href, text) => <a href={href} target="_blank" rel="noreferrer">{text}</a>;

const WEATHER = [
  [ext('https://open-meteo.com/', 'Open-Meteo'), 'CC BY 4.0; the free API is for non-commercial use',
    'Weather data by Open-Meteo.com. Converted to EPW here (changes made).'],
  ['ERA5, ERA5-Land, CERRA, ECMWF IFS (behind Open-Meteo and PVGIS)', 'CC BY',
    'Contains modified Copernicus Climate Change Service information. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.'],
  [ext('https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en', 'PVGIS'),
    'Free for public use if the source is acknowledged', 'PVGIS © European Communities, 2001-2026.'],
  [ext('https://energyplus.net/weather/sources', 'EnergyPlus weather list'), 'Terms differ for each source',
    'Each file keeps the copyright line of its source in its header. IWEC files are © ASHRAE, licensed for your own use; they must not be passed on without ASHRAE’s permission.'],
  [ext('https://climate.onebuilding.org/', 'Climate.OneBuilding.org'), 'All rights reserved; no licence stated',
    'Lawrie, L.K., Crawley, D.B. 2026. Development of Global Typical Meteorological Years (TMYx). climate.onebuilding.org'],
];

const TOOLS = [
  ['EnergyPlus version 9.6', 'BSD-style licence (University of Illinois, UC / Lawrence Berkeley National Laboratory, Oak Ridge National Laboratory, Alliance for Energy Innovation and other contributors)',
    'Crawley et al. (2001), Energy and Buildings 33(4), 319-331. doi:10.1016/S0378-7788(00)00114-6'],
  ['EnergyPlusToFMU 3.1.0', 'Modified 3-clause BSD (The Regents of the University of California, Lawrence Berkeley National Laboratory)', ''],
  ['BESOS', 'GPL-3.0 (Ralph Evins and the BESOS authors). The course and the tutorials were written for it',
    'Westermann et al. (2021), Journal of Open Source Software 6(60), 2677. doi:10.21105/joss.02677'],
  ['bdopt', 'MIT', ''],
  ['openHAB, Eclipse Mosquitto', 'EPL-2.0 (Mosquitto also EDL-1.0)', ''],
  ['Grafana 12, InfluxDB 1.11, Home Assistant', 'AGPL-3.0, MIT, Apache-2.0: run unmodified in their own containers', ''],
  ['PyFMI, Assimulo, pymoo, scikit-learn, Stable-Baselines3, Gymnasium, eppy, pyepw, Flask, React and the rest',
    'LGPL-3.0 (PyFMI, Assimulo), Apache-2.0 (pymoo, pyepw), BSD-3 (scikit-learn), MIT (the others)',
    'Cite scikit-learn (Pedregosa et al. 2011), pymoo (Blank & Deb 2020) and Stable-Baselines3 (Raffin et al. 2021) when you use them in a report.'],
];

export default function Credits() {
  return (
    <div className="cr">
      <header className="cr-bar">
        <h1>Credits &amp; licences</h1>
        <p>
          The platform is built on the work of others. This page says what, under which terms, and how to credit it in a report.
          The full list, with every reference and the text of the licences that must travel with the files, is
          <code> NOTICE.md</code> and the folder <code>licenses/</code> of the repository.
        </p>
      </header>

      <section className="cr-card">
        <h2>The platform</h2>
        <p>
          Smart Building Educational Platform, Politecnico di Torino. Lorenzo Bottaccioli. The first version was documented by
          Andres Orellana (July 2025).
        </p>
        <p className="cr-note">The licence of the platform’s own code has not been declared yet.</p>
      </section>

      <section className="cr-card">
        <h2>Weather data</h2>
        <div className="cr-scroll">
          <table className="cr-table">
            <thead><tr><th>Source</th><th>Terms</th><th>Credit to give</th></tr></thead>
            <tbody>
              {WEATHER.map(([a, b, c], i) => <tr key={i}><td>{a}</td><td>{b}</td><td>{c}</td></tr>)}
            </tbody>
          </table>
        </div>
        <p className="cr-note">
          A weather file made or edited here keeps the source and the changes in its header (COMMENTS 1 and 2): keep them if you
          pass the file on. If you publish results, say which file you used and cite the dataset: ERA5, doi:10.24381/cds.adbb2d47;
          Open-Meteo (Zippenfenig 2023), doi:10.5281/ZENODO.7970649.
        </p>
      </section>

      <section className="cr-card">
        <h2>Software and teaching material</h2>
        <div className="cr-scroll">
          <table className="cr-table">
            <thead><tr><th>Component</th><th>Licence</th><th>Citation</th></tr></thead>
            <tbody>
              {TOOLS.map(([a, b, c], i) => <tr key={i}><td>{a}</td><td>{b}</td><td>{c}</td></tr>)}
            </tbody>
          </table>
        </div>
        <p className="cr-note">
          The four tutorial notebooks are adapted from the course notebooks written for BESOS; two of their figures come from the
          BESOS documentation. Each notebook ends with its sources and references (methods: Latin hypercube, Sobol’ indices,
          Gaussian processes, NSGA-II, LOLA-Voronoi). The building models of the examples were made with DesignBuilder.
        </p>
      </section>
    </div>
  );
}

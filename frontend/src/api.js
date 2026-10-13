// Single place where the backend lives, so the host is not hardcoded in every component.
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? `http://${window.location.hostname}:5000`;

export const SERVICES = {
  // Jupyter of the surrogate stage (root of backend/surrogate_notebooks: the problem notebook and tutorials/).
  surrogateJupyter: `http://${window.location.hostname}:8889`,
  surrogateNotebook: `http://${window.location.hostname}:8889/notebooks/SurrogateNotebook.ipynb`,
  // Root of the Jupyter that edits the students' Workspace/ (devices/, iot/, ai/, logs/).
  workspaceJupyter: `http://${window.location.hostname}:8892`,
  grafana: `http://${window.location.hostname}:3000`,
  // openHAB main UI: the Overview page is the demo page in the demo, empty in a new project.
  openhab: `http://${window.location.hostname}:8080/`,
  // Home Assistant: the project's own dashboard (the demo one in the demo, empty in a new project). The root of
  // this Home Assistant opens its automatic Home page (/home/overview), which knows nothing of the project.
  homeassistant: `http://${window.location.hostname}:8123/lovelace/`,
};

export const api = (path) => `${API_BASE}${path}`;

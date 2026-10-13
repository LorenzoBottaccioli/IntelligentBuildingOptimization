// How the Sensors & actuators page divides what EnergyPlus offers, as plain functions.
//
// The rule is "which type -> which one -> where": the type comes from what EnergyPlus declares (the
// units of a report variable, the units and control type of an actuator, the resource tokens of a
// meter name), never from a word list for one building. Every table below was checked against the
// dictionaries of 628 EnergyPlus 9.6 example models (tests/instrumentation/measure_dictionaries.py)
// and the functions against a sample of them (tests/instrumentation/instrument_groups.test.mjs).
//
// Kept apart from outputGroups.js, which the Outputs tab of the Model editor owns.

// ---- sensors: the quantity comes from the unit ----------------------------------

export const QUANTITIES = [
  ['temperature', 'Temperature'],
  ['power', 'Power and energy'],
  ['flow', 'Flow and speed'],
  ['humidity', 'Humidity and CO2'],
  ['light', 'Light'],
  ['time', 'Time and angle'],
  ['mass', 'Mass, volume, pressure'],
  ['coefficient', 'Coefficients'],
  ['electrical', 'Electrical'],
  ['status', 'Status and counts'],
];

// Unit strings of the .rdd (OutputProcessor::Unit of EnergyPlus 9.6, 50 strings seen in 628 models).
const QUANTITY_OF_UNIT = {};
[
  ['temperature', ['C', 'deltaC']],
  ['power', ['W', 'J', 'W/m2', 'J/m2']],
  ['flow', ['m3/s', 'kg/s', 'kgWater/s', 'kmol/s', 'ach', 'kg/m2-s', 'm/s', 'rev/min']],
  ['humidity', ['kgWater/kgDryAir', '%', 'ppm', 'kg/kg']],
  ['light', ['lux', 'cd/m2', 'lum/W']],
  ['time', ['hr', 'min', 's', 'deg', 'rad']],
  ['mass', ['m3', 'kg', 'L', 'Pa', 'kg/m3', 'm', 'm2']],
  ['coefficient', ['W/m2-K', 'W/K', 'W/W', 'J/kg', 'J/kg-K', 'W/m-K', 'K/m', 'clo', 'J/kgWater', 'K/W', 'W/m2-C', 'Btu/h-W']],
  ['electrical', ['A', 'V', 'Ah']],
  ['status', ['', 'ON/OFF']],
].forEach(([q, units]) => units.forEach((u) => { QUANTITY_OF_UNIT[u] = q; }));

/** The quantity of a report variable from its unit; 'other' for a unit not in the table. */
export function quantityOfUnit(units) {
  return QUANTITY_OF_UNIT[String(units ?? '').trim()] || 'other';
}

/**
 * One row per quantity: "X Rate [W]" and "X Energy [J]" (and "X Rate per Area [W/m2]") share a row.
 * "Rate" is also the suffix of flows (m3/s, kg/s) and of air changes, so only W, J and W/m2 pair.
 */
export function pairKey(name, units) {
  if (units === 'W' && name.endsWith(' Rate')) return name.slice(0, -' Rate'.length);
  if (units === 'J' && name.endsWith(' Energy')) return name.slice(0, -' Energy'.length);
  if (units === 'W/m2' && name.endsWith(' Rate per Area')) return name.slice(0, -' Rate per Area'.length);
  return name;
}

/** Report variables ({variableName, units, keys}) -> rows with their unit variants, in the order met. */
export function sensorRows(variables) {
  const rows = new Map();
  variables.forEach((v) => {
    const id = pairKey(v.variableName, v.units ?? '');
    let row = rows.get(id);
    if (!row) {
      row = { id, title: id, variants: [], keys: [], quantity: quantityOfUnit(v.units) };
      rows.set(id, row);
    }
    row.variants.push({ id: v.variableName, units: v.units ?? '' });
    (v.keys || []).forEach((k) => { if (!row.keys.includes(k)) row.keys.push(k); });
  });
  return [...rows.values()];
}

// ---- a long list becomes headers by common prefix, only above a limit --------------

export const LIST_LIMIT = 40;
const TINY = 2;

/**
 * Split items by the words of their title until every group has at most `limit` items.
 * Returns nodes: {title, count, items} for a short group, {title, count, children} for a header.
 * A level where every item shares the word adds no header: the prefix just grows.
 */
export function splitByPrefix(items, titleOf = (x) => x.title, limit = LIST_LIMIT) {
  const words = (it) => titleOf(it).split(/\s+/);
  const walk = (list, depth, prefix) => {
    if (list.length <= limit || depth > 10) return [{ title: prefix, count: list.length, items: list }];
    const groups = new Map();
    list.forEach((it) => {
      const w = words(it)[depth - 1] ?? '';
      if (!groups.has(w)) groups.set(w, []);
      groups.get(w).push(it);
    });
    if (groups.size === 1) return walk(list, depth + 1, prefix);
    const out = [];
    const tiny = [];
    [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).forEach(([w, g]) => {
      const title = `${prefix} ${w}`.trim();
      if (g.length <= TINY && w !== '') tiny.push(...g);
      else if (g.length <= limit) out.push({ title, count: g.length, items: g });
      else out.push({ title, count: g.length, children: walk(g, depth + 1, title) });
    });
    // One or two items under their own header are clutter: they share a group, as long as it stays short.
    if (tiny.length > 0 && tiny.length <= limit) out.push({ title: `${prefix} (other)`.trim(), count: tiny.length, items: tiny });
    else tiny.length && out.push({ title: `${prefix} (other)`.trim(), count: tiny.length, children: walk(tiny, depth + 1, `${prefix} (other)`.trim()) });
    return out;
  };
  const nodes = walk([...items].sort((a, b) => titleOf(a).localeCompare(titleOf(b))), 1, '');
  // A single short group needs no header at all.
  return nodes;
}

/** The short groups of a tree, in order. */
export function leavesOf(nodes) {
  return nodes.flatMap((n) => (n.children ? leavesOf(n.children) : [n]));
}

// ---- meters: resource and end use are the tokens of the IDD -----------------------

// EnergyManagementSystem:MeteredOutputVariable "Resource Type", Meter:Custom "Resource Type" and
// LifeCycleCost:UsePriceEscalation "Resource" of the 9.6 IDD (29 keys), and its "End-Use Category" (21).
export const RESOURCES = new Set([
  'Electricity', 'NaturalGas', 'Gasoline', 'Diesel', 'Coal', 'FuelOilNo1', 'FuelOilNo2', 'Propane', 'OtherFuel1',
  'OtherFuel2', 'WaterUse', 'OnSiteWaterProduced', 'MainsWaterSupply', 'RainWaterCollected', 'WellWaterDrawn',
  'CondensateWaterCollected', 'EnergyTransfer', 'Steam', 'DistrictCooling', 'DistrictHeating',
  'ElectricityProducedOnSite', 'SolarWaterHeating', 'SolarAirHeating', 'Water', 'Generic', 'ElectricityPurchased',
  'ElectricityProduced', 'ElectricitySurplusSold', 'ElectricityNet',
  // Not in those IDD lists, yet in the .mdd of 624 of 628 example models (MainsWater:Facility, MainsWater:HVAC).
  'MainsWater',
]);
export const END_USES = new Set([
  'Heating', 'Cooling', 'InteriorLights', 'ExteriorLights', 'InteriorEquipment', 'ExteriorEquipment', 'Fans', 'Pumps',
  'HeatRejection', 'Humidifier', 'HeatRecovery', 'WaterSystems', 'Refrigeration', 'OnSiteGeneration', 'HeatingCoils',
  'CoolingCoils', 'Chillers', 'Boilers', 'Baseboard', 'HeatRecoveryForCooling', 'HeatRecoveryForHeating',
]);
const PLAIN_SCOPES = new Set(['Facility', 'Building', 'HVAC', 'Plant', 'System']);

/**
 * `[Subcategory:]EndUse:Resource[:Zone:x | :SpaceType:x]` or `Resource:(Facility|Building|Plant|HVAC)`,
 * the two forms of 79 218 meters in 628 models. Names that hold neither token (emissions, PlantLoop...Demand,
 * Carbon Equivalent, meters of the user) keep their first token as family and the rest as they are.
 */
export function meterParts(name) {
  const parts = name.split(':');
  const iRes = parts.findIndex((p) => RESOURCES.has(p));
  const iEnd = parts.findIndex((p) => END_USES.has(p));
  let scopeAt = parts.findIndex((p, i) => (p === 'Zone' || p === 'SpaceType') && i > 0 && i < parts.length - 1);
  if (scopeAt < 0) scopeAt = parts.findIndex((p) => PLAIN_SCOPES.has(p));
  const scope = scopeAt < 0 ? { type: '', name: '' }
    : PLAIN_SCOPES.has(parts[scopeAt]) ? { type: parts[scopeAt], name: '' }
      : { type: parts[scopeAt], name: parts.slice(scopeAt + 1).join(':') };
  const end = scopeAt < 0 ? parts.length : scopeAt;
  const resource = iRes >= 0 ? parts[iRes] : '';
  const endUse = iEnd >= 0 ? parts[iEnd] : '';
  const prefix = endUse && iEnd > 0 ? parts.slice(0, iEnd).join(':') : '';
  const row = parts.slice(0, end).join(':') || name;
  return { resource, endUse, prefix, scope, row };
}

/** The family a meter belongs to for the type filter. */
export function meterFamily(parts) {
  if (parts.resource) return parts.resource;
  const head = parts.row.split(':')[0];
  if (/emissions$/i.test(head) || /^carbon/i.test(head) || /^(Source|CO2|CO|NOx|SO2|PM|PM10|PM2.5|NH3|NMVOC|Hg|Pb|N2O|CH4)$/i.test(head)) return 'Emissions';
  if (/^PlantLoop/i.test(head)) return 'Plant loop demand';
  return 'Other';
}

// ---- actuators: the unit of the EDD, the control type where the unit does not decide ----

export const ACTUATOR_KINDS = [
  ['setpoint', 'Temperature setpoints'],
  ['temperature', 'Temperature'],
  ['flow', 'Flow'],
  ['humidity', 'Humidity'],
  ['power', 'Power and people'],
  ['weather', 'Weather and wind'],
  ['surface', 'Surfaces and materials'],
  ['schedule', 'Schedules'],
  ['status', 'Status and fractions'],
  ['other', 'Other'],
];

/**
 * The kind of an actuator action from its EDD unit; the control type decides only where the unit is
 * blank or unknown (Schedule Value, absorptances, Construction State, View Factor To Ground,
 * Availability Status, Curve Result: the 12 combinations found in 628 models).
 */
export function actuatorKind(type, control, units) {
  const u = String(units ?? '').trim();
  const c = String(control ?? '');
  const t = String(type ?? '');
  if (/^schedule/i.test(t) || /^schedule value$/i.test(c)) return 'schedule';
  if (/outdoor air (drybulb|wetbulb|wind)|outdoor (dry bulb|dew point|relative humidity)|^(drybulb|wetbulb) temperature|^wind (speed|direction)|diffuse solar|direct solar/i.test(c)
    || /^weather data$/i.test(t)) return 'weather';
  if (u === 'C') return /setpoint/i.test(c) ? 'setpoint' : 'temperature';
  if (u === 'm/s' || u === 'deg' || u === 'degree' || u === 'degrees') return 'weather';
  if (u === 'kg/s' || u === 'm3/s') return 'flow';
  if (u === 'kgWater/kgDryAir' || u === '%') return 'humidity';
  if (u === 'W' || u === 'W/m2' || u === 'each') return 'power';
  if (u === 'W/m2-K' || u === 'W/m-K' || u === 'J/kg-C' || /absorptance|view factor|construction state/i.test(c)) return 'surface';
  if (['fraction', 'Fraction', 'on/off', 'integer', 'ShadeStatus'].includes(u) || /availability status|control status/i.test(c)) return 'status';
  return 'other';
}

/** Component types such as "Plant Component Boiler:HotWater" share a family: the list stays one entry. */
export function actuatorFamily(type) {
  return /^Plant Component /.test(type) ? 'Plant Component' : type;
}

// ---- schedules: by what they drive -----------------------------------------------

export const SCHEDULE_KINDS = [
  ['setpoints', 'Setpoints'],
  ['loads', 'Occupancy and loads'],
  ['hvac', 'HVAC'],
  ['envelope', 'Ventilation and shading'],
  ['other', 'Other'],
  ['unused', 'Not used'],
];

export function scheduleKind(sch) {
  const classes = (sch.users || []).map((u) => u.class);
  if (!classes.length) return 'unused';
  const any = (re) => classes.some((c) => re.test(c));
  if (any(/^(ThermostatSetpoint|ZoneControl:(Thermostat|Humidistat))/i)) return 'setpoints';
  if (any(/^(People|Lights|ElectricEquipment|GasEquipment|HotWaterEquipment|SteamEquipment|OtherEquipment|WaterUse)/i)) return 'loads';
  if (any(/^(ZoneVentilation|ZoneInfiltration|ZoneMixing|ZoneCrossMixing|WindowShadingControl|AirflowNetwork|ZoneCooltower|ZoneEarthtube)/i)) return 'envelope';
  if (any(/(Availability|AirLoop|ZoneHVAC|Fan|Pump|Coil|Plant|Controller|Branch|Humidifier|Chiller|Boiler|Tower|Heater|OutdoorAir|Setpoint)/i)) return 'hvac';
  return 'other';
}

// ---- where: the zones a choice applies to ---------------------------------------

/** The zones an option (a key, a component, a meter scope) belongs to: itself, or what the IDD says owns it. */
export function zonesOfOption(label, owners) {
  return (owners || {})[String(label).toUpperCase()] || [];
}

/**
 * The options a row starts with: those of the zones in scope. With no zone information a single option
 * is taken, several are left to choose.
 */
export function defaultSelection(options, scope, owners) {
  const inScope = new Set([...scope].map((z) => String(z).toUpperCase()));
  const owned = options.filter((o) => zonesOfOption(o.label, owners).length > 0);
  if (owned.length === 0) return options.length === 1 ? [options[0].id] : [];
  return owned
    .filter((o) => zonesOfOption(o.label, owners).some((z) => inScope.has(String(z).toUpperCase())))
    .map((o) => o.id);
}

// ---- names ---------------------------------------------------------------------

/** Turn a label into an Erl/FMU-safe identifier, mirroring the backend rule. */
export function toIdentifier(raw) {
  const cleaned = (raw || '')
    .trim()
    .replace(/[^0-9a-zA-Z_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
  if (!cleaned) return '';
  return /^\d/.test(cleaned) ? `v_${cleaned}` : cleaned;
}

export const shortKey = (key) => (key && key !== 'Environment' ? key.split(':').pop() : '');

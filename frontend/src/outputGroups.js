// Groups of report variables and meters, by EnergyPlus naming conventions. Shared by the
// Sensors & actuators page and the Model editor's Outputs tab.

const METER_GROUPS = [
  ['building', 'Whole building', 'Totals for the facility, one value per fuel or end use.'],
  ['enduse', 'By end use', 'Heating, cooling, lights, equipment, fans... summed over the building.'],
  ['zone', 'By zone', 'The same end uses, zone by zone.'],
];

function meterGroup(name) {
  if (/:Zone:/i.test(name)) return 'zone';
  if (/:(Facility|Building)$/i.test(name)) return 'building';
  return 'enduse';
}

const SENSOR_GROUPS = [
  ['zone', 'Zone conditions', 'Temperatures, humidity, CO2, comfort and loads of each zone or space.'],
  ['outdoor', 'Outdoor and site', 'Weather and site conditions.'],
  ['surface', 'Surfaces and windows', 'Surface temperatures, heat flows, solar through windows, shading status.'],
  ['loads', 'Occupants and internal loads', 'People, lights, equipment, infiltration objects.'],
  ['hvac', 'HVAC and plant', 'Nodes, air loops, ideal loads, plant and equipment.'],
  ['schedule', 'Schedules', 'The current value of any schedule.'],
  ['other', 'Other', 'Variables that fit none of the groups above.'],
];

function sensorGroup(v) {
  const n = v.variableName;
  if (/^(Site|Environmental)\b/i.test(n)) return 'outdoor';
  if (/^Schedule\b/i.test(n)) return 'schedule';
  if (/^(Surface|Daylighting|Window)\b/i.test(n)) return 'surface';
  if (/^(People|Lights|Exterior Lights|Electric Equipment|Gas Equipment|Hot Water Equipment|Steam Equipment|Other Equipment|Infiltration|Ventilation)\b/i.test(n)) return 'loads';
  if (/^Zone (Ideal Loads|Air Terminal|Packaged|Unitary|Window Air Conditioner|Baseboard|Radiant|Four Pipe|Water to Air|VRF|Evaporative)/i.test(n)) return 'hvac';
  if (/^(Zone|Space)\b/i.test(n)) return 'zone';
  if (/^(System|Air System|Plant|HVAC|Facility|Fan|Pump|Cooling Coil|Heating Coil|Chiller|Boiler|Cooling Tower|Water Heater|Baseboard|Unitary|Air Terminal)\b/i.test(n) || v.varType === 'HVAC') return 'hvac';
  return 'other';
}

export { METER_GROUPS, meterGroup, SENSOR_GROUPS, sensorGroup };

// Run from the repository root:  node --test tests/instrumentation/instrument_groups.test.mjs
// The functions of frontend/src/instrumentGroups.js against real dictionaries: tests/fixtures/dictionaries/sample.json.gz
// (84 of the 628 EnergyPlus 9.6 example models; see measure_dictionaries.py for how they are made).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import {
  QUANTITIES, quantityOfUnit, pairKey, sensorRows, splitByPrefix, leavesOf, meterParts, meterFamily,
  actuatorKind, actuatorFamily, scheduleKind, defaultSelection, toIdentifier, shortKey,
} from '../../frontend/src/instrumentGroups.js';

const corpus = JSON.parse(gunzipSync(readFileSync(new URL('../fixtures/dictionaries/sample.json.gz', import.meta.url))).toString('utf8'));
const models = Object.entries(corpus);
const median = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
const variablesOf = (m) => m.rdd.filter(([, rt]) => rt !== 'Meter').map(([, , name, units]) => ({ variableName: name, units, keys: [] }));

test('every unit of every report variable has a quantity', () => {
  const unknown = new Set();
  models.forEach(([, m]) => variablesOf(m).forEach((v) => { if (quantityOfUnit(v.units) === 'other') unknown.add(v.units); }));
  assert.deepEqual([...unknown], []);
  assert.equal(new Set(QUANTITIES.map(([id]) => id)).size, QUANTITIES.length);
});

test('only W, J and W/m2 variables pair; flows named Rate stay alone', () => {
  assert.equal(pairKey('Zone Lights Total Heating Rate', 'W'), 'Zone Lights Total Heating');
  assert.equal(pairKey('Zone Lights Total Heating Energy', 'J'), 'Zone Lights Total Heating');
  assert.equal(pairKey('Site Direct Solar Radiation Rate per Area', 'W/m2'), 'Site Direct Solar Radiation');
  assert.equal(pairKey('Zone Mechanical Ventilation Air Changes per Hour', 'ach'), 'Zone Mechanical Ventilation Air Changes per Hour');
  assert.equal(pairKey('System Node Mass Flow Rate', 'kg/s'), 'System Node Mass Flow Rate');
  assert.equal(pairKey('Surface Window Transmitted Solar Radiation Rate', 'W'), 'Surface Window Transmitted Solar Radiation');
});

test('rows join the unit variants of one quantity and never mix quantities', () => {
  const vars = variablesOf(corpus['5ZoneAirCooled']);
  const rows = sensorRows(vars);
  assert.ok(rows.length < vars.length);
  assert.equal(rows.reduce((n, r) => n + r.variants.length, 0), vars.length);
  rows.forEach((r) => assert.equal(new Set(r.variants.map((x) => quantityOfUnit(x.units))).size, 1, r.id));
  const pair = rows.find((r) => r.id === 'Zone Lights Total Heating');
  assert.deepEqual(pair.variants.map((x) => x.units).sort(), ['J', 'W']);
});

test('the prefix split keeps every list within the limit, with few header levels', () => {
  const leafCounts = [];
  let largest = 0;
  let depth = 0;
  const levels = (nodes, d = 1) => nodes.forEach((n) => { depth = Math.max(depth, d); if (n.children) levels(n.children, d + 1); });
  models.forEach(([, m]) => {
    const byQuantity = new Map();
    sensorRows(variablesOf(m)).forEach((r) => {
      if (!byQuantity.has(r.quantity)) byQuantity.set(r.quantity, []);
      byQuantity.get(r.quantity).push(r);
    });
    let leaves = 0;
    byQuantity.forEach((rows) => {
      const tree = splitByPrefix(rows);
      levels(tree);
      leavesOf(tree).forEach((l) => { largest = Math.max(largest, l.items.length); leaves += 1; assert.equal(l.count, l.items.length); });
      assert.equal(leavesOf(tree).reduce((n, l) => n + l.items.length, 0), rows.length);
    });
    leafCounts.push(leaves);
  });
  assert.ok(largest <= 40, `largest list ${largest}`);
  assert.ok(depth <= 4, `header levels ${depth}`);
  // measure_dictionaries.py with limit 40 gave a median of 69 lists per model on the 628 models.
  assert.ok(median(leafCounts) >= 50 && median(leafCounts) <= 90, `median lists ${median(leafCounts)}`);
});

test('meter names split into subcategory, end use, resource and scope', () => {
  const p = (n) => meterParts(n);
  assert.deepEqual(p('Electricity:Facility'), {
    resource: 'Electricity', endUse: '', prefix: '', scope: { type: 'Facility', name: '' }, row: 'Electricity',
  });
  const z = p('Cooling:EnergyTransfer:Zone:BLOCK1B:ROOM');
  assert.equal(z.endUse, 'Cooling');
  assert.equal(z.resource, 'EnergyTransfer');
  assert.deepEqual(z.scope, { type: 'Zone', name: 'BLOCK1B:ROOM' });
  assert.equal(z.row, 'Cooling:EnergyTransfer');
  assert.deepEqual(p('Electricity:SpaceType:GENERAL').scope, { type: 'SpaceType', name: 'GENERAL' });
  const e = p('ELECTRIC EQUIPMENT#Block1B:Room#05:InteriorEquipment:Electricity:Zone:BLOCK1B:ROOM');
  assert.equal(e.prefix, 'ELECTRIC EQUIPMENT#Block1B:Room#05');
  assert.equal(e.endUse, 'InteriorEquipment');
  assert.equal(e.resource, 'Electricity');
  assert.equal(e.scope.name, 'BLOCK1B:ROOM');
  assert.equal(meterFamily(p('Carbon Equivalent:Facility')), 'Emissions');
  assert.equal(meterFamily(p('NaturalGasEmissions:CO2')), 'Emissions');
  assert.equal(meterFamily(p('PlantLoopHeatingDemand:Plant')), 'Plant loop demand');
  assert.equal(meterFamily(p('DistrictHeating:Facility')), 'DistrictHeating');
});

test('every meter of the corpus is rebuilt from its parts, and almost all have a family', () => {
  let total = 0;
  let other = 0;
  models.forEach(([name, m]) => m.mdd.forEach(([, , meter]) => {
    const parts = meterParts(meter);
    const scope = parts.scope.type ? `:${parts.scope.type}${parts.scope.name ? `:${parts.scope.name}` : ''}` : '';
    assert.equal(parts.row + scope, meter, `${name}: ${meter}`);
    total += 1;
    if (meterFamily(parts) === 'Other') other += 1;
  }));
  assert.ok(total > 5000);
  assert.ok(other / total < 0.05, `${other} of ${total} meters in Other`);
});

test('actuator kinds follow the unit, and the control type where the unit is blank', () => {
  const k = actuatorKind;
  assert.equal(k('Zone Temperature Control', 'Heating Setpoint', 'C'), 'setpoint');
  assert.equal(k('System Node Setpoint', 'Temperature Setpoint', 'C'), 'setpoint');
  assert.equal(k('System Node Setpoint', 'Mass Flow Rate Setpoint', 'kg/s'), 'flow');
  assert.equal(k('Schedule:Compact', 'Schedule Value', ''), 'schedule');
  assert.equal(k('Material', 'Surface Property Solar Absorptance', ''), 'surface');
  assert.equal(k('Surface', 'Construction State', ''), 'surface');
  assert.equal(k('Surface', 'Outdoor Air Wind Speed', 'm/s'), 'weather');
  assert.equal(k('Weather Data', 'Outdoor Dry Bulb', 'C'), 'weather');
  assert.equal(k('Plant Component Pump:VariableSpeed', 'On/Off Supervisory', 'fraction'), 'status');
  assert.equal(k('People', 'Number of People', 'each'), 'power');
  assert.equal(k('Lights', 'Electricity Rate', 'W'), 'power');
  assert.equal(actuatorFamily('Plant Component Boiler:HotWater'), 'Plant Component');
  assert.equal(actuatorFamily('Zone'), 'Zone');
});

test('few actuator actions of the corpus end up in Other', () => {
  const seen = new Map();
  models.forEach(([, m]) => m.edd.forEach(([, type, control, units]) => seen.set(`${type}|${control}|${units}`, [type, control, units])));
  const other = [...seen.values()].filter(([t, c, u]) => actuatorKind(t, c, u) === 'other');
  console.log(`actions in Other: ${other.length} of ${seen.size}`, other.slice(0, 8).map((x) => x.join(' | ')));
  assert.ok(other.length / seen.size < 0.15, `${other.length} of ${seen.size}`);
});

test('schedules are divided by what uses them', () => {
  assert.equal(scheduleKind({ users: [] }), 'unused');
  assert.equal(scheduleKind({ users: [{ class: 'ThermostatSetpoint:DualSetpoint' }] }), 'setpoints');
  assert.equal(scheduleKind({ users: [{ class: 'People' }] }), 'loads');
  assert.equal(scheduleKind({ users: [{ class: 'AirLoopHVAC' }] }), 'hvac');
});

test('a row starts with the options of the zones in scope', () => {
  const owners = { 'WALL A': ['Z1'], 'WALL B': ['Z2'], Z1: ['Z1'], Z2: ['Z2'] };
  const opts = [{ id: 'a', label: 'Wall A' }, { id: 'b', label: 'Wall B' }, { id: 'n', label: 'Node 7' }];
  assert.deepEqual(defaultSelection(opts, new Set(['Z1', 'Z2']), owners), ['a', 'b']);
  assert.deepEqual(defaultSelection(opts, new Set(['Z2']), owners), ['b']);
  assert.deepEqual(defaultSelection([{ id: 'x', label: 'Environment' }], new Set(['Z1']), owners), ['x']);
  assert.deepEqual(defaultSelection([{ id: 'x', label: 'N1' }, { id: 'y', label: 'N2' }], new Set(['Z1']), owners), []);
});

test('identifiers', () => {
  assert.equal(toIdentifier('Zone Mean Air Temperature_BLOCK1:ZONEWEST'), 'Zone_Mean_Air_Temperature_BLOCK1_ZONEWEST');
  assert.equal(toIdentifier('1abc'), 'v_1abc');
  assert.equal(shortKey('BLOCK1:ZONEWEST'), 'ZONEWEST');
  assert.equal(shortKey('Environment'), '');
});

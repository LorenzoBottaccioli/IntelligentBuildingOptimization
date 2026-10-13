// SurrogateObjectGrid.jsx
// One card per object: its name, which is what FieldSelector's object_name
// takes, and its fields as a table under their IDD names, which field_name
// takes. Empty fields are left out.
import React, { useState } from 'react';

const materialFields = (m) => [
  ['Roughness', m.roughness],
  ['Thickness', m.thickness, 'm'],
  ['Conductivity', m.conductivity, 'W/m-K'],
  ['Density', m.density, 'kg/m3'],
  ['Specific Heat', m.specificHeat, 'J/kg-K'],
  ['Thermal Absorptance', m.thermalAbsorptance],
  ['Solar Absorptance', m.solarAbsorptance],
  ['Visible Absorptance', m.visibleAbsorptance],
];

const constructionFields = (c) =>
  [c.outsideLayer, ...(c.layers ?? []).slice(1)]
    .filter(Boolean)
    .map((layer, i) => [i === 0 ? 'Outside Layer' : `Layer ${i + 1}`, layer]);

const fenestrationFields = (f) => [
  ['Surface Type', f.surfaceType],
  ['Construction Name', f.constructionName],
  ['Building Surface Name', f.buildingSurfaceName],
  ['Frame and Divider Name', f.frameAndDividerName],
  ['Multiplier', f.multiplier],
];

const ventilationFields = (v) => [
  ['Zone or ZoneList Name', v.zone_name],
  ['Schedule Name', v.schedule_name],
  ['Design Flow Rate Calculation Method', v.design_flow_rate_calculation_method],
  ['Design Flow Rate', v.design_flow_rate, 'm3/s'],
  ['Flow Rate per Zone Floor Area', v.flow_per_zone_floor_area, 'm3/s-m2'],
  ['Flow Rate per Person', v.flow_rate_per_person, 'm3/s-person'],
  ['Air Changes per Hour', v.air_changes_per_hour, '1/hr'],
  ['Ventilation Type', v.ventilation_type],
  ['Minimum Indoor Temperature', v.minimum_indoor_temperature, 'C'],
  ['Maximum Indoor Temperature', v.maximum_indoor_temperature, 'C'],
  ['Delta Temperature', v.delta_temperature, 'deltaC'],
  ['Minimum Outdoor Temperature', v.minimum_outdoor_temperature, 'C'],
  ['Maximum Outdoor Temperature', v.maximum_outdoor_temperature, 'C'],
  ['Maximum Wind Speed', v.maximum_wind_speed, 'm/s'],
];

const lightsFields = (l) => [
  ['Zone or ZoneList or Space or SpaceList Name', l.zone_or_space_name],
  ['Schedule Name', l.schedule_name],
  ['Design Level Calculation Method', l.design_level_calculation_method],
  ['Lighting Level', l.lighting_level, 'W'],
  ['Watts per Zone Floor Area', l.watts_per_zone_floor_area, 'W/m2'],
  ['Watts per Person', l.watts_per_person, 'W/person'],
  ['Return Air Fraction', l.return_air_fraction],
  ['Fraction Radiant', l.fraction_radiant],
  ['Fraction Visible', l.fraction_visible],
  ['Fraction Replaceable', l.fraction_replaceable],
  ['End-Use Subcategory', l.end_use_subcategory],
];

const shadingFields = (s) => {
  const surfaces = [];
  for (let i = 1; i <= 10; i++) {
    if (s[`fenestration_surface_${i}_name`]) surfaces.push(s[`fenestration_surface_${i}_name`]);
  }
  return [
    ['Zone Name', s.zone_name],
    ['Shading Type', s.shading_type],
    ['Construction with Shading Name', s.construction_with_shading_name],
    ['Shading Device Material Name', s.shading_device_material_name],
    ['Shading Control Type', s.shading_control_type],
    ['Schedule Name', s.schedule_name],
    ['Setpoint', s.setpoint],
    ['Setpoint 2', s.setpoint_2],
    ['Type of Slat Angle Control for Blinds', s.slat_angle_control_type],
    ['Multiple Surface Control Type', s.multiple_surface_control_type],
    ...surfaces.map((n, i) => [`Fenestration Surface ${i + 1} Name`, n]),
  ];
};

export const FIELDS = {
  materials: materialFields,
  constructions: constructionFields,
  fenestration_surfaces: fenestrationFields,
  zone_ventilations: ventilationFields,
  lights: lightsFields,
  window_shading_controls: shadingFields,
};

const filled = (v) => v !== null && v !== undefined && String(v).trim() !== '';

function ObjectCard({ obj, type }) {
  const [copied, setCopied] = useState(false);
  const rows = FIELDS[type](obj).filter(([, value]) => filled(value));
  const copy = () => {
    navigator.clipboard?.writeText(obj.name).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };
  return (
    <div className="so-card">
      <div className="so-card-head">
        <code className="so-name">{obj.name}</code>
        <button type="button" className="so-copy" onClick={copy} title="Copy the name, for object_name">
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      {rows.length > 0 && (
        <table className="so-fields">
          <tbody>
            {rows.map(([label, value, unit]) => (
              <tr key={label}>
                <th>{label}</th>
                <td>
                  {String(value)}
                  {unit && <span className="so-unit"> {unit}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function SurrogateObjectGrid({ objects = [], type }) {
  if (!objects.length) return <p className="so-none">None in this model.</p>;
  return (
    <div className="so-list">
      {objects.map((obj) => (
        <ObjectCard key={obj.id ?? obj.name} obj={obj} type={type} />
      ))}
    </div>
  );
}

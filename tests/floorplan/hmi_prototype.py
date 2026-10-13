"""Prototype: the floor plan of the model as the page of openHAB and of Home Assistant.

Everything position-dependent comes from backend/floorplan.py (the zones of the model, in the files EnergyPlus writes); the
points come from the topics of the demo gateway (Workspace/devices/gateway.py). Nothing here is imported by the platform.

    python tests/floorplan/hmi_prototype.py --dxf backend/simulation_outputs/eplusout.dxf --eio backend/simulation_outputs/eplusout.eio \
        --out <folder>

writes into <folder>:   plan.svg, <zone>_<band>.svg (one overlay per zone and band), markers.json,
                        homeassistant/mqtt.yaml, homeassistant/lovelace.json, openhab/...
"""

import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANDS = (('cold', '#4f8fd6', 'below 18 °C'), ('ok', '#5fb878', '18 to 24 °C'), ('warm', '#f0a04b', 'above 24 °C'))
LIMITS = (18.0, 24.0)


def load_floorplan():
    spec = importlib.util.spec_from_file_location('floorplan', os.path.join(HERE, '..', '..', 'backend', 'floorplan.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules['floorplan'] = module
    spec.loader.exec_module(module)
    return module


def short(name):
    """'Block1:ZoneWest' -> 'west': the last part of the name without a leading 'zone'."""
    last = re.split(r'[:/]', name)[-1].strip().lower()
    last = re.sub(r'^zone[\s_-]*', '', last) or last
    return re.sub(r'[^a-z0-9]+', '_', last).strip('_')


def build(fp, dxf, eio, level=0):
    plan = fp.build_plan(fp.read_dxf(dxf), fp.eio_tables(eio))
    lv = next(l for l in plan['levels'] if l['index'] == level)
    x0, y0, x1, y1 = lv['bbox']
    w, h = x1 - x0, y1 - y0
    pad = max(w, h) * 0.06
    view = (x0 - pad, -(y1 + pad), w + 2 * pad, h + 2 * pad)          # SVG viewBox, y up -> -y
    marks = fp.markers(plan, level)
    zones = []
    for r in plan['zones']:
        if r['level'] != level:
            continue
        zones.append({'name': r['name'], 'id': short(r['name']), 'polygons': r['polygons'], 'x': marks[r['name']][0],
                      'y': marks[r['name']][1], 'outline': fp.outline(r['polygons'])})
    return plan, view, zones


def svg_head(view, width):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="{:.3f} {:.3f} {:.3f} {:.3f}" width="{}" height="{:.0f}">'
            .format(*view, width, width * view[3] / view[2]))


def path_of(polygons):
    return ' '.join('M' + ' L'.join('{:.3f},{:.3f}'.format(x, -y) for x, y in poly) + 'Z' for poly in polygons)


def edge_of(segments):
    return ' '.join('M{:.3f},{:.3f} L{:.3f},{:.3f}'.format(a[0], -a[1], b[0], -b[1]) for a, b in segments)


def plan_svg(view, zones, width=900):
    line = max(view[2], view[3]) * 0.004
    parts = [svg_head(view, width), '<rect x="{:.3f}" y="{:.3f}" width="{:.3f}" height="{:.3f}" fill="#f4f6f8"/>'.format(*view)]
    for z in zones:
        parts.append('<path d="{}" fill="#e6ebf0" stroke="#e6ebf0" stroke-width="{:.3f}" stroke-linejoin="round"/>'.format(path_of(z['polygons']), line / 3))
    for z in zones:
        parts.append('<path d="{}" fill="none" stroke="#6b7a89" stroke-width="{:.3f}" stroke-linecap="round"/>'.format(edge_of(z['outline']), line))
    parts.append('</svg>')
    return '\n'.join(parts)


def overlay_svg(view, zone, colour, width=900):
    """Only this zone, filled with the colour of its band, on a transparent background (same viewBox as the plan)."""
    line = max(view[2], view[3]) * 0.004
    return '\n'.join([svg_head(view, width),
                      '<path d="{}" fill="{}" fill-opacity="0.72" stroke="{}" stroke-opacity="0.72" stroke-width="{:.3f}" stroke-linejoin="round"/>'
                      .format(path_of(zone['polygons']), colour, colour, line / 3),
                      '<path d="{}" fill="none" stroke="#6b7a89" stroke-width="{:.3f}" stroke-linecap="round"/>'.format(edge_of(zone['outline']), line),
                      '</svg>'])


# ---- Home Assistant -----------------------------------------------------------------------------------

BAND_TEMPLATE = ("{{% set t = value_json.value | float(0) %}}{{{{ 'cold' if t < {lo} else ('warm' if t > {hi} else 'ok') }}}}"
                 .format(lo=LIMITS[0], hi=LIMITS[1]))


def device(z):
    """One device per zone: Home Assistant groups its entities and creates the area (its model of rooms, like openHAB's Locations).

    The ids the dashboard uses (sensor.west_temperature_controlled) are fixed with default_entity_id on every entity
    that has a device. Without it only an installation whose registry already held them kept them: a new Home
    Assistant builds an id from the area, the device and the name (sensor.west_zone_west_temperature_controlled)
    and the dashboard shows a warning triangle where an entity is missing.
    """
    return {'identifiers': ['demo_zone_' + z['id']], 'name': z['id'].title(), 'manufacturer': 'Demo building', 'model': 'Heating zone',
            'suggested_area': z['id'].title() + ' zone'}


def ha_mqtt(zones):
    sensors, climates = [], []
    for run in ('controlled', 'baseline'):
        for z in zones:
            sensors.append({'name': f"Temperature {run}", 'device': device(z), 'unique_id': f"demo_temperature_{z['id']}_{run}",
                            'default_entity_id': f"sensor.{z['id']}_temperature_{run}",
                            'state_topic': f"demo/{run}/temperature_{z['id']}", 'value_template': '{{ value_json.value }}',
                            'unit_of_measurement': '°C', 'device_class': 'temperature', 'state_class': 'measurement'})
            sensors.append({'name': f"Comfort {run}", 'device': device(z), 'unique_id': f"demo_comfort_{z['id']}_{run}",
                            'default_entity_id': f"sensor.{z['id']}_comfort_{run}",
                            'state_topic': f"demo/{run}/temperature_{z['id']}", 'value_template': BAND_TEMPLATE})
        for name, key, unit, cls, state in (('Electricity power', 'electricity_kw', 'kW', 'power', 'measurement'),
                                            ('Heating power', 'heating_kw', 'kW', 'power', 'measurement'),
                                            ('Electricity energy', 'electricity_kwh', 'kWh', 'energy', 'total_increasing'),
                                            ('Heating energy', 'heating_kwh', 'kWh', 'energy', 'total_increasing')):
            sensors.append({'name': f"{name} {run}", 'unique_id': f"demo_{key}_{run}", 'state_topic': f"demo/{run}/{key}",
                            'value_template': '{{ value_json.value }}', 'unit_of_measurement': unit, 'device_class': cls, 'state_class': state})
    for z in zones:
        sensors.append({'name': 'Setpoint', 'device': device(z), 'unique_id': f"demo_setpoint_{z['id']}",
                        'default_entity_id': f"sensor.{z['id']}_setpoint",
                        'state_topic': f"demo/controlled/setpoint/{z['id']}", 'value_template': '{{ value_json.value }}',
                        'unit_of_measurement': '°C', 'device_class': 'temperature'})
        climates.append({'name': 'Thermostat', 'device': device(z), 'unique_id': f"demo_thermostat_{z['id']}",
                         'default_entity_id': f"climate.{z['id']}_thermostat",
                         'current_temperature_topic': f"demo/controlled/temperature_{z['id']}",
                         'current_temperature_template': '{{ value_json.value }}',
                         'temperature_state_topic': f"demo/controlled/setpoint/{z['id']}",
                         'temperature_state_template': '{{ value_json.value }}',
                         'temperature_command_topic': f"demo/controlled/cmd/{z['id']}",
                         'temperature_command_template': '{"value": {{ value | float }}}',
                         'modes': ['heat'], 'mode_state_topic': 'demo/site/run', 'mode_state_template': 'heat', 'min_temp': 10, 'max_temp': 30, 'temp_step': 1, 'precision': 0.1})
    for name, key, unit, cls in (('Outdoor temperature', 'outdoor_temperature', '°C', 'temperature'),
                                 ('Outdoor humidity', 'outdoor_humidity', '%', 'humidity'),
                                 ('Wind speed', 'wind_speed', 'm/s', None),
                                 ('Direct solar', 'solar_direct', 'W/m²', 'irradiance')):
        sensors.append({'name': name, 'unique_id': f"demo_{key}", 'state_topic': f"demo/site/{key}",
                        'value_template': '{{ value_json.value }}', 'unit_of_measurement': unit, 'state_class': 'measurement',
                        **({'device_class': cls} if cls else {})})
    sensors.append({'name': 'Simulated time', 'unique_id': 'demo_clock', 'state_topic': 'demo/site/clock',
                    'value_template': "{{ as_datetime(value_json.value).strftime('%a %d %b %Y, %H:%M') }}", 'icon': 'mdi:clock-outline'})
    sensors.append({'name': 'Run in progress', 'unique_id': 'demo_run', 'state_topic': 'demo/site/run',
                    'value_template': '{{ value_json.value }}', 'icon': 'mdi:play-circle-outline'})
    return {'sensor': sensors, 'climate': climates}


def yaml_dump(data, indent=0):
    """Minimal YAML for the nested dicts/lists above (no dependency on PyYAML)."""
    pad = '  ' * indent
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{k}:")
                out.append(yaml_dump(v, indent + 1))
            else:
                out.append(f"{pad}{k}: {scalar(v)}")
    else:
        for item in data:
            if isinstance(item, dict):
                lines = yaml_dump(item, indent + 1).split('\n')
                out.append(f"{pad}- {lines[0].strip()}")
                out.extend(lines[1:])
            else:
                out.append(f"{pad}- {scalar(item)}")
    return '\n'.join(out)


def scalar(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    return json.dumps(v, ensure_ascii=False)


HISTORY_HOURS = 6


def history_cards(zones):
    """What the History panel of Home Assistant shows only after the entities are picked, ready on a page.

    The recorder stores every state with the time it ARRIVED, not with the simulated time of the payload: the x axis is real
    time, so a run in `scaled` mode (about one simulated day per minute) gives readable curves and `fast` gives a spike.
    """
    def graph(title, entities):
        return {'type': 'history-graph', 'title': title, 'hours_to_show': HISTORY_HOURS, 'show_names': True, 'entities': entities}

    temps = [f"sensor.{z['id']}_temperature_controlled" for z in zones]
    return [
        {'type': 'markdown', 'content': f"Last {HISTORY_HOURS} hours of **real** time: the history is stamped when a value arrives, "
                                        "not with the simulated date. Run the building in *scaled* mode to get curves."},
        graph('Zone temperatures, controlled run', temps + ['sensor.outdoor_temperature']),
        graph('Heating setpoints applied', [f"sensor.{z['id']}_setpoint" for z in zones]),
        graph('Controlled against baseline, ' + zones[0]['id'], [f"sensor.{zones[0]['id']}_temperature_controlled",
                                                                   f"sensor.{zones[0]['id']}_temperature_baseline",
                                                                   'sensor.outdoor_temperature']),
        graph('Heating power', ['sensor.heating_power_controlled', 'sensor.heating_power_baseline']),
        graph('Electricity power', ['sensor.electricity_power_controlled', 'sensor.electricity_power_baseline']),
        {'type': 'button', 'name': 'Open the History panel with the zone temperatures', 'icon': 'mdi:chart-line',
         'tap_action': {'action': 'navigate', 'navigation_path': '/history?entity_id=' + ','.join(temps + ['sensor.outdoor_temperature'])}},
    ]


def ha_lovelace(zones, ratio):
    def plan_card(run):
        elements = []
        for z in zones:
            for band, colour, _ in BANDS:
                elements.append({'type': 'conditional', 'conditions': [{'entity': f"sensor.{z['id']}_comfort_{run}", 'state': band}],
                                 'elements': [{'type': 'image', 'image': f"/local/floorplan/{z['id']}_{band}.svg",
                                               'style': {'left': '50%', 'top': '50%', 'width': '100%', 'pointer-events': 'none'}}]})
        for z in zones:
            elements.append({'type': 'state-label', 'entity': f"sensor.{z['id']}_temperature_{run}", 'prefix': z['id'].title() + '  ',
                             'style': {'left': f"{z['x']}%", 'top': f"{z['y'] - 4:.1f}%", 'color': '#1d2733', 'font-size': '17px', 'font-weight': '700'}})
            if run == 'controlled':
                elements.append({'type': 'state-label', 'entity': f"sensor.{z['id']}_setpoint", 'prefix': 'set ',
                                 'style': {'left': f"{z['x']}%", 'top': f"{z['y'] + 3:.1f}%", 'color': '#3b4a59', 'font-size': '11px'}})
        return {'type': 'picture-elements', 'image': '/local/floorplan/plan.svg', 'elements': elements}

    import hmi_ha_views
    return {'title': 'Demo building', 'views': hmi_ha_views.build(zones, plan_card, history_cards, HISTORY_HOURS)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dxf', required=True)
    ap.add_argument('--eio', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    fp = load_floorplan()
    plan, view, zones = build(fp, args.dxf, args.eio)
    os.makedirs(os.path.join(args.out, 'homeassistant'), exist_ok=True)
    with open(os.path.join(args.out, 'plan.svg'), 'w', encoding='utf-8') as f:
        f.write(plan_svg(view, zones))
    for z in zones:
        for band, colour, _ in BANDS:
            with open(os.path.join(args.out, f"{z['id']}_{band}.svg"), 'w', encoding='utf-8') as f:
                f.write(overlay_svg(view, z, colour))
    with open(os.path.join(args.out, 'markers.json'), 'w') as f:
        json.dump({'viewBox': view, 'zones': [{k: z[k] for k in ('name', 'id', 'x', 'y')} for z in zones]}, f, indent=1)
    with open(os.path.join(args.out, 'homeassistant', 'mqtt.yaml'), 'w', encoding='utf-8') as f:
        data = ha_mqtt(zones)
        f.write('\n'.join(f"{kind}:\n{yaml_dump(items, 1)}" for kind, items in data.items()) + '\n')
    with open(os.path.join(args.out, 'homeassistant', 'lovelace.json'), 'w', encoding='utf-8') as f:
        json.dump(ha_lovelace(zones, view[2] / view[3]), f, indent=1, ensure_ascii=False)
    sys.path.insert(0, HERE)
    import hmi_openhab as oh
    ohdir = os.path.join(args.out, 'openhab')
    os.makedirs(ohdir, exist_ok=True)
    colours = [b[1] for b in BANDS]
    for name, text in (('simbuilding.things', oh.things(zones)), ('simbuilding.items', oh.items(zones)), ('simbuilding.sitemap', oh.sitemap(zones))):
        with open(os.path.join(ohdir, name), 'w', encoding='utf-8') as f:
            f.write(text)
    with open(os.path.join(ohdir, 'uicomponents_ui_page.json'), 'w', encoding='utf-8') as f:
        json.dump(oh.pages(zones, view, LIMITS, colours), f, indent=2, ensure_ascii=False)
    print('zones:', [(z['id'], z['x'], z['y']) for z in zones])


if __name__ == '__main__':
    main()

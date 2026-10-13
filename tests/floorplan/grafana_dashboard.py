"""Run with GRAFANA_ADMIN_USER and GRAFANA_ADMIN_PASSWORD in the environment (the .env of the repository).

Grafana dashboard 'Demo building' for the points of the new demo gateway (points,point=<name> in base_building / controlled_building)."""
import base64
import json
import os
import urllib.request

BASE = 'PEA767B3DDC7793D7'          # uids of the data sources of this platform (InfluxDB Base / Controlled)
CONTROLLED = 'P3C427C6903D4C228'
DS = {'baseline': {'type': 'influxdb', 'uid': BASE}, 'controlled': {'type': 'influxdb', 'uid': CONTROLLED}}
ZONES = ('west', 'south', 'east', 'north')
COLOURS = {'west': 'blue', 'south': 'orange', 'east': 'green', 'north': 'purple'}
RUN_COLOUR = {'baseline': 'green', 'controlled': 'yellow'}


def query(run, point, alias, ref):
    return {'datasource': DS[run], 'refId': ref, 'rawQuery': True, 'resultFormat': 'time_series', 'alias': alias,
            'query': 'SELECT mean("value") FROM "points" WHERE "point" = \'{}\' AND $timeFilter GROUP BY time($__interval) fill(previous)'.format(point)}


def override(name, colour, extra=None):
    props = [{'id': 'color', 'value': {'mode': 'fixed', 'fixedColor': colour}}]
    props += extra or []
    return {'matcher': {'id': 'byName', 'options': name}, 'properties': props}


def series(title, targets, overrides, unit, x, y, w=12, h=8, min_=None, max_=None):
    defaults = {'unit': unit, 'custom': {'lineWidth': 2, 'fillOpacity': 0, 'spanNulls': True, 'showPoints': 'never'}}
    if min_ is not None:
        defaults['min'] = min_
    if max_ is not None:
        defaults['max'] = max_
    return {'type': 'timeseries', 'title': title, 'datasource': {'type': 'datasource', 'uid': '-- Mixed --'}, 'targets': targets,
            'fieldConfig': {'defaults': defaults, 'overrides': overrides}, 'interval': '10m',
            'options': {'legend': {'displayMode': 'list', 'placement': 'bottom'}, 'tooltip': {'mode': 'multi'}},
            'gridPos': {'x': x, 'y': y, 'w': w, 'h': h}}


def stat(title, run, point, unit, x, y, decimals=0):
    return {'type': 'stat', 'title': title, 'datasource': DS[run], 'gridPos': {'x': x, 'y': y, 'w': 4, 'h': 4},
            'targets': [{'datasource': DS[run], 'refId': 'A', 'rawQuery': True, 'resultFormat': 'time_series',
                         'query': 'SELECT last("value") FROM "points" WHERE "point" = \'{}\' AND $timeFilter'.format(point)}],
            'fieldConfig': {'defaults': {'unit': unit, 'decimals': decimals, 'color': {'mode': 'fixed', 'fixedColor': RUN_COLOUR[run]}}, 'overrides': []},
            'options': {'colorMode': 'value', 'graphMode': 'none', 'reduceOptions': {'calcs': ['lastNotNull']}}}


panels = []
panels += [stat('Heating energy, baseline', 'baseline', 'heating_kwh', 'suffix: kWh', 0, 0), stat('Heating energy, controlled', 'controlled', 'heating_kwh', 'suffix: kWh', 4, 0),
           stat('Electricity energy, baseline', 'baseline', 'electricity_kwh', 'suffix: kWh', 8, 0), stat('Electricity energy, controlled', 'controlled', 'electricity_kwh', 'suffix: kWh', 12, 0)]
panels.append({'type': 'text', 'title': 'Reading the numbers', 'gridPos': {'x': 16, 'y': 0, 'w': 8, 'h': 4},
               'options': {'mode': 'markdown', 'content': 'Energy is the value reached **at the end of the selected period** (cumulated since the start of each run). '
                                                          'A run that stops earlier shows what it had reached.'}})

targets = [query('controlled', 'temperature_' + z, z, chr(65 + i)) for i, z in enumerate(ZONES)]
targets.append(query('controlled', 'outdoor_temperature', 'outdoor', 'E'))
panels.append(series('Zone temperatures, controlled run', targets,
                     [override(z, COLOURS[z]) for z in ZONES] + [override('outdoor', 'dark-gray', [{'id': 'custom.lineStyle', 'value': {'fill': 'dash', 'dash': [8, 8]}}])],
                     'celsius', 0, 4))
panels.append(series('West zone: controlled against baseline',
                     [query('controlled', 'temperature_west', 'controlled', 'A'), query('baseline', 'temperature_west', 'baseline', 'B'),
                      query('controlled', 'outdoor_temperature', 'outdoor', 'C')],
                     [override('controlled', 'yellow'), override('baseline', 'green'),
                      override('outdoor', 'dark-gray', [{'id': 'custom.lineStyle', 'value': {'fill': 'dash', 'dash': [8, 8]}}])], 'celsius', 12, 4))
panels.append(series('Heating setpoints applied by the controller', [query('controlled', 'setpoint_' + z, z, chr(65 + i)) for i, z in enumerate(ZONES)],
                     [override(z, COLOURS[z]) for z in ZONES], 'celsius', 0, 12, min_=8, max_=32))
panels.append(series('Heating power', [query('controlled', 'heating_kw', 'controlled', 'A'), query('baseline', 'heating_kw', 'baseline', 'B')],
                     [override('controlled', 'yellow'), override('baseline', 'green')], 'kwatt', 12, 12))
panels.append(series('Electricity power', [query('controlled', 'electricity_kw', 'controlled', 'A'), query('baseline', 'electricity_kw', 'baseline', 'B')],
                     [override('controlled', 'yellow'), override('baseline', 'green')], 'kwatt', 0, 20))
panels.append(series('Outdoor weather', [query('controlled', 'outdoor_temperature', 'temperature', 'A'), query('controlled', 'solar_direct', 'direct solar', 'B'),
                                         query('controlled', 'wind_speed', 'wind', 'C')],
                     [override('temperature', 'blue'),
                      override('direct solar', 'orange', [{'id': 'unit', 'value': 'watt'}, {'id': 'custom.axisPlacement', 'value': 'right'}]),
                      override('wind', 'gray', [{'id': 'unit', 'value': 'velocityms'}, {'id': 'custom.axisPlacement', 'value': 'hidden'}])], 'celsius', 12, 20))

dashboard = {'uid': 'demo-building', 'title': 'Demo building', 'tags': ['demo'], 'timezone': 'utc', 'schemaVersion': 39,
             'time': {'from': '2026-01-01T00:00:00.000Z', 'to': '2026-01-08T00:00:00.000Z'}, 'refresh': '', 'panels': panels}
for i, p in enumerate(panels, 1):
    p['id'] = i

user, password = os.environ['GRAFANA_ADMIN_USER'], os.environ['GRAFANA_ADMIN_PASSWORD']
req = urllib.request.Request('http://localhost:3000/api/dashboards/db', data=json.dumps({'dashboard': dashboard, 'overwrite': True}).encode(), method='POST',
                             headers={'Content-Type': 'application/json',
                                      'Authorization': 'Basic ' + base64.b64encode('{}:{}'.format(user, password).encode()).decode()})
print(json.load(urllib.request.urlopen(req, timeout=30)))

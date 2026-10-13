"""openHAB side of the floor plan prototype (see hmi_prototype.py): things, items, sitemap and the two Main UI pages.

The plan page is an `oh-plan-page` on /static/floorplan/plan.svg (conf/html/floorplan/plan.svg) with `oh-plan-marker` labels.
Marker `coords` are "y,x" in pixels of the image, y counted from the bottom (the page uses a simple Leaflet CRS).
"""

IMAGE_WIDTH = 900
# the label sits in a 40 px icon box centred on the point: an inline-block shifted by half the box and half its own width is centred
CENTRED = {'display': 'inline-block', 'position': 'relative', 'left': '20px', 'transform': 'translateX(-50%)'}
DEG = '°C'
SQ = 'W/m²'


def names(z):
    return z['id'].title()


def things(zones):
    ch = []

    def number(cid, label, topic, extra=''):
        ch.append('            Type number : {} "{}" [ stateTopic="{}", transformationPattern="JSONPATH:$.value"{} ]'.format(cid, label, topic, extra))

    for run in ('controlled', 'baseline'):
        for z in zones:
            number('temp_{}_{}'.format(z['id'], run), '{} temperature, {}'.format(names(z), run), 'demo/{}/temperature_{}'.format(run, z['id']))
        for key in ('electricity_kw', 'heating_kw', 'electricity_kwh', 'heating_kwh'):
            number('{}_{}'.format(key, run), '{} {}'.format(key, run), 'demo/{}/{}'.format(run, key))
    for z in zones:
        number('sp_' + z['id'], '{} setpoint'.format(names(z)), 'demo/controlled/setpoint/' + z['id'],
               ', commandTopic="demo/controlled/cmd/{}", formatBeforePublish="{{\\"value\\": %s}}"'.format(z['id']))
    for key in ('outdoor_temperature', 'outdoor_humidity', 'wind_speed', 'solar_direct'):
        number(key, key, 'demo/site/' + key)
    ch.append('            Type string : clock "Simulated time" [ stateTopic="demo/site/clock", transformationPattern="JSONPATH:$.value" ]')
    ch.append('            Type string : run "Run in progress" [ stateTopic="demo/site/run", transformationPattern="JSONPATH:$.value" ]')
    return ('Bridge mqtt:broker:demoBroker [ host="mosquitto", port=1883, secure=false, clientID="openhab-demo" ] {\n'
            '    Thing topic demoBuilding "Demo building" {\n        Channels:\n' + '\n'.join(ch) + '\n    }\n}\n')


def items(zones):
    def ref(cid):
        return '{ channel="mqtt:topic:demoBroker:demoBuilding:' + cid + '" }'

    lines = ['// Semantic model: Building > Rooms > HVAC equipment > points, and the Outdoor location with its weather station.',
             'Group gDemo "Demo building" <house> ["Building"]']
    for z in zones:
        n = names(z)
        lines.append('Group g{} "{} zone" <office> (gDemo) ["Room"]'.format(n, n))
        lines.append('Group e{} "{} zone heating" (g{}) ["HVAC"]'.format(n, n, n))
    lines += ['Group gOutdoor "Outdoor" <sun> (gDemo) ["Outdoor"]', 'Group eWeather "Weather" (gOutdoor) ["WeatherService"]', '']
    for z in zones:
        n = names(z)
        for run in ('controlled', 'baseline'):
            lines.append('Number Temp_{n}_{R} "{n} temperature, {run} [%.1f {deg}]" <temperature> (e{n}) ["Measurement", "Temperature"] {r}'.format(
                n=n, R=run.title(), run=run, deg=DEG, r=ref('temp_{}_{}'.format(z['id'], run))))
        lines.append('Number Setpoint_{n} "{n} heating setpoint [%.0f {deg}]" <heating> (e{n}) ["Setpoint", "Temperature"] {r}'.format(
            n=n, deg=DEG, r=ref('sp_' + z['id'])))
    for key, label, fmt, tags in (('outdoor_temperature', 'Outdoor temperature', '%.1f ' + DEG, '"Measurement", "Temperature"'),
                                  ('outdoor_humidity', 'Outdoor humidity', '%.0f %%', '"Measurement", "Humidity"'),
                                  ('wind_speed', 'Wind speed', '%.1f m/s', '"Measurement", "Wind"'),
                                  ('solar_direct', 'Direct solar radiation', '%.0f ' + SQ, '"Measurement", "Irradiance"')):
        lines.append('Number {} "{} [{}]" (eWeather) [{}] {}'.format(item_name(key), label, fmt, tags, ref(key)))
    lines.append('String Sim_Clock "Simulated time [%s]" <time> (gDemo) ' + ref('clock'))
    lines.append('String Run_Now "Run in progress [%s]" (gDemo) ' + ref('run'))
    lines.append('')
    for run in ('controlled', 'baseline'):
        for key, label, fmt in (('electricity_kw', 'Electricity power', '%.2f kW'), ('heating_kw', 'Heating power', '%.2f kW'),
                                ('electricity_kwh', 'Electricity energy', '%.1f kWh'), ('heating_kwh', 'Heating energy', '%.1f kWh')):
            lines.append('Number {}_{} "{}, {} [{}]" <energy> (gDemo) ["Measurement", "Energy"] {}'.format(
                item_name(key), run.title(), label, run, fmt, ref('{}_{}'.format(key, run))))
    return '\n'.join(lines) + '\n'


def item_name(key):
    """outdoor_temperature -> Outdoor_Temperature, heating_kw -> Heating_kW, electricity_kwh -> Electricity_kWh."""
    return '_'.join({'kw': 'kW', 'kwh': 'kWh'}.get(p, p.title()) for p in key.split('_'))


def sitemap(zones):
    out = ['sitemap simbuilding label="Demo building" {', '    Frame label="Site" {',
           '        Text item=Sim_Clock', '        Text item=Outdoor_Temperature', '    }']
    for z in zones:
        n = names(z)
        out += ['    Frame label="{} zone" {{'.format(n),
                '        Text item=Temp_{}_Controlled valuecolor=[<18="blue", >24="orange", >=18="green"]'.format(n),
                '        Text item=Temp_{}_Baseline'.format(n),
                '        Setpoint item=Setpoint_{} minValue=10 maxValue=30 step=1'.format(n), '    }']
    out.append('}')
    return '\n'.join(out) + '\n'


def band_colour(item, limits, colours):
    return "=(items.{i}.numericState < {lo:g} ? '{c0}' : (items.{i}.numericState > {hi:g} ? '{c2}' : '{c1}'))".format(
        i=item, lo=limits[0], hi=limits[1], c0=colours[0], c1=colours[1], c2=colours[2])


def tile(title, label, background, icon, size='30px', **extra):
    """A label card used as a coloured tile: a title, a large value, a background that can be an expression."""
    config = {'title': title, 'label': label, 'background': background, 'icon': icon, 'iconSize': 34, 'fontSize': size, 'fontWeight': '700',
              'vertical': True, 'action': 'none'}
    config.update(extra)
    return {'component': 'oh-label-card', 'config': config}


def overview_page(zones, limits, colours):
    """The Overview tab, as tiles: a coloured tile per zone (band of its temperature), the site, the weather, the result.

    Label cards take expressions for the label and for the background, so the colour follows the state without any rule.
    """
    def band(item):
        return band_colour(item, limits, colours)

    cards = [tile('Simulated time', '=items.Sim_Clock.state.replace("T", "  ")', '#eef2f6', 'f7:clock', '22px'),
             tile('Run in progress', '=items.Run_Now.state', '#eef2f6', 'f7:play_circle', '24px')]
    for z in zones:
        n = names(z)
        cards.append(tile('=" {} zone - set " + items.Setpoint_{}.displayState'.format(n, n),
                          '=items.Temp_{}_Controlled.displayState'.format(n), band('Temp_{}_Controlled'.format(n)), 'f7:thermometer', '34px'))
    cards.append(tile('Outdoor', '=items.Outdoor_Temperature.displayState', '#dfeaf6', 'f7:cloud_sun', '30px'))
    cards.append(tile('Humidity and wind', '=items.Outdoor_Humidity.displayState + "   " + items.Wind_Speed.displayState', '#dfeaf6', 'f7:wind', '22px'))
    cards.append(tile('Direct solar radiation', '=items.Solar_Direct.displayState', '#fbf1d9', 'f7:sun_max', '26px'))
    cards.append(tile('Heating energy, controlled', '=items.Heating_kWh_Controlled.displayState', '#eef2f6', 'f7:flame', '24px'))
    cards.append(tile('Heating energy, baseline', '=items.Heating_kWh_Baseline.displayState', '#eef2f6', 'f7:flame', '24px'))
    ratio = '(1 - items.Heating_kWh_Controlled.numericState / items.Heating_kWh_Baseline.numericState)'
    cards.append(tile('Heating energy saved by the controller',
                      '=(items.Heating_kWh_Baseline.numericState > 0 ? Math.round(1000 * {r}) / 10 + " %" : "-")'.format(r=ratio),
                      '=(items.Heating_kWh_Baseline.numericState > 0 && {r} > 0 ? "#cfe9d4" : "#f6dcd0")'.format(r=ratio), 'f7:leaf', '30px'))
    return {'component': 'oh-layout-page',
            'config': {'label': 'Overview', 'layoutType': 'responsive'},
            'slots': {'default': [], 'masonry': [{'component': 'oh-masonry', 'config': {}, 'slots': {'default': cards}}]}}


def overview_page_lists(zones, limits, colours):
    """The first version of the Overview tab, as lists (kept for comparison; not used).

    A floor plan page does not render in that tab (it is a full page), so the plan has its own page and this one is a layout page
    of cards: the site (time, run, weather), the zones with their setpoints, the energy of the last runs and what the controller saved.
    """
    def row(title, subtitle, after, icon, badge=None, badge_colour=None):
        config = {'title': title, 'subtitle': subtitle, 'after': after, 'icon': icon}
        if badge:
            config.update({'badge': badge, 'badgeColor': badge_colour})
        return {'component': 'oh-list-item', 'config': config}

    zone_rows = []
    for z in zones:
        n = names(z)
        zone_rows.append(row('{} zone'.format(n),
                             '="set " + items.Setpoint_{n}.displayState + "   baseline " + items.Temp_{n}_Baseline.displayState'.format(n=n),
                             '=items.Temp_{}_Controlled.displayState'.format(n), 'f7:thermometer'))
    weather_rows = [row('Outdoor temperature', '', '=items.Outdoor_Temperature.displayState', 'f7:thermometer'),
                    row('Outdoor humidity', '', '=items.Outdoor_Humidity.displayState', 'f7:drop'),
                    row('Wind', '', '=items.Wind_Speed.displayState', 'f7:wind'),
                    row('Direct solar radiation', '', '=items.Solar_Direct.displayState', 'f7:sun_max')]
    energy_rows = []
    for key, label in (('Heating', 'Heating energy'), ('Electricity', 'Electricity energy')):
        energy_rows.append(row(label, '="baseline " + items.{k}_kWh_Baseline.displayState'.format(k=key),
                               '=items.{k}_kWh_Controlled.displayState'.format(k=key), 'f7:flame' if key == 'Heating' else 'f7:bolt'))

    saved = ('="Heating energy saved by the controller: " + (items.Heating_kWh_Baseline.numericState > 0 ? '
             'Math.round(100 * (1 - items.Heating_kWh_Controlled.numericState / items.Heating_kWh_Baseline.numericState)) + " %" : "-")')
    cards = [
        {'component': 'oh-label-card', 'config': {'label': '=items.Sim_Clock.state.replace("T", "  ")', 'icon': 'f7:clock', 'iconSize': 30,
                                                   'fontSize': '22px', 'fontWeight': '700', 'action': 'none'}},
        {'component': 'oh-label-card', 'config': {'label': '="Run in progress: " + items.Run_Now.state', 'icon': 'f7:play_circle', 'iconSize': 30,
                                                   'fontSize': '18px', 'action': 'none'}},
        {'component': 'oh-list-card', 'config': {'title': 'Zones, controlled run', 'mediaList': True},
         'slots': {'default': zone_rows}},
        {'component': 'oh-list-card', 'config': {'title': 'Weather'}, 'slots': {'default': weather_rows}},
        {'component': 'oh-list-card', 'config': {'title': 'Energy of the last runs (controlled)', 'mediaList': True}, 'slots': {'default': energy_rows}},
        {'component': 'oh-label-card', 'config': {'label': saved, 'icon': 'f7:leaf', 'iconSize': 30, 'fontSize': '18px', 'action': 'none'}},
    ]
    return {'component': 'oh-layout-page',
            'config': {'label': 'Overview', 'layoutType': 'responsive'},
            'slots': {'default': [], 'masonry': [{'component': 'oh-masonry', 'config': {}, 'slots': {'default': cards}}]}}


def pages(zones, view, limits, colours):
    height = round(IMAGE_WIDTH * view[3] / view[2])
    markers = []
    for z in zones:
        n = names(z)
        x = z['x'] / 100 * IMAGE_WIDTH
        rows = ((-4.5, {'tooltip': '="{}  " + items.Temp_{}_Controlled.displayState'.format(n, n),
                        'tooltipStyle': dict(CENTRED, **{'background-color': band_colour('Temp_{}_Controlled'.format(n), limits, colours), 'color': '#1d2733',
                                         'padding': '3px 10px', 'border-radius': '10px', 'font-weight': '700', 'font-size': '16px'})}),
                (1.5, {'tooltip': '="set " + items.Setpoint_{}.displayState'.format(n),
                       'tooltipStyle': dict(CENTRED, **{'color': '#3b4a59', 'font-size': '12px'})}),
                (6.0, {'tooltip': '="baseline " + items.Temp_{}_Baseline.displayState'.format(n),
                       'tooltipStyle': dict(CENTRED, **{'color': '#7a8793', 'font-size': '12px'})}))
        for dy, config in rows:
            y = (100 - (z['y'] + dy)) / 100 * height
            markers.append({'component': 'oh-plan-marker',
                            'config': dict({'coords': '{:.1f},{:.1f}'.format(y, x), 'useTooltipAsLabel': True, 'tooltipPermanent': True}, **config)})
    plan = {'component': 'oh-plan-page',
            'config': {'label': 'Floor plan', 'imageUrl': '/static/floorplan/plan.svg', 'imageWidth': IMAGE_WIDTH, 'imageHeight': height,
                       'noZoomOrDrag': True, 'sidebar': True, 'order': '100', 'icon': 'f7:map'},
            'slots': {'default': markers}}

    cards = [{'component': 'oh-label-card', 'config': {'title': 'Simulated time', 'item': 'Sim_Clock', 'icon': 'f7:clock', 'action': 'none'}},
             {'component': 'oh-label-card', 'config': {'title': 'Run in progress', 'item': 'Run_Now', 'icon': 'f7:play_circle', 'action': 'none'}}]
    for z in zones:
        n = names(z)
        cards.append({'component': 'oh-gauge-card', 'config': {'title': '{} zone, controlled'.format(n), 'item': 'Temp_{}_Controlled'.format(n),
                                                                 'type': 'semicircle', 'min': 8, 'max': 26, 'unit': DEG, 'valueFontSize': 26}})
        cards.append({'component': 'oh-slider-card', 'config': {'title': '{} heating setpoint (the controller overwrites it every step)'.format(n),
                                                                 'item': 'Setpoint_' + n, 'min': 10, 'max': 30, 'step': 1, 'unit': DEG,
                                                                 'scale': True, 'scaleSteps': 4}})
    for item, title, lo, hi in (('Outdoor_Temperature', 'Outdoor temperature', -10, 40), ('Heating_kW_Controlled', 'Heating power, controlled', 0, 20),
                                ('Heating_kW_Baseline', 'Heating power, baseline', 0, 20), ('Electricity_kW_Controlled', 'Electricity power, controlled', 0, 20)):
        cards.append({'component': 'oh-gauge-card', 'config': {'title': title, 'item': item, 'type': 'semicircle', 'min': lo, 'max': hi, 'valueFontSize': 26}})
    controls = {'component': 'oh-layout-page',
                'config': {'label': 'Controls and energy', 'layoutType': 'responsive', 'sidebar': True, 'order': '110', 'icon': 'f7:slider_horizontal_3'},
                'slots': {'default': [], 'masonry': [{'component': 'oh-masonry', 'config': {}, 'slots': {'default': cards}}]}}
    overview = overview_page(zones, limits, colours)
    stamp = 'Oct 11, 2026, 1:30:00 PM'
    out = {}
    for uid, page in (('overview', overview), ('floorplan', plan), ('controls', controls)):
        value = {'uid': uid, 'tags': [], 'props': {'parameters': [], 'parameterGroups': []}, 'timestamp': stamp}
        value.update(page)
        out[uid] = {'class': 'org.openhab.core.ui.components.RootUIComponent', 'value': value}
    return out

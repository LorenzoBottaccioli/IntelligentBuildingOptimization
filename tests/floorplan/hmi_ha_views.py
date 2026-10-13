"""The views of the Home Assistant dashboard of the prototype (see hmi_prototype.py): sections views with headings, badges and tiles.

Entities are the ones of hmi_prototype.ha_mqtt(): sensor.<zone>_temperature_<run>, sensor.<zone>_comfort_<run>, sensor.<zone>_setpoint,
climate.<zone>_thermostat, sensor.<kind>_<power|energy>_<run>, and the site sensors (outdoor_*, wind_speed, direct_solar, simulated_time, run_in_progress).
"""

SAVED = ("{% set c = states('sensor.heating_energy_controlled') | float(0) %}{% set b = states('sensor.heating_energy_baseline') | float(0) %}"
         "## {{ ((1 - c / b) * 100) | round(1) if b > 0 else '-' }} %\n"
         "heating energy saved by the controller, last run of each ({{ c | round(0) }} against {{ b | round(0) }} kWh)")


def heading(text, icon, badges=()):
    card = {'type': 'heading', 'heading': text, 'heading_style': 'title', 'icon': icon}
    if badges:
        card['badges'] = [{'type': 'entity', 'entity': e} for e in badges]
    return card


def gauge(entity, name, high):
    segments = [{'from': 0, 'color': '#5fb878'}, {'from': high * 0.5, 'color': '#f0a04b'}, {'from': high * 0.8, 'color': '#e05d5d'}]
    return {'type': 'gauge', 'entity': entity, 'name': name, 'min': 0, 'max': high, 'needle': True, 'segments': segments}


def saved_card():
    """A markdown card is one grid row high by default and its text is cut: three rows, full width."""
    return {'type': 'markdown', 'content': SAVED, 'grid_options': {'columns': 'full', 'rows': 3}}


def build(zones, plan_card, history_cards, hours):
    weather = [{'type': 'tile', 'entity': e, 'vertical': False} for e in
               ('sensor.outdoor_temperature', 'sensor.outdoor_humidity', 'sensor.wind_speed', 'sensor.direct_solar')]
    overview = {
        'type': 'sections', 'title': 'Overview', 'path': 'overview', 'icon': 'mdi:home-analytics', 'max_columns': 2,
        'badges': [{'type': 'entity', 'entity': e, 'show_name': False} for e in
                   ('sensor.simulated_time', 'sensor.run_in_progress', 'sensor.outdoor_temperature', 'sensor.outdoor_humidity')],
        'sections': [
            {'type': 'grid', 'cards': [heading('Controlled run', 'mdi:robot-outline',
                                               ['sensor.heating_power_controlled', 'sensor.electricity_power_controlled']),
                                       plan_card('controlled')]},
            {'type': 'grid', 'cards': [heading('Baseline run', 'mdi:thermostat-box',
                                               ['sensor.heating_power_baseline', 'sensor.electricity_power_baseline']),
                                       plan_card('baseline')]},
            {'type': 'grid', 'cards': [heading('Now', 'mdi:clock-outline'),
                                       {'type': 'tile', 'entity': 'sensor.simulated_time', 'name': 'Simulated time'},
                                       {'type': 'tile', 'entity': 'sensor.run_in_progress', 'name': 'Run in progress'},
                                       heading('Outdoor', 'mdi:weather-partly-cloudy')] + weather +
                                      [heading('Result', 'mdi:leaf'), saved_card()]},
        ]}

    sections = []
    for z in zones:
        n = z['id'].title()
        sections.append({'type': 'grid', 'cards': [
            heading('{} zone'.format(n), 'mdi:home-thermometer-outline', ['sensor.{}_comfort_controlled'.format(z['id'])]),
            {'type': 'tile', 'entity': 'climate.{}_thermostat'.format(z['id']), 'name': 'Thermostat', 'features': [{'type': 'target-temperature'}],
             'grid_options': {'columns': 'full'}},
            {'type': 'sensor', 'entity': 'sensor.{}_temperature_controlled'.format(z['id']), 'name': 'Controlled', 'graph': 'line', 'detail': 2,
             'hours_to_show': hours, 'grid_options': {'columns': 'full'}},
            {'type': 'sensor', 'entity': 'sensor.{}_temperature_baseline'.format(z['id']), 'name': 'Baseline', 'graph': 'line', 'detail': 2,
             'hours_to_show': hours, 'grid_options': {'columns': 'full'}},
        ]})
    rooms = {'type': 'sections', 'title': 'Rooms', 'path': 'rooms', 'icon': 'mdi:floor-plan', 'max_columns': 4, 'sections': sections}

    energy = {'type': 'sections', 'title': 'Energy', 'path': 'energy', 'icon': 'mdi:lightning-bolt', 'max_columns': 3, 'sections': [
        {'type': 'grid', 'cards': [heading('Heating power', 'mdi:radiator'), gauge('sensor.heating_power_controlled', 'Controlled', 200),
                                   gauge('sensor.heating_power_baseline', 'Baseline', 200)]},
        {'type': 'grid', 'cards': [heading('Electricity power', 'mdi:flash'), gauge('sensor.electricity_power_controlled', 'Controlled', 50),
                                   gauge('sensor.electricity_power_baseline', 'Baseline', 50)]},
        {'type': 'grid', 'cards': [heading('Energy of the run', 'mdi:sigma'), saved_card(),
                                   {'type': 'tile', 'entity': 'sensor.heating_energy_controlled', 'name': 'Heating, controlled'},
                                   {'type': 'tile', 'entity': 'sensor.heating_energy_baseline', 'name': 'Heating, baseline'},
                                   {'type': 'tile', 'entity': 'sensor.electricity_energy_controlled', 'name': 'Electricity, controlled'},
                                   {'type': 'tile', 'entity': 'sensor.electricity_energy_baseline', 'name': 'Electricity, baseline'}]},
    ]}
    history = {'title': 'History', 'path': 'history', 'icon': 'mdi:chart-line', 'cards': history_cards(zones)}
    return [overview, rooms, energy, history]

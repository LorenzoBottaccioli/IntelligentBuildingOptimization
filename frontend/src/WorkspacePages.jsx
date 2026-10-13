import React from 'react';
import WorkspacePage from './WorkspacePage';

const LOGS = {
  id: 'logs',
  label: 'Logs',
  path: 'tree/logs',
  file: 'logs/',
  blurb: 'What your scripts printed, their errors and their restarts. Look here first when something does not work.',
};

const DEVICES = [
  {
    id: 'gateway',
    label: 'gateway.py',
    path: 'edit/devices/gateway.py',
    file: 'devices/gateway.py',
    blurb: 'Your device gateway: step the building with building.py, publish its sensors on your topics, apply commands to its actuators.',
  },
  LOGS,
];

const SUBSCRIBER = [
  {
    id: 'subscriber',
    label: 'subscriber.py',
    path: 'edit/iot/subscriber.py',
    file: 'iot/subscriber.py',
    blurb: 'Subscriber: subscribe to your device topics, clean and check values, store them in InfluxDB with your schema, republish on your topics.',
  },
  LOGS,
];

const DATA = [
  {
    id: 'access',
    label: 'Data access',
    path: 'notebooks/iot/data_access.ipynb',
    file: 'iot/data_access.ipynb',
    blurb: 'Query your database.',
  },
  {
    id: 'signature',
    label: 'Energy signature',
    path: 'notebooks/iot/energy_signature.ipynb',
    file: 'iot/energy_signature.ipynb',
    blurb: 'Energy signature of the baseline.',
  },
];

const CONTROLLER = [
  {
    id: 'controller',
    label: 'controller.py',
    path: 'edit/ai/controller.py',
    file: 'ai/controller.py',
    blurb: 'From an IF-THEN rule up to a trained RL agent.',
  },
  LOGS,
];

const FORECASTING = [
  {
    id: 'forecasting',
    label: 'Forecasting',
    path: 'notebooks/ai/forecasting.ipynb',
    file: 'ai/forecasting.ipynb',
    blurb: 'Forecast with the data you stored.',
  },
];

export const DevicesCode = () => <WorkspacePage files={DEVICES} route="/devices_code" />;
export const SubscriberCode = () => <WorkspacePage files={SUBSCRIBER} route="/subscriber_code" />;
export const DataNotebooks = () => <WorkspacePage files={DATA} route="/data_notebooks" />;
export const ControllerCode = () => <WorkspacePage files={CONTROLLER} route="/controller_code" />;
export const Forecasting = () => <WorkspacePage files={FORECASTING} route="/forecasting" />;

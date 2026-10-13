import React from 'react';
import IframePage from './IframePage';
import { SERVICES } from './api';

export default function Grafana() {
  return <IframePage title="Grafana" src={SERVICES.grafana} />;
}

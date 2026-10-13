import React from 'react';
import WorkspacePage from './WorkspacePage';

const FILES = [
  {
    id: 'training',
    label: 'Agent training',
    path: 'notebooks/ai/AgentTraining.ipynb',
    file: 'ai/AgentTraining.ipynb',
    blurb: 'Train an RL agent on your building. Save the model so your controller can load it.',
  },
];

export default function AgentTraining() {
  return <WorkspacePage files={FILES} route="/agent_training" />;
}

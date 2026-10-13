// The role of an FMU output, shown as both choices side by side so the student
// sees what it is and what else it could be -- the same control when adding an
// output and on the outputs already added.
import React from 'react';
import './FmuRole.css';

const ROLES = [
  ['observation', 'Observation', 'The controller reads it'],
  ['reward', 'Reward', 'The controller is scored on it'],
];

export default function RoleSwitch({ value, onChange, disabled, compact }) {
  return (
    <span className={`roleswitch${compact ? ' roleswitch--compact' : ''}${value ? '' : ' is-unset'}`}
      role="radiogroup" aria-label="Role in the controller">
      {ROLES.map(([id, label, hint]) => (
        <button key={id} type="button" role="radio" aria-checked={value === id} title={hint}
          className={value === id ? 'is-on' : undefined} disabled={disabled}
          onClick={() => value !== id && onChange(id)}>
          {label}
        </button>
      ))}
    </span>
  );
}

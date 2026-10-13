import React, { useState, useEffect } from 'react';
import { api } from './api';

function ModalComponent({ isOpen, closeModal, type, onSubmitSuccess, refreshData, data }) {
  const [name, setName] = useState('');
  const [outputVariableOrOutputMeterIndexKeyName, setOutputVariableOrOutputMeterIndexKeyName] = useState('');
  const [outputVariableOrOutputMeterName, setOutputVariableOrOutputMeterName] = useState('');
  const [actuatedComponentUniqueName, setActuatedComponentUniqueName] = useState('');
  const [actuatedComponentType, setActuatedComponentType] = useState('');
  const [actuatedComponentControlType, setActuatedComponentControlType] = useState('');
  const [fmuVariableName, setFmuVariableName] = useState('');
  const [initialValue, setInitialValue] = useState('');
  const [outputVariableIndexKeyName, setOutputVariableIndexKeyName] = useState('');
  const [outputVariableName, setOutputVariableName] = useState('');
  const [scheduleName, setScheduleName] = useState('');
  const [scheduleTypeLimitsNames, setScheduleTypeLimitsNames] = useState('');
  const [energyPlusModelCallingPoint, setEnergyPlusModelCallingPoint] = useState('');
  const [programNames, setProgramNames] = useState([]);
  const [newProgramName, setNewProgramName] = useState('');
  const [programLine, setProgramLine] = useState('');
  const [programLines, setProgramLines] = useState([]);
  const [keyValue, setKeyValue] = useState('');
  const [oVariableName, setOVariableName] = useState('');
  const [reportingFrequency, setReportingFrequency] = useState('');
  const [addType, setAddType] = useState('output_variable');
  const [nameType, setNameType] = useState('custom_name');

  const availableExpressions = ['(', ')', '+', '-', '*', '/', '^', '==', '>', '>=', '<', '<=', '&&', '||', '=', '.'];
  const availableStatements = ['RUN', 'RETURN', 'SET', 'IF', 'ELSEIF', 'ELSE', 'ENDIF', 'WHILE', 'ENDWHILE'];

  const reportingFrequencyOptions = ['Detailed', 'Timestep', 'Hourly', 'Daily', 'Runperiod', 'Environment', 'Annual'];

  const energyPlusModelCallingPointOptions = [
    'BeginNewEnvironment', 'BeginZoneTimestepBeforeSetCurrentWeather', 'AfterNewEnvironmentWarmUpIsComplete',
    'BeginZoneTimestepBeforeInitHeatBalance', 'BeginZoneTimestepAfterInitHeatBalance',
    'BeginTimestepBeforePredictor', 'AfterPredictorBeforeHVACManagers',
    'AfterPredictorAfterHVACManagers', 'InsideHVACSystemIterationLoop',
    'EndOfZoneTimestepBeforeZoneReporting', 'EndOfZoneTimestepAfterZoneReporting',
    'EndOfSystemTimestepBeforeHVACReporting', 'EndOfSystemTimestepAfterHVACReporting',
    'EndOfZoneSizing', 'EndOfSystemSizing', 'AfterComponentInputReadIn',
    'UserDefinedComponentModel', 'UnitarySystemSizing'
  ];

  const {
    edd_actuators,
    rdd_variables,
    existing_schedule_type_limits,
    current_ems_programs,
    current_ems_actuators,
    current_ems_sensors,
    current_fmu_to_variables,
    existing_schedule_names,
    zone_names
  } = data;

  useEffect(() => {
    if (isOpen) {
      setName('');
      setOutputVariableOrOutputMeterIndexKeyName('');
      setOutputVariableOrOutputMeterName('');
      setActuatedComponentUniqueName('');
      setActuatedComponentType('');
      setActuatedComponentControlType('');
      setFmuVariableName('');
      setInitialValue('');
      setOutputVariableIndexKeyName('');
      setOutputVariableName('');
      setScheduleName('');
      setScheduleTypeLimitsNames('');
      setEnergyPlusModelCallingPoint('');
      setProgramNames([]);
      setNewProgramName('');
      setProgramLine('');
      setProgramLines([]);
      setKeyValue('');
      setOVariableName('');
      setReportingFrequency('');
      setAddType('output_variable');
      setNameType('custom_name');
    }
  }, [isOpen]);

  const endpointMap = {
    'Output:Variable': api('/model_editor/add_output_variable'),
    'EnergyManagementSystem:Sensor': api('/model_editor/add_ems_sensor'),
    'EnergyManagementSystem:Actuator': api('/model_editor/add_ems_actuator'),
    'EnergyManagementSystem:Program': api('/model_editor/add_ems_program'),
    'EnergyManagementSystem:ProgramCallingManager': api('/model_editor/add_ems_program_calling_manager'),
    'ExternalInterface:FunctionalMockupUnitExport:To:Actuator': api('/model_editor/add_fmu_actuator'),
    'ExternalInterface:FunctionalMockupUnitExport:From:Variable': api('/model_editor/add_fmu_from_variable'),
    'ExternalInterface:FunctionalMockupUnitExport:To:Variable': api('/model_editor/add_fmu_to_variable'),
    'ExternalInterface:FunctionalMockupUnitExport:To:Schedule': api('/model_editor/add_fmu_schedule')
  };

  const handleActuatorSelect = (e) => {
    const [uniqueName, type, controlType] = e.target.value.split('-');
    const selectedActuator = edd_actuators.find(
      actuator =>
        actuator.componentUniqueName === uniqueName &&
        actuator.componentType === type &&
        actuator.controlType === controlType
    );

    if (selectedActuator) {
      setActuatedComponentUniqueName(selectedActuator.componentUniqueName);
      setActuatedComponentType(selectedActuator.componentType);
      setActuatedComponentControlType(selectedActuator.controlType);
    } else {
      setActuatedComponentUniqueName('');
      setActuatedComponentType('');
      setActuatedComponentControlType('');
    }
  };

  const addSelectedProgramName = () => {
    if (newProgramName && !programNames.includes(newProgramName)) {
      setProgramNames((prevNames) => [...prevNames, newProgramName]);
    }
  };

  const handleSelectedProgramNameChange = (e) => {
    setNewProgramName(e.target.value);
  };

  const addProgramLine = () => {
    if (programLine.trim()) {
      setProgramLines((prevLines) => [...prevLines, programLine.trim()]);
      setProgramLine('');
    }
  };

  const insertIntoLine = (item) => {
    setProgramLine((prev) => `${prev} ${item}`.trim());
  };

  const handleSubmit = async () => {
    let payload = {};

    switch (type) {
      case 'Output:Variable':
        payload = {
          keyValue,
          oVariableName,
          reportingFrequency,
          addType,
          name,
          fmuVariableName,
          scheduleName
        };
        break;
      case 'EnergyManagementSystem:Sensor':
        payload = {
          name,
          outputVariableOrOutputMeterIndexKeyName,
          outputVariableOrOutputMeterName
        };
        break;
      case 'EnergyManagementSystem:Actuator':
        payload = {
          name,
          actuatedComponentUniqueName,
          actuatedComponentType,
          actuatedComponentControlType
        };
        break;
      case 'EnergyManagementSystem:Program':
        payload = {
          name,
          programLines
        };
        break;
      case 'EnergyManagementSystem:ProgramCallingManager':
        payload = {
          name,
          energyPlusModelCallingPoint,
          programNames
        };
        break;
      case 'ExternalInterface:FunctionalMockupUnitExport:To:Actuator':
        payload = {
          name,
          actuatedComponentUniqueName,
          actuatedComponentType,
          actuatedComponentControlType,
          fmuVariableName,
          initialValue
        };
        break;
      case 'ExternalInterface:FunctionalMockupUnitExport:From:Variable':
        payload = {
          outputVariableIndexKeyName,
          outputVariableName,
          fmuVariableName
        };
        break;
      case 'ExternalInterface:FunctionalMockupUnitExport:To:Variable':
        payload = {
          name,
          fmuVariableName,
          initialValue
        };
        break;
      case 'ExternalInterface:FunctionalMockupUnitExport:To:Schedule':
        payload = {
          scheduleName,
          scheduleTypeLimitsNames,
          fmuVariableName,
          initialValue,
          nameType
        };
        break;
      default:
        console.warn(`Unrecognized type: ${type}`);
        return;
    }

    const endpoint = endpointMap[type];

    if (endpoint) {
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (response.ok) {
          onSubmitSuccess(result);
          refreshData(result);
          closeModal();
          alert(result.message);
        } else {
          alert(result.error || 'Failed to add the object');
        }
      } catch (error) {
        console.error('Error while adding object:', error);
        alert('Failed to add the object due to a network error');
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.5)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center'
      }}
    >
      <div
        style={{
          background: 'white',
          padding: 30,
          borderRadius: 8,
          maxWidth: 1100,
          width: '100%',
          display: 'flex'
        }}
      >
        {/* Formulario a la izquierda */}
        <div style={{ flex: 2, paddingRight: '20px' }}>
          <button
            onClick={closeModal}
            style={{
              position: 'absolute',
              top: 10,
              right: 10,
              backgroundColor: 'transparent',
              border: 'none',
              fontSize: 20,
              cursor: 'pointer'
            }}
          >
            &times;
          </button>
          <h3>Object Adder {type}</h3>

          {type === 'EnergyManagementSystem:Actuator' && (
            <>
              <label>
                Name:
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Select Actuator:
                <select
                  value={`${actuatedComponentUniqueName}-${actuatedComponentType}-${actuatedComponentControlType}`}
                  onChange={handleActuatorSelect}
                  required
                >
                  <option value="">Select an Actuator</option>
                  {edd_actuators.map((actuator) => (
                    <option
                      key={actuator.id}
                      value={`${actuator.componentUniqueName}-${actuator.componentType}-${actuator.controlType}`}
                    >
                      {actuator.componentUniqueName} - {actuator.componentType} -{' '}
                      {actuator.controlType}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`EnergyManagementSystem:Actuator,
    ${name || ''},    !- Name
    ${actuatedComponentUniqueName || ''},    !- Actuated Component Unique Name
    ${actuatedComponentType || ''},    !- Actuated Component Type
    ${actuatedComponentControlType || ''};    !- Actuated Component Control Type`}
              </pre>
            </>
          )}

          {type === 'EnergyManagementSystem:Sensor' && (
            <>
              <label>
                Name:
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Output Variable or Meter Index Key Name:
                <input
                  type="text"
                  value={outputVariableOrOutputMeterIndexKeyName}
                  onChange={(e) =>
                    setOutputVariableOrOutputMeterIndexKeyName(e.target.value)
                  }
                  required
                />
              </label>
              <br />
              <label>
                Select Variable:
                <select
                  value={outputVariableOrOutputMeterName}
                  onChange={(e) => setOutputVariableOrOutputMeterName(e.target.value)}
                  required
                >
                  <option value="">Select a Variable</option>
                  {rdd_variables.map((variable) => (
                    <option key={variable.id} value={variable.variableName}>
                      {variable.varType} - {variable.variableName}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`EnergyManagementSystem:Sensor,
    ${name || ''},    !- Name
    ${outputVariableOrOutputMeterIndexKeyName || ''},    !- OutputVariable or OutputMeter Index Key Name
    ${outputVariableOrOutputMeterName || ''};    !- OutputVariable or OutputMeter Name`}
              </pre>
            </>
          )}

          {type === 'ExternalInterface:FunctionalMockupUnitExport:From:Variable' && (
            <>
              <label>
                Output Variable Index Key Name:
                <input
                  type="text"
                  value={outputVariableIndexKeyName}
                  onChange={(e) => setOutputVariableIndexKeyName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Select Variable:
                <select
                  value={outputVariableName}
                  onChange={(e) => setOutputVariableName(e.target.value)}
                  required
                >
                  <option value="">Select a Variable</option>
                  {rdd_variables.map((variable) => (
                    <option key={variable.id} value={variable.variableName}>
                      {variable.varType} - {variable.variableName}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <label>
                FMU Variable Name:
                <input
                  type="text"
                  value={fmuVariableName}
                  onChange={(e) => setFmuVariableName(e.target.value)}
                  required
                />
              </label>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`ExternalInterface:FunctionalMockupUnitExport:From:Variable,
    ${outputVariableIndexKeyName || ''},    !- Output:Variable Index Key Name
    ${outputVariableName || ''},    !- Output:Variable Name
    ${fmuVariableName || ''};    !- FMU Variable Name`}
              </pre>
            </>
          )}

          {type === 'Output:Variable' && (
            <>
              <label>
                Key Value:
                <input
                  type="text"
                  value={keyValue}
                  onChange={(e) => setKeyValue(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Select Variable:
                <select
                  value={oVariableName}
                  onChange={(e) => setOVariableName(e.target.value)}
                  required
                >
                  <option value="">Select a Variable</option>
                  {rdd_variables.map((variable) => (
                    <option key={variable.id} value={variable.variableName}>
                      {variable.varType} - {variable.variableName}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <label>
                Reporting Frequency:
                <select
                  value={reportingFrequency}
                  onChange={(e) => setReportingFrequency(e.target.value)}
                  required
                >
                  <option value="">Select a Reporting Frequency</option>
                  {reportingFrequencyOptions.map((frequency) => (
                    <option key={frequency} value={frequency}>
                      {frequency}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <label>
                Schedule Name:
                <select
                  value={scheduleName}
                  onChange={(e) => setScheduleName(e.target.value)}
                  required
                >
                  <option value="">No Schedule</option>
                  {existing_schedule_names.map((schedule) => (
                    <option key={schedule.id} value={schedule.scheduleName}>
                      {schedule.scheduleName}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <label>
                <input
                  type="radio"
                  name="addType"
                  value="output_variable"
                  checked={addType === 'output_variable'}
                  onChange={(e) => setAddType(e.target.value)}
                />
                Only Output Variable
              </label>
              <br />
              <label>
                <input
                  type="radio"
                  name="addType"
                  value="output_variable_with_ems_sensor"
                  checked={addType === 'output_variable_with_ems_sensor'}
                  onChange={(e) => setAddType(e.target.value)}
                />
                Output Variable with EMS Sensor
              </label>
              <br />
              {addType === 'output_variable_with_ems_sensor' && (
                <>
                  <label>
                    EMS Sensor Name:
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />
                  </label>
                  <br />
                </>
              )}
              <label>
                <input
                  type="radio"
                  name="addType"
                  value="output_variable_with_external_from_variable"
                  checked={addType === 'output_variable_with_external_from_variable'}
                  onChange={(e) => setAddType(e.target.value)}
                />
                Output Variable with External From Variable
              </label>
              <br />
              {addType === 'output_variable_with_external_from_variable' && (
                <>
                  <label>
                    FMU Variable Name:
                    <input
                      type="text"
                      value={fmuVariableName}
                      onChange={(e) => setFmuVariableName(e.target.value)}
                      required
                    />
                  </label>
                  <br />
                </>
              )}
              <label>
                <input
                  type="radio"
                  name="addType"
                  value="output_variable_with_both"
                  checked={addType === 'output_variable_with_both'}
                  onChange={(e) => setAddType(e.target.value)}
                />
                Output Variable with Both EMS Sensor and External From Variable
              </label>
              <br />
              {addType === 'output_variable_with_both' && (
                <>
                  <label>
                    EMS Sensor Name:
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                    />
                  </label>
                  <br />
                  <label>
                    FMU Variable Name:
                    <input
                      type="text"
                      value={fmuVariableName}
                      onChange={(e) => setFmuVariableName(e.target.value)}
                      required
                    />
                  </label>
                  <br />
                </>
              )}
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`Output:Variable,
    ${keyValue || ''},    !- Key Value
    ${oVariableName || ''},    !- Variable Name
    ${reportingFrequency || ''};    !- Reporting Frequency`}
              </pre>
            </>
          )}

          {type === 'ExternalInterface:FunctionalMockupUnitExport:To:Variable' && (
            <>
              <label>
                Name:
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                FMU Variable Name:
                <input
                  type="text"
                  value={fmuVariableName}
                  onChange={(e) => setFmuVariableName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Initial Value:
                <input
                  type="text"
                  value={initialValue}
                  onChange={(e) => setInitialValue(e.target.value)}
                  required
                />
              </label>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`ExternalInterface:FunctionalMockupUnitExport:To:Variable,
    ${name || ''},    !- Name
    ${fmuVariableName || ''},    !- FMU Variable Name
    ${initialValue || ''};    !- Initial Value`}
              </pre>
            </>
          )}

          {type === 'ExternalInterface:FunctionalMockupUnitExport:To:Actuator' && (
            <>
              <label>
                Name:
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Select Actuator:
                <select
                  value={`${actuatedComponentUniqueName}-${actuatedComponentType}-${actuatedComponentControlType}`}
                  onChange={handleActuatorSelect}
                  required
                >
                  <option value="">Select an Actuator</option>
                  {edd_actuators.map((actuator) => (
                    <option
                      key={actuator.id}
                      value={`${actuator.componentUniqueName}-${actuator.componentType}-${actuator.controlType}`}
                    >
                      {actuator.componentUniqueName} - {actuator.componentType} -{' '}
                      {actuator.controlType}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <label>
                FMU Variable Name:
                <input
                  type="text"
                  value={fmuVariableName}
                  onChange={(e) => setFmuVariableName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Initial Value:
                <input
                  type="text"
                  value={initialValue}
                  onChange={(e) => setInitialValue(e.target.value)}
                  required
                />
              </label>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`ExternalInterface:FunctionalMockupUnitExport:To:Actuator,
    ${name || ''},    !- Name
    ${actuatedComponentUniqueName || ''},    !- Actuated Component Unique Name
    ${actuatedComponentType || ''},    !- Actuated Component Type
    ${actuatedComponentControlType || ''},    !- Actuated Component Control Type
    ${fmuVariableName || ''},    !- FMU Variable Name
    ${initialValue || ''};    !- Initial Value`}
              </pre>
            </>
          )}

          {type === 'ExternalInterface:FunctionalMockupUnitExport:To:Schedule' && (
            <>
              <label>
                <input
                  type="radio"
                  name="nameType"
                  value="existing_schedule"
                  checked={nameType === 'existing_schedule'}
                  onChange={(e) => setNameType(e.target.value)}
                  required
                />
                From an Existing Schedule
              </label>
              <br />
              <label>
                <input
                  type="radio"
                  name="nameType"
                  value="custom_name"
                  checked={nameType === 'custom_name'}
                  onChange={(e) => setNameType(e.target.value)}
                  required
                />
                Create a Custom Name
              </label>
              <br />
              {nameType === 'custom_name' && (
                <>
                  <label>
                    Schedule Name:
                    <input
                      type="text"
                      value={scheduleName}
                      onChange={(e) => setScheduleName(e.target.value)}
                      required
                    />
                  </label>
                  <br />
                </>
              )}
              {nameType === 'existing_schedule' && (
                <>
                  <label>
                    Schedule Name:
                    <select
                      value={scheduleName}
                      onChange={(e) => setScheduleName(e.target.value)}
                      required
                    >
                      <option value="">Select Schedule Name</option>
                      {existing_schedule_names.map((schedule) => (
                        <option key={schedule.id} value={schedule.scheduleName}>
                          {schedule.scheduleName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <br />
                </>
              )}
              <label>
                Select Schedule Type Limits Names:
                <select
                  value={scheduleTypeLimitsNames}
                  onChange={(e) => setScheduleTypeLimitsNames(e.target.value)}
                  required
                >
                  <option value="">Select Limits</option>
                  {existing_schedule_type_limits.map((limit) => (
                    <option key={limit.id} value={limit.name}>
                      {limit.name}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <label>
                FMU Variable Name:
                <input
                  type="text"
                  value={fmuVariableName}
                  onChange={(e) => setFmuVariableName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                Initial Value:
                <input
                  type="text"
                  value={initialValue}
                  onChange={(e) => setInitialValue(e.target.value)}
                  required
                />
              </label>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`ExternalInterface:FunctionalMockupUnitExport:To:Schedule,
    ${scheduleName || ''},    !- Schedule Name
    ${scheduleTypeLimitsNames || ''},    !- Schedule Type Limits Names
    ${fmuVariableName || ''},    !- FMU Variable Name
    ${initialValue || ''};    !- Initial Value`}
              </pre>
            </>
          )}

          {type === 'EnergyManagementSystem:ProgramCallingManager' && (
            <>
              <label>
                Name:
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                EnergyPlus Model Calling Point:
                <select
                  value={energyPlusModelCallingPoint}
                  onChange={(e) => setEnergyPlusModelCallingPoint(e.target.value)}
                  required
                >
                  <option value="">Select a Calling Point</option>
                  {energyPlusModelCallingPointOptions.map((point) => (
                    <option key={point} value={point}>
                      {point}
                    </option>
                  ))}
                </select>
              </label>
              <br />
              <label>
                Select Program Name to Add:
                <select
                  value={newProgramName}
                  onChange={handleSelectedProgramNameChange}
                  required
                >
                  <option value="">Select a Program Name</option>
                  {current_ems_programs.map((program) => (
                    <option key={program.id} value={program.name}>
                      {program.name}
                    </option>
                  ))}
                </select>
              </label>
              <button onClick={addSelectedProgramName}>Add Program Name</button>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`EnergyManagementSystem:ProgramCallingManager,
    ${name || ''},    !- Name
    ${energyPlusModelCallingPoint || ''},    !- EnergyPlus Model Calling Point
    ${programNames
      .map((programName, index) => `${programName},    !- Program Name ${index + 1}`)
      .join('\n    ')};`}
              </pre>
            </>
          )}

          {type === 'EnergyManagementSystem:Program' && (
            <>
              <label>
                Program Name:
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <br />
              <label>
                New Program Line:
                <input
                  type="text"
                  style={{ width: '700px' }}
                  value={programLine}
                  onChange={(e) => setProgramLine(e.target.value)}
                  required
                />
              </label>
              <button onClick={addProgramLine}>Add Line</button>
              <ul>
                {programLines.map((line, index) => (
                  <li key={index}>{line}</li>
                ))}
              </ul>
              <br />
              <h4>Select Available Sensors, Actuators, FMU Variables, Programs, Statements, and Expressions:</h4>
              {current_ems_sensors && (
                <>
                  <label>Available Sensors:</label>
                  <select onChange={(e) => insertIntoLine(e.target.value)} required>
                    <option value="">Select a Sensor</option>
                    {current_ems_sensors.map((sensor) => (
                      <option key={sensor.id} value={sensor.name}>
                        {sensor.name}
                      </option>
                    ))}
                  </select>
                  <br />
                </>
              )}
              {current_ems_actuators && (
                <>
                  <label>Available Actuators:</label>
                  <select onChange={(e) => insertIntoLine(e.target.value)} required>
                    <option value="">Select an Actuator</option>
                    {current_ems_actuators.map((actuator) => (
                      <option key={actuator.id} value={actuator.name}>
                        {actuator.name}
                      </option>
                    ))}
                  </select>
                  <br />
                </>
              )}
              {current_fmu_to_variables && (
                <>
                  <label>Available FMU To Variables:</label>
                  <select onChange={(e) => insertIntoLine(e.target.value)} required>
                    <option value="">Select an FMU Variable</option>
                    {current_fmu_to_variables.map((variable) => (
                      <option key={variable.id} value={variable.name}>

                        {variable.name}
                      </option>
                    ))}
                  </select>
                  <br />
                </>
              )}
              {current_ems_programs && (
                <>
                  <label>Available Program Names:</label>
                  <select onChange={(e) => insertIntoLine(e.target.value)} required>
                    <option value="">Select a Program Name</option>
                    {current_ems_programs.map((program) => (
                      <option key={program.id} value={program.name}>
                        {program.name}
                      </option>
                    ))}
                  </select>
                  <br />
                </>
              )}
              <label>Available Statements:</label>
              <select onChange={(e) => insertIntoLine(e.target.value)} required>
                <option value="">Select a Statement</option>
                {availableStatements.map((statement) => (
                  <option key={statement} value={statement}>
                    {statement}
                  </option>
                ))}
              </select>
              <br />
              <label>Available Expressions:</label>
              <select onChange={(e) => insertIntoLine(e.target.value)} required>
                <option value="">Select an Expression</option>
                {availableExpressions.map((expression) => (
                  <option key={expression} value={expression}>
                    {expression}
                  </option>
                ))}
              </select>
              <br />
              <h4>Preview:</h4>
              <pre
                style={{
                  backgroundColor: '#f7f7f7',
                  padding: '10px',
                  borderRadius: '5px'
                }}
              >
                {`EnergyManagementSystem:Program,
      ${name || ''},    !- Name
      ${programLines
        .map((line, index) => `${line},    !- Program Line ${index + 1}`)
        .join('\n    ')};`}
              </pre>
            </>
          )}

          {/* Botones Add / Cancel dentro del white box */}
          <br />
          <button onClick={handleSubmit}>Add</button>
          <button onClick={closeModal} style={{ marginLeft: '10px' }}>
            Cancel
          </button>
        </div>

        {/* Lista de zone_names a la derecha para ciertos tipos */}
        {(type === 'Output:Variable' ||
          type === 'EnergyManagementSystem:Sensor' ||
          type === 'ExternalInterface:FunctionalMockupUnitExport:From:Variable') && (
          <div
            style={{
              flex: 1,
              marginLeft: '20px',
              borderLeft: '1px solid #ccc',
              paddingLeft: '20px'
            }}
          >
            <h4>Zone Names</h4>
            <ul style={{ maxHeight: '300px', overflowY: 'auto', paddingLeft: '20px' }}>
              {zone_names && zone_names.length > 0 ? (
                zone_names.map((zone, idx) => <li key={idx}>{zone}</li>)
              ) : (
                <li>No zones available</li>
              )}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default ModalComponent;

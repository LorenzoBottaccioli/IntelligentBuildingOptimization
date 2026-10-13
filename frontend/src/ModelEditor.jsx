import React, { useContext, useState, useEffect, useCallback } from 'react';
import IdfObjectGrid from './IdfObjectGrid';
import ModalComponent from './ModalComponent';
import MonitoringPanel from './MonitoringPanel';
import EmsPrograms from './EmsPrograms';
import { AppContext } from './AppContext';

// Raw EnergyPlus classes, kept behind the advanced view.
const GRID_TITLES = {
  'Output:Variable': 'current_output_variables',
  'Output:Meter': 'current_output_meters',
  'EnergyManagementSystem:Actuator': 'current_ems_actuators',
  'EnergyManagementSystem:Sensor': 'current_ems_sensors',
  'EnergyManagementSystem:OutputVariable': 'current_ems_output_variables',
  'EnergyManagementSystem:Program': 'current_ems_programs',
  'EnergyManagementSystem:ProgramCallingManager': 'current_ems_program_calling_managers',
  'ExternalInterface:FunctionalMockupUnitExport:From:Variable': 'current_fmu_from_variables',
  'ExternalInterface:FunctionalMockupUnitExport:To:Actuator': 'current_fmu_actuators',
  'ExternalInterface:FunctionalMockupUnitExport:To:Variable': 'current_fmu_to_variables',
  'ExternalInterface:FunctionalMockupUnitExport:To:Schedule': 'current_fmu_schedules',
};

/** Title, one line of purpose, and the model-level actions every step offers. */
function StepHeader({ title, children, actions }) {
  const { filesUploaded, revertToOriginal } = useContext(AppContext);
  const handleRevert = async () => {
    if (!window.confirm('Discard every change and go back to the uploaded IDF?')) return;
    try {
      await revertToOriginal();
      alert('Model restored.');
    } catch (e) {
      alert(`Restore failed: ${e?.response?.data?.details || e.message}`);
    }
  };
  return (
    <header className="editor__bar">
      <div>
        <h1>{title}</h1>
        <p className="editor__subtitle">{children}</p>
      </div>
      <div className="editor__bar-actions">
        {actions}
        <button type="button" onClick={handleRevert} disabled={!filesUploaded}>
          Restore original
        </button>
      </div>
    </header>
  );
}

function useObjects() {
  const { idfObjects, fetchIdfObjects } = useContext(AppContext);
  useEffect(() => {
    if (!idfObjects) fetchIdfObjects();
  }, [idfObjects, fetchIdfObjects]);
}

/** Building & devices, step 1: what the controller reads and what it can act on. */
export function SensorsActuators() {
  const { idfObjects, fetchIdfObjects, filesUploaded, removeObject } = useContext(AppContext);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalType, setModalType] = useState('');
  const [selectedSection, setSelectedSection] = useState('');
  const [advanced, setAdvanced] = useState(false);
  useObjects();

  const refreshData = useCallback(async () => {
    try {
      await fetchIdfObjects();
    } catch (error) {
      console.error('Error refreshing data:', error);
    }
  }, [fetchIdfObjects]);

  return (
    <div className="editor">
      <StepHeader
        title="Sensors & actuators"
        actions={(
          <label className="editor__toggle">
            <input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />
            Advanced: raw IDF objects
          </label>
        )}
      >
        Instrument the building: choose what the controller reads (observations and rewards) and what it can act on
        (schedules and actuators, each with its range). The platform writes the EnergyPlus objects behind each choice.
      </StepHeader>

      {!advanced ? <MonitoringPanel /> : (
        <div className="editor__advanced">
          <aside className="editor__nav">
            <h2>Objects</h2>
            <ul>
              {Object.keys(GRID_TITLES).map((section) => (
                <li
                  key={section}
                  className={section === selectedSection ? 'is-active' : undefined}
                  onClick={() => setSelectedSection(section)}
                >
                  {section}
                </li>
              ))}
            </ul>
          </aside>

          <div className="editor__detail">
            {!filesUploaded ? (
              <p className="muted">No IDF uploaded.</p>
            ) : selectedSection ? (
              <IdfObjectGrid
                idfObjects={idfObjects}
                openModal={(type) => {
                  setModalType(type);
                  setIsModalOpen(true);
                }}
                section={selectedSection}
                refreshData={refreshData}
                removeObject={removeObject}
              />
            ) : (
              <p className="muted">Choose an object type.</p>
            )}

            <ModalComponent
              isOpen={isModalOpen}
              closeModal={() => setIsModalOpen(false)}
              type={modalType}
              onSubmitSuccess={refreshData}
              refreshData={refreshData}
              data={idfObjects}
            />
          </div>
        </div>
      )}
    </div>
  );
}

/** Building & devices, step 2: control logic that runs inside the model. */
export function EmsProgramsPage() {
  useObjects();
  return (
    <div className="editor">
      <StepHeader title="EMS programs">
        Control logic that runs inside EnergyPlus: programs, the variables they use and when they are called.
        Optional: the model&apos;s own EMS is listed here too.
      </StepHeader>
      <EmsPrograms />
    </div>
  );
}

import React, { createContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { api } from './api';

const AppContext = createContext();

const AppProvider = ({ children }) => {
  const [idfObjects, setIdfObjects] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState({ idf: '', epw: '' });
  const [filesUploaded, setFilesUploaded] = useState(false);
  // Bumped on every upload and every reset: pages holding choices about the
  // model (Problem definition) start over when it changes, even when the
  // flag above stays true from one model to the next.
  const [modelId, setModelId] = useState(0);
  const [scheduleTypeLimits, setScheduleTypeLimits] = useState({});
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  // Bumped when a whole workspace is swapped (new / open / reset session):
  // embedded notebooks remount with it.
  const [sessionKey, setSessionKey] = useState(0);

  // What is loaded is what the backend holds in uploads/, not what this browser
  // remembers: a first start is empty, and a model stays until Reset Session.
  // The backend may still be starting (after a rebuild): keep asking, and once it
  // answers drop whatever objects were fetched in the meantime so pages re-read.
  useEffect(() => {
    let timer = null;
    let tries = 0;
    const ask = () => axios
      .get(api('/model_editor/loaded_files'))
      .then(({ data }) => {
        if (data.idf) {
          setUploadedFiles({ idf: data.idf, epw: data.epw });
          setFilesUploaded(true);
        }
        if (tries > 0) setIdfObjects(null);
      })
      .catch((error) => {
        tries += 1;
        if (tries === 1) console.error('Backend not reachable yet, retrying:', error.message);
        if (tries < 60) timer = setTimeout(ask, 2000);
      });
    ask();
    return () => clearTimeout(timer);
  }, []);

  const fetchIdfObjects = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(api('/model_editor/get_objects'));
      setIdfObjects(data);

      const limits = {};
      (data.existing_schedule_type_limits || []).forEach((limit) => {
        limits[limit.name] = {
          min: parseFloat(limit.lowerLimitValue),
          max: parseFloat(limit.upperLimitValue),
        };
      });
      setScheduleTypeLimits(limits);
    } catch (error) {
      console.error('Error fetching objects:', error);
      setIdfObjects({});
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * The backend swapped the workspace (new / open / reset session): read what
   * it holds now and make every page start over from it.
   */
  const reloadWorkspace = useCallback(async () => {
    let data = {};
    try {
      data = (await axios.get(api('/model_editor/loaded_files'))).data || {};
    } catch (error) {
      console.error('Error reading the loaded files:', error);
    }
    if (data.idf) {
      setUploadedFiles({ idf: data.idf, epw: data.epw });
      setFilesUploaded(true);
    } else {
      setUploadedFiles({ idf: '', epw: '' });
      setFilesUploaded(false);
      localStorage.removeItem('uploadedFiles');
    }
    setIdfObjects('');
    setScheduleTypeLimits({});
    setModelId((n) => n + 1);
    setSessionKey((n) => n + 1);
  }, []);

  const resetSession = async () => {
    try {
      await axios.delete(api('/model_editor/reset_session'));
      await reloadWorkspace();
    } catch (error) {
      console.error('Error resetting session:', error);
      alert('Failed to reset session');
    }
  };

  /** Throw away every edit but keep the uploaded model loaded. */
  const revertToOriginal = async () => {
    const { data } = await axios.post(api('/model_editor/revert_to_original'));
    await fetchIdfObjects();
    return data;
  };

  const updateUploadedFiles = (files) => {
    setUploadedFiles(files);
    setFilesUploaded(true);
    setModelId((n) => n + 1);
    localStorage.setItem('uploadedFiles', JSON.stringify(files));
    fetchIdfObjects();
  };

  /** The session weather file changed (Weather section): the model and the design problem stay as they are. */
  const updateWeatherFile = (epw) => {
    setUploadedFiles((files) => {
      const next = { ...files, epw };
      localStorage.setItem('uploadedFiles', JSON.stringify(next));
      return next;
    });
  };

  const removeObject = async (url, data) => {
    try {
      await axios.delete(url, { data });
      fetchIdfObjects();
    } catch (error) {
      console.error('Error removing object:', error);
      alert('Failed to remove object');
    }
  };

  /**
   * Export one quantity to the FMU. The backend builds the whole EMS chain
   * (sensor -> EMS output variable -> Output:Variable -> FMU export) behind this.
   */
  const monitorQuantity = async (payload) => {
    const { data } = await axios.post(api('/model_editor/add_monitored_quantity'), payload);
    await fetchIdfObjects();
    return data;
  };

  const unmonitorQuantity = async (name) => {
    const { data } = await axios.delete(api('/model_editor/remove_monitored_quantity'), {
      data: { name },
    });
    await fetchIdfObjects();
    return data;
  };

  const addControlledActuator = async (payload) => {
    const { data } = await axios.post(api('/model_editor/add_controlled_actuator'), payload);
    await fetchIdfObjects();
    return data;
  };

  const removeControlledActuator = async (name) => {
    const { data } = await axios.delete(api('/model_editor/remove_controlled_actuator'), {
      data: { name },
    });
    await fetchIdfObjects();
    return data;
  };

  // EMS programs: the programs a student writes, the variables they use, when they run.
  const fetchEmsPrograms = async () => (await axios.get(api('/model_editor/ems_programs'))).data;

  const checkEmsProgram = async (lines) =>
    (await axios.post(api('/model_editor/check_ems_program'), { lines })).data;

  const saveEmsProgram = async (payload) => {
    const { data } = await axios.post(api('/model_editor/save_ems_program'), payload);
    await fetchIdfObjects();
    return data;
  };

  const removeEmsProgram = async (name) => {
    const { data } = await axios.delete(api('/model_editor/remove_ems_program'), { data: { name } });
    await fetchIdfObjects();
    return data;
  };

  const saveEmsManager = async (payload) => {
    const { data } = await axios.post(api('/model_editor/save_ems_manager'), payload);
    await fetchIdfObjects();
    return data;
  };

  const removeEmsManager = async (name) => {
    const { data } = await axios.delete(api('/model_editor/remove_ems_manager'), { data: { name } });
    await fetchIdfObjects();
    return data;
  };

  // The model's own EMS, all of it or one calling manager, on or off.
  const setModelEms = async (enabled, name) => {
    const { data } = await axios.post(api('/model_editor/set_model_ems'), { enabled, name });
    await fetchIdfObjects();
    return data;
  };

  const addEmsVariable = async (payload) => {
    const { data } = await axios.post(api('/model_editor/add_ems_variable'), payload);
    await fetchIdfObjects();
    return data;
  };

  const removeEmsVariable = async (kind, name) => {
    const { data } = await axios.delete(api('/model_editor/remove_ems_variable'), { data: { kind, name } });
    await fetchIdfObjects();
    return data;
  };

  // Direct mode: no EMS object at all. A report variable is read as it is; a component
  // or a schedule is written by the FMU itself.
  const addDirectVariable = async (payload) => {
    const { data } = await axios.post(api('/model_editor/add_direct_variable'), payload);
    await fetchIdfObjects();
    return data;
  };

  const removeDirectVariable = async (fmuVariableName) => {
    const { data } = await axios.delete(api('/model_editor/remove_direct_variable'), {
      data: { fmuVariableName },
    });
    await fetchIdfObjects();
    return data;
  };

  const addDirectActuator = async (payload) => {
    const { data } = await axios.post(api('/model_editor/add_direct_actuator'), payload);
    await fetchIdfObjects();
    return data;
  };

  const removeDirectActuator = async (name) => {
    const { data } = await axios.delete(api('/model_editor/remove_direct_actuator'), { data: { name } });
    await fetchIdfObjects();
    return data;
  };

  const fetchScheduleCandidates = async () => {
    const { data } = await axios.get(api('/model_editor/schedule_candidates'));
    return { schedules: data.schedules || [], thermostats: data.thermostats || [] };
  };

  const addDirectSchedule = async (payload) => {
    const { data } = await axios.post(api('/model_editor/add_direct_schedule'), payload);
    await fetchIdfObjects();
    return data;
  };

  const removeDirectSchedule = async (scheduleName) => {
    const { data } = await axios.delete(api('/model_editor/remove_direct_schedule'), {
      data: { scheduleName },
    });
    await fetchIdfObjects();
    return data;
  };

  // Roles of the FMU outputs and ranges of the FMU inputs live in the model
  // session (idfObjects.fmu_roles); the editor and the export both read them there.
  const setFmuRole = async (payload) => {
    const { data } = await axios.post(api('/model_editor/set_fmu_role'), payload);
    await fetchIdfObjects();
    return data;
  };

  return (
    <AppContext.Provider
      value={{
        idfObjects,
        uploadedFiles,
        fetchIdfObjects,
        resetSession,
        revertToOriginal,
        filesUploaded,
        modelId,
        sessionKey,
        reloadWorkspace,
        updateUploadedFiles,
        updateWeatherFile,
        removeObject,
        monitorQuantity,
        unmonitorQuantity,
        addControlledActuator,
        removeControlledActuator,
        fetchEmsPrograms,
        checkEmsProgram,
        saveEmsProgram,
        removeEmsProgram,
        saveEmsManager,
        setModelEms,
        removeEmsManager,
        addEmsVariable,
        removeEmsVariable,
        addDirectVariable,
        removeDirectVariable,
        addDirectActuator,
        removeDirectActuator,
        fetchScheduleCandidates,
        addDirectSchedule,
        removeDirectSchedule,
        setFmuRole,
        scheduleTypeLimits,
        loading,
        uploadProgress,
        setUploadProgress,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export { AppProvider, AppContext };

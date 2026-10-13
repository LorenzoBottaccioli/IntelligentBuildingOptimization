import React, { useState, useContext, useEffect } from 'react';
import { api } from './api';
import { AppContext } from './AppContext';
import axios from 'axios';
import { Download, FileCode, Upload } from 'lucide-react';
// Global Bootstrap styles several pages rely on; imported once, here.
import 'bootstrap/dist/css/bootstrap.min.css';
import './FileUploadBar.css';

// The model every page works on, in the sidebar under the session: which IDF and
// EPW are loaded, download the edited IDF, or load a model when there is none.
function FileUploadBar({ collapsed, onExpand }) {
  const { updateUploadedFiles, uploadedFiles, filesUploaded, setUploadProgress, uploadProgress } =
    useContext(AppContext);

  const [idfFile, setIdfFile] = useState(null);
  const [epwFile, setEpwFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!uploading) return undefined;
    const interval = setInterval(async () => {
      try {
        const { data } = await axios.get(api('/model_editor/progress'));
        setUploadProgress(data.progress);
      } catch (err) {
        console.error('Error fetching progress:', err);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [uploading, setUploadProgress]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!idfFile || !epwFile) return;
    const formData = new FormData();
    formData.append('idf_file', idfFile);
    formData.append('epw_file', epwFile);

    setError(null);
    setUploading(true);
    setUploadProgress(10);
    try {
      const { data } = await axios.post(api('/model_editor/upload_files'), formData);
      if (!data.message) throw new Error(data.error || 'Unknown error');
      updateUploadedFiles({ idf: idfFile.name, epw: epwFile.name });
      setUploadProgress(100);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.error || err.message || 'Upload failed.');
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  };

  if (collapsed) {
    const label = filesUploaded ? `Model: ${uploadedFiles.idf}` : 'Load a model';
    return (
      <button type="button" className="sidebar__icon" title={label} aria-label={label} onClick={onExpand}>
        <FileCode size={18} aria-hidden="true" />
      </button>
    );
  }

  return (
    <div className="sidemodel">
      <span className="sessionmenu__label">{filesUploaded ? 'Model' : 'Load a model'}</span>
      {filesUploaded ? (
        <>
          <span className="sidemodel__file" title="Building model (IDF)">{uploadedFiles.idf}</span>
          <span className="sidemodel__file" title="Weather file (EPW)">{uploadedFiles.epw}</span>
          <button type="button" className="sessiontools__btn" onClick={() => window.open(api('/model_converter/get_idf'), '_blank')}>
            <Download size={15} aria-hidden="true" /> <span>Download edited IDF</span>
          </button>
        </>
      ) : (
        <form className="sidemodel__form" onSubmit={handleSubmit}>
          <label className="sidemodel__pick">
            <input type="file" accept=".idf" onChange={(e) => setIdfFile(e.target.files[0])} />
            <span>{idfFile ? idfFile.name : 'Choose the IDF…'}</span>
          </label>
          <label className="sidemodel__pick">
            <input type="file" accept=".epw" onChange={(e) => setEpwFile(e.target.files[0])} />
            <span>{epwFile ? epwFile.name : 'Choose the EPW…'}</span>
          </label>
          <button type="submit" className="sidemodel__upload" disabled={!idfFile || !epwFile || uploading}>
            <Upload size={15} aria-hidden="true" /> {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </form>
      )}
      {uploading && (
        <div className="sidemodel__progress" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100}>
          <div style={{ width: `${uploadProgress}%` }} />
        </div>
      )}
      {error && <span className="sessiontools__msg is-error">{error}</span>}
    </div>
  );
}

export default FileUploadBar;

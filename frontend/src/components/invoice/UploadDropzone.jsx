import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useDispatch, useSelector } from 'react-redux';

import { uploadInvoice, fetchStats, fetchInvoices } from '../../store/slices/invoicesSlice.js';

const ACCEPTED = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/tiff': ['.tif', '.tiff'],
};

export default function UploadDropzone() {
  const dispatch = useDispatch();
  const { uploading, uploadProgress } = useSelector((s) => s.invoices);

  const onDrop = useCallback(
    async (accepted) => {
      for (const file of accepted) {
        // Upload serially so the progress bar is meaningful.
        await dispatch(uploadInvoice(file));
      }
      dispatch(fetchStats());
      dispatch(fetchInvoices());
    },
    [dispatch],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: 25 * 1024 * 1024,
    multiple: true,
    disabled: uploading,
  });

  return (
    <div
      {...getRootProps({
        className: `dropzone ${isDragActive ? 'dropzone--active' : ''}`,
      })}
      aria-label="Upload invoice files"
    >
      <input {...getInputProps()} />
      <div className="dropzone__icon">⇪</div>
      <h3>{uploading ? 'Uploading…' : 'Drop invoices here, or click to browse'}</h3>
      <p>Supports PDF, PNG, JPEG and TIFF — up to 25 MB per file</p>
      {uploading && (
        <div className="progress" aria-label="Upload progress">
          <div className="progress__bar" style={{ width: `${uploadProgress}%` }} />
        </div>
      )}
    </div>
  );
}

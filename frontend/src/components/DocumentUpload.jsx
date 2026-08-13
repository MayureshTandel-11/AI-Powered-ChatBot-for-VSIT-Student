import { useRef, useState } from "react";
import { uploadAdminDocument } from "../services/api.js";

const ALLOWED_TYPES = [".pdf", ".txt", ".docx", ".csv"];

export default function DocumentUpload({ onUploaded }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!ALLOWED_TYPES.includes(extension)) {
      setError(`Unsupported file type. Allowed: ${ALLOWED_TYPES.join(", ")}`);
      setSuccess("");
      return;
    }

    setUploading(true);
    setError("");
    setSuccess("");

    try {
      const response = await uploadAdminDocument(file);
      setSuccess(response.message || "Document uploaded successfully");
      onUploaded();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  return (
    <div className="admin-upload">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.docx,.csv"
        onChange={handleFileChange}
        disabled={uploading}
        hidden
        id="document-upload-input"
      />
      <label htmlFor="document-upload-input" className="admin-button">
        {uploading ? "Uploading..." : "Upload Document"}
      </label>
      {error && <p className="admin-error">{error}</p>}
      {success && <p className="admin-success">{success}</p>}
    </div>
  );
}

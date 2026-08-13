import { useCallback, useEffect, useState } from "react";
import DocumentUpload from "../components/DocumentUpload.jsx";
import {
  deleteAdminDocument,
  getAdminDocuments,
  getAdminMlMetrics,
  getAdminStatistics,
  logout,
  reindexAdminDocuments,
} from "../services/api.js";

function StatCard({ label, value, accent = "blue" }) {
  return (
    <div className={`stat-card stat-card-${accent}`}>
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
    </div>
  );
}

export default function AdminDashboard({ user, onLogout }) {
  const [statistics, setStatistics] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [mlMetrics, setMlMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState("");
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [stats, docs, metrics] = await Promise.all([
        getAdminStatistics(),
        getAdminDocuments(),
        getAdminMlMetrics().catch(() => null),
      ]);
      setStatistics(stats);
      setDocuments(docs.documents);
      setMlMetrics(metrics);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  async function handleDelete(documentId) {
    if (!window.confirm("Delete this document from the knowledge base?")) {
      return;
    }
    try {
      await deleteAdminDocument(documentId);
      setActionMessage("Document deleted successfully");
      loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleReindex() {
    try {
      const response = await reindexAdminDocuments();
      setActionMessage(response.message);
    } catch (err) {
      setError(err.message);
    }
  }

  function handleLogout() {
    logout();
    onLogout();
  }

  if (loading) {
    return (
      <div className="admin-page loading-screen">
        <div className="loading-box">
          <span className="loading-spinner" aria-hidden="true" />
          <p>Loading admin dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div>
          <span className="admin-badge">Admin Panel</span>
          <h1>Dashboard</h1>
          <p>Signed in as {user.email}</p>
        </div>
        <button type="button" className="admin-button secondary" onClick={handleLogout}>
          Logout
        </button>
      </header>

      {error && <p className="admin-error banner">{error}</p>}
      {actionMessage && <p className="admin-success banner">{actionMessage}</p>}

      <section className="admin-section">
        <h2>Overview</h2>
        <div className="stat-grid">
          <StatCard label="Total Students" value={statistics?.total_students ?? 0} accent="blue" />
          <StatCard label="Total Documents" value={statistics?.total_documents ?? 0} accent="green" />
          <StatCard label="Total Questions" value={statistics?.total_questions ?? 0} accent="purple" />
          <StatCard label="Active Users (30d)" value={statistics?.active_users ?? 0} accent="orange" />
        </div>
      </section>

      <section className="admin-section">
        <div className="section-header">
          <div>
            <h2>Knowledge Base</h2>
            <p className="section-desc">Upload and manage college documents for the chatbot</p>
          </div>
          <div className="section-actions">
            <DocumentUpload onUploaded={loadDashboard} />
            <button type="button" className="admin-button secondary" onClick={handleReindex}>
              Re-index
            </button>
          </div>
        </div>

        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan="6" className="table-empty">
                    No documents uploaded yet. Upload a PDF, TXT, DOCX, or CSV file.
                  </td>
                </tr>
              ) : (
                documents.map((document) => (
                  <tr key={document.id}>
                    <td>{document.filename}</td>
                    <td>{document.document_type}</td>
                    <td>
                      <span className={`status-badge status-${document.status}`}>
                        {document.status}
                      </span>
                    </td>
                    <td>{document.chunk_count}</td>
                    <td>{new Date(document.uploaded_at).toLocaleString()}</td>
                    <td>
                      <button
                        type="button"
                        className="table-button danger"
                        onClick={() => handleDelete(document.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="admin-section">
        <h2>ML Model Metrics</h2>
        <p className="section-desc">Intent classifier evaluation from the latest training run</p>
        {!mlMetrics ? (
          <p className="admin-muted">
            Intent model metrics not available. Run <code>python -m app.ml.train_model</code>.
          </p>
        ) : (
          <div className="metrics-grid">
            <StatCard label="Model" value={mlMetrics.model_name} accent="blue" />
            <StatCard label="Training Examples" value={mlMetrics.training_examples} accent="green" />
            <StatCard label="Accuracy" value={mlMetrics.accuracy.toFixed(3)} accent="purple" />
            <StatCard label="Precision" value={mlMetrics.precision.toFixed(3)} accent="orange" />
            <StatCard label="Recall" value={mlMetrics.recall.toFixed(3)} accent="blue" />
            <StatCard label="F1 Score" value={mlMetrics.f1_score.toFixed(3)} accent="green" />
          </div>
        )}
      </section>
    </div>
  );
}

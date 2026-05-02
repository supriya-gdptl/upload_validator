import { useState, useRef, useCallback } from "react";

const API_BASE = "http://localhost:8000";

const ACCEPTED = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
  "application/pdf": [".pdf"],
  "video/mp4": [".mp4"],
  "video/quicktime": [".mov"],
};

const ACCEPT_STRING = Object.values(ACCEPTED).flat().join(",");

function ScoreRing({ score }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;

  const color =
    score >= 75 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <svg width="96" height="96" viewBox="0 0 96 96" className="score-ring">
      <circle cx="48" cy="48" r={r} fill="none" stroke="#1e293b" strokeWidth="8" />
      <circle
        cx="48"
        cy="48"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 48 48)"
        style={{ transition: "stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)" }}
      />
      <text
        x="48"
        y="53"
        textAnchor="middle"
        fill={color}
        fontSize="18"
        fontWeight="700"
        fontFamily="'DM Mono', monospace"
      >
        {score}%
      </text>
    </svg>
  );
}

function FileIcon({ type }) {
  if (type === "pdf")
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="file-icon">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="9" y1="13" x2="15" y2="13" />
        <line x1="9" y1="17" x2="12" y2="17" />
      </svg>
    );
  if (type === "video")
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="file-icon">
        <polygon points="23 7 16 12 23 17 23 7" />
        <rect x="1" y="5" width="15" height="14" rx="2" />
      </svg>
    );
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="file-icon">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </svg>
  );
}

export default function UploadValidator() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [description, setDescription] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [forceSubmit, setForceSubmit] = useState(false);
  const inputRef = useRef();

  const reset = () => {
    setFile(null);
    setPreview(null);
    setDescription("");
    setResult(null);
    setForceSubmit(false);
  };

  const handleFile = (f) => {
    if (!f) return;
    setFile(f);
    setResult(null);
    setForceSubmit(false);
    if (f.type.startsWith("image/")) {
      const url = URL.createObjectURL(f);
      setPreview(url);
    } else {
      setPreview(null);
    }
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }, []);

  const validate = async (skipThreshold = false) => {
    if (!file || !description.trim()) return;
    setLoading(true);
    setResult(null);

    const form = new FormData();
    form.append("file", file);
    form.append("description", description);

    try {
      const res = await fetch(`${API_BASE}/validate`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();

      if (!res.ok) {
        setResult({ error: data.detail || "Validation failed." });
        return;
      }

      if (skipThreshold && data.decision === "warning") {
        data.decision = "approved";
        data.message = "Submitted with your existing description.";
      }

      setResult(data);
    } catch {
      setResult({ error: "Cannot reach the validation server. Is the backend running?" });
    } finally {
      setLoading(false);
    }
  };

  const canSubmit = file && description.trim().length > 0;

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
          background: #0a0f1e;
          color: #e2e8f0;
          font-family: 'DM Sans', sans-serif;
          min-height: 100vh;
        }

        .app {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 2rem 1rem;
          background:
            radial-gradient(ellipse 80% 50% at 50% -10%, #1a2a6c22 0%, transparent 60%),
            radial-gradient(ellipse 60% 40% at 80% 110%, #b21f1f11 0%, transparent 60%),
            #0a0f1e;
        }

        .card {
          width: 100%;
          max-width: 580px;
          background: #111827;
          border: 1px solid #1e293b;
          border-radius: 20px;
          padding: 2.5rem;
          box-shadow: 0 32px 80px #00000055;
        }

        .header {
          margin-bottom: 2rem;
          text-align: center;
        }

        .badge {
          display: inline-block;
          font-family: 'DM Mono', monospace;
          font-size: 0.65rem;
          letter-spacing: 0.15em;
          text-transform: uppercase;
          color: #60a5fa;
          border: 1px solid #1e40af44;
          padding: 0.2rem 0.7rem;
          border-radius: 100px;
          background: #1e3a8a11;
          margin-bottom: 0.75rem;
        }

        h1 {
          font-family: 'DM Serif Display', serif;
          font-size: 2rem;
          font-weight: 400;
          color: #f1f5f9;
          line-height: 1.15;
        }

        h1 span { color: #60a5fa; }

        .subtitle {
          font-size: 0.85rem;
          color: #64748b;
          margin-top: 0.4rem;
        }

        /* Drop zone */
        .dropzone {
          border: 2px dashed #1e293b;
          border-radius: 14px;
          padding: 2rem 1rem;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          background: #0f172a;
          margin-bottom: 1.25rem;
          position: relative;
          overflow: hidden;
        }

        .dropzone.drag-over {
          border-color: #3b82f6;
          background: #1e3a8a0a;
        }

        .dropzone.has-file {
          border-style: solid;
          border-color: #1e40af44;
          padding: 1.25rem 1rem;
        }

        .dropzone-inner { pointer-events: none; }

        .drop-icon {
          width: 40px; height: 40px;
          margin: 0 auto 0.75rem;
          color: #334155;
        }

        .drop-label {
          font-size: 0.85rem;
          color: #475569;
        }
        .drop-label strong { color: #60a5fa; font-weight: 500; }

        .drop-types {
          font-family: 'DM Mono', monospace;
          font-size: 0.7rem;
          color: #334155;
          margin-top: 0.4rem;
        }

        /* File preview row */
        .file-preview {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .file-thumb {
          width: 52px; height: 52px;
          border-radius: 8px;
          overflow: hidden;
          background: #1e293b;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .file-thumb img {
          width: 100%; height: 100%; object-fit: cover;
        }

        .file-icon { width: 24px; height: 24px; color: #60a5fa; }

        .file-info { flex: 1; min-width: 0; text-align: left; }
        .file-name {
          font-size: 0.85rem;
          font-weight: 500;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          color: #e2e8f0;
        }
        .file-size {
          font-family: 'DM Mono', monospace;
          font-size: 0.7rem;
          color: #475569;
        }

        .remove-btn {
          background: none;
          border: none;
          color: #475569;
          cursor: pointer;
          padding: 0.25rem;
          border-radius: 4px;
          font-size: 1.1rem;
          line-height: 1;
          transition: color 0.15s;
        }
        .remove-btn:hover { color: #ef4444; }

        /* Textarea */
        label {
          display: block;
          font-size: 0.75rem;
          font-weight: 600;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: #475569;
          margin-bottom: 0.5rem;
        }

        textarea {
          width: 100%;
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 10px;
          color: #e2e8f0;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.9rem;
          padding: 0.85rem 1rem;
          resize: vertical;
          min-height: 90px;
          outline: none;
          transition: border-color 0.2s;
          margin-bottom: 1.25rem;
        }
        textarea:focus { border-color: #3b82f6; }
        textarea::placeholder { color: #334155; }

        /* Buttons */
        .btn-row { display: flex; gap: 0.75rem; }

        .btn {
          flex: 1;
          padding: 0.75rem 1.25rem;
          border-radius: 10px;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.9rem;
          font-weight: 600;
          cursor: pointer;
          border: none;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.4rem;
        }

        .btn-primary {
          background: #2563eb;
          color: #fff;
        }
        .btn-primary:hover:not(:disabled) { background: #1d4ed8; }
        .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

        .btn-ghost {
          background: #1e293b;
          color: #94a3b8;
        }
        .btn-ghost:hover { background: #263245; color: #e2e8f0; }

        /* Result panel */
        .result {
          margin-top: 1.5rem;
          padding: 1.5rem;
          border-radius: 14px;
          border: 1px solid;
          animation: slideUp 0.3s ease;
        }

        @keyframes slideUp {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        .result.approved  { background: #052e16; border-color: #166534; }
        .result.warning   { background: #1c1107; border-color: #92400e; }
        .result.rejected  { background: #1c0505; border-color: #991b1b; }
        .result.error     { background: #1c1107; border-color: #7c3aed; }

        .result-top {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 1rem;
        }

        .result-info { flex: 1; }

        .result-label {
          font-family: 'DM Mono', monospace;
          font-size: 0.65rem;
          letter-spacing: 0.15em;
          text-transform: uppercase;
          margin-bottom: 0.25rem;
        }

        .approved  .result-label { color: #4ade80; }
        .warning   .result-label { color: #fbbf24; }
        .rejected  .result-label { color: #f87171; }

        .result-msg {
          font-size: 0.88rem;
          color: #cbd5e1;
          line-height: 1.5;
        }

        /* Debug details */
        .debug {
          margin-top: 0.75rem;
          display: flex;
          gap: 0.5rem;
          flex-wrap: wrap;
        }

        .chip {
          font-family: 'DM Mono', monospace;
          font-size: 0.68rem;
          background: #ffffff08;
          border: 1px solid #ffffff11;
          border-radius: 6px;
          padding: 0.2rem 0.55rem;
          color: #64748b;
        }

        .warn-actions {
          display: flex;
          gap: 0.6rem;
          margin-top: 1rem;
        }

        .btn-warn {
          flex: 1;
          padding: 0.6rem;
          border-radius: 8px;
          font-size: 0.82rem;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid;
          background: none;
          font-family: 'DM Sans', sans-serif;
          transition: all 0.15s;
        }

        .btn-warn-edit {
          border-color: #92400e;
          color: #fbbf24;
        }
        .btn-warn-edit:hover { background: #92400e22; }

        .btn-warn-submit {
          border-color: #1d4ed8;
          color: #60a5fa;
        }
        .btn-warn-submit:hover { background: #1d4ed811; }

        /* Spinner */
        .spinner {
          width: 18px; height: 18px;
          border: 2px solid #ffffff33;
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <div className="app">
        <div className="card">
          <div className="header">
            <div className="badge">AI Content Validator</div>
            <h1>Upload <span>Smart.</span></h1>
            <p className="subtitle">
              Your file is scanned locally — no data leaves the server.
            </p>
          </div>

          {/* ── Drop zone ── */}
          <div
            className={`dropzone ${dragging ? "drag-over" : ""} ${file ? "has-file" : ""}`}
            onClick={() => !file && inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT_STRING}
              style={{ display: "none" }}
              onChange={(e) => handleFile(e.target.files[0])}
            />

            {file ? (
              <div className="file-preview">
                <div className="file-thumb">
                  {preview
                    ? <img src={preview} alt="preview" />
                    : <FileIcon type={file.type.includes("pdf") ? "pdf" : file.type.includes("video") ? "video" : "image"} />
                  }
                </div>
                <div className="file-info">
                  <div className="file-name">{file.name}</div>
                  <div className="file-size">{(file.size / 1024).toFixed(1)} KB</div>
                </div>
                <button className="remove-btn" onClick={(e) => { e.stopPropagation(); reset(); }}>✕</button>
              </div>
            ) : (
              <div className="dropzone-inner">
                <svg className="drop-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <p className="drop-label"><strong>Click to browse</strong> or drag &amp; drop</p>
                <p className="drop-types">JPG · PNG · PDF · MP4 · MOV</p>
              </div>
            )}
          </div>

          {/* ── Description ── */}
          <label htmlFor="desc">File description</label>
          <textarea
            id="desc"
            placeholder="Describe what this file contains…"
            value={description}
            onChange={(e) => { setDescription(e.target.value); setResult(null); setForceSubmit(false); }}
          />

          {/* ── Primary actions ── */}
          <div className="btn-row">
            <button className="btn btn-ghost" onClick={reset}>Clear</button>
            <button
              className="btn btn-primary"
              disabled={!canSubmit || loading}
              onClick={() => validate(false)}
            >
              {loading ? <span className="spinner" /> : "Validate & Upload"}
            </button>
          </div>

          {/* ── Result ── */}
          {result && (
            <div className={`result ${result.error ? "error" : result.decision}`}>
              {result.error ? (
                <p className="result-msg" style={{ color: "#c4b5fd" }}>⚠ {result.error}</p>
              ) : (
                <>
                  <div className="result-top">
                    <ScoreRing score={result.score} />
                    <div className="result-info">
                      <div className="result-label">
                        {result.decision === "approved" && "✓ Approved"}
                        {result.decision === "warning" && "⚠ Review description"}
                        {result.decision === "rejected" && "✗ Rejected"}
                      </div>
                      <p className="result-msg">{result.message}</p>
                    </div>
                  </div>

                  <div className="debug">
                    <span className="chip">type: {result.file_type}</span>
                    {result.clip_available && (
                      <span className="chip">clip: {result.clip_similarity}%</span>
                    )}
                    <span className="chip">text: {result.text_similarity}%</span>
                    {result.frames_analysed != null && (
                      <span className="chip">frames: {result.frames_analysed}</span>
                    )}
                    {result.ocr_preview && (
                      <span className="chip" title={result.ocr_preview}>
                        ocr: "{result.ocr_preview.slice(0, 40)}…"
                      </span>
                    )}
                  </div>

                  {result.decision === "warning" && (
                    <div className="warn-actions">
                      <button
                        className="btn-warn btn-warn-edit"
                        onClick={() => { setResult(null); document.getElementById("desc")?.focus(); }}
                      >
                        ✏ Improve description
                      </button>
                      <button
                        className="btn-warn btn-warn-submit"
                        onClick={() => validate(true)}
                      >
                        Submit anyway →
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

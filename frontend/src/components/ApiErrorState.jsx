import React from "react";

export default function ApiErrorState({
  title = "Unable to load project intelligence",
  message = "Backend connection unavailable. Please check if the intelligence engine service is running.",
  endpoint,
  status,
  errorDetails,
  onRetry,
}) {
  const isDev = import.meta.env.DEV || true;

  return (
    <div className="api-error-card">
      <div className="api-error-header">
        <span className="error-icon">⚠️</span>
        <div>
          <h3 className="error-title">{title}</h3>
          <p className="error-message">{message}</p>
        </div>
      </div>

      {isDev && (endpoint || status || errorDetails) && (
        <div className="dev-error-details">
          <div className="dev-error-label">Developer Diagnostic Trace (Dev Mode):</div>
          {endpoint && <div><strong>Endpoint:</strong> <code>{endpoint}</code></div>}
          {status && <div><strong>HTTP Status:</strong> <code>{status}</code></div>}
          {errorDetails && (
            <div className="dev-error-msg">
              <strong>Error Message:</strong> <code>{errorDetails}</code>
            </div>
          )}
        </div>
      )}

      {onRetry && (
        <button className="btn primary btn-retry" onClick={onRetry}>
          ↻ Retry Request
        </button>
      )}
    </div>
  );
}

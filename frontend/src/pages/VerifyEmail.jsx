import { useState, useEffect } from "react";
import { verifyEmailOtp, resendOtp } from "../services/api.js";

export default function VerifyEmail() {
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    const pending = localStorage.getItem("pending_email") || "";
    setEmail(pending);
  }, []);

  useEffect(() => {
    let timer = null;
    if (cooldown > 0) {
      timer = setTimeout(() => setCooldown((value) => value - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function handleVerify(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await verifyEmailOtp(email, otp);
      setMessage(res.message || "Email verified successfully.");
      setVerified(true);
      localStorage.removeItem("pending_email");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await resendOtp(email);
      setMessage(res.message || "OTP resent.");
      setCooldown(60);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <header className="auth-header">
          <div className="auth-logo">✉️</div>
          <h1>Verify Your Email</h1>
          <p>
            Enter the 6-digit code sent to{" "}
            <strong>{email || "your VSIT email"}</strong>
          </p>
        </header>

        <div className="auth-card">
          {verified ? (
            <div className="auth-verified">
              <p className="auth-message success">{message}</p>
              <button
                type="button"
                className="auth-button"
                onClick={() => {
                  window.location.href = "/";
                }}
              >
                Continue to Login
              </button>
            </div>
          ) : (
            <>
              <form onSubmit={handleVerify} className="auth-form">
                <label>
                  Verification Code
                  <input
                    type="text"
                    className="otp-field"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    required
                    maxLength={6}
                    placeholder="000000"
                  />
                </label>

                {error && <div className="auth-message error">{error}</div>}
                {message && !verified && <div className="auth-message info">{message}</div>}

                <button type="submit" className="auth-button" disabled={loading || otp.length !== 6}>
                  {loading ? "Verifying..." : "Verify Email"}
                </button>
              </form>

              <p className="auth-toggle">
                Didn&apos;t receive the code?{" "}
                <button
                  type="button"
                  className="link-button"
                  onClick={handleResend}
                  disabled={cooldown > 0 || loading}
                >
                  {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend OTP"}
                </button>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

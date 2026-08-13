import { useState } from "react";
import { login, register } from "../services/api.js";

export default function LoginForm({ onSuccess }) {
  const [mode, setMode] = useState("login");
  const [firstName, setFirstName] = useState("");
  const [surname, setSurname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "login") {
        const data = await login(email.trim().toLowerCase(), password);
        onSuccess(data.user);
        return;
      }

      if (password !== confirmPassword) {
        throw new Error("Passwords do not match");
      }

      await register({
        first_name: firstName.trim(),
        surname: surname.trim(),
        email: email.trim().toLowerCase(),
        password,
        confirm_password: confirmPassword,
      });

      localStorage.setItem("pending_email", email.trim().toLowerCase());
      window.location.href = "/verify-email";
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <div className="auth-tabs">
        <button
          type="button"
          className={`auth-tab ${mode === "login" ? "active" : ""}`}
          onClick={() => {
            setMode("login");
            setError("");
          }}
        >
          Login
        </button>
        <button
          type="button"
          className={`auth-tab ${mode === "register" ? "active" : ""}`}
          onClick={() => {
            setMode("register");
            setError("");
          }}
        >
          Register
        </button>
      </div>

      <p className="auth-card-desc">
        {mode === "login"
          ? "Use your verified VSIT email to access the chatbot."
          : "Register with your official VSIT student email."}
      </p>

      <form className="auth-form" onSubmit={handleSubmit}>
        {mode === "register" && (
          <div className="auth-form-row">
            <label>
              First Name
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
                placeholder="Rahul"
              />
            </label>
            <label>
              Surname
              <input
                type="text"
                value={surname}
                onChange={(e) => setSurname(e.target.value)}
                required
                placeholder="Sharma"
              />
            </label>
          </div>
        )}

        <label>
          VSIT Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="name.surname@vsit.edu.in"
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            placeholder="Minimum 8 characters"
          />
        </label>

        {mode === "register" && (
          <label>
            Confirm Password
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              placeholder="Re-enter password"
            />
          </label>
        )}

        {error && <div className="auth-message error">{error}</div>}

        <button type="submit" className="auth-button" disabled={loading}>
          {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
        </button>
      </form>

      {mode === "register" && (
        <p className="auth-note">A verification OTP will be sent to your VSIT email.</p>
      )}
    </div>
  );
}

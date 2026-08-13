import LoginForm from "../components/LoginForm.jsx";

export default function Login({ onSuccess }) {
  return (
    <div className="auth-page">
      <div className="auth-container">
        <header className="auth-header">
          <div className="auth-logo">🎓</div>
          <h1>College AI Student Assistant</h1>
          <p>Sign in or create your VSIT student account</p>
        </header>
        <LoginForm onSuccess={onSuccess} />
      </div>
    </div>
  );
}

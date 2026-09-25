import { useEffect, useState } from "react";
import Login from "./pages/Login.jsx";
import Chat from "./pages/Chat.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import { getMe, getStoredUser, logout as clearAuth } from "./services/api.js";
import "./App.css";

function App() {
  const [user, setUser] = useState(getStoredUser());
  const [loading, setLoading] = useState(Boolean(getStoredUser()));

  useEffect(() => {
    if (!getStoredUser()) {
      setLoading(false);
      return;
    }

    getMe()
      .then((profile) => setUser(profile))
      .catch(() => {
        clearAuth();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="app loading-screen">
        <p>Loading session...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="app auth-layout">
        <Login onSuccess={setUser} />
      </div>
    );
  }

  if (user.role === "admin") {
    return (
      <div className="app admin-app">
        <AdminDashboard user={user} onLogout={() => setUser(null)} />
      </div>
    );
  }

  return (
    <div className="app chat-app">
      <Chat user={user} onLogout={() => setUser(null)} />
    </div>
  );
}

export default App;

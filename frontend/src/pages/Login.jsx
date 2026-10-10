import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("admin");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const res = await api("/login", "POST", { username, password, role });
    setBusy(false);
    if (res.ok) {
      // go to the OTP screen and pass the masked email + timer
      navigate("/otp", { state: { email: res.data.email, expiresIn: res.data.expires_in } });
    } else {
      setError(res.data.error || "Login failed");
    }
  }

  return (
    <div className="card">
      <h1>PrivView</h1>
      <p className="muted">Privacy-preserving data visualisation</p>
      <form onSubmit={handleSubmit}>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <label>Role</label>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="admin">System Admin</option>
          <option value="analyst">External Cloud Analyst</option>
        </select>
        {error && <p className="error">{error}</p>}
        <button disabled={busy}>{busy ? "Sending OTP..." : "Login"}</button>
      </form>
    </div>
  );
}

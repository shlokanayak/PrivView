import { useEffect, useState } from "react";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { api } from "../api.js";

export default function Otp({ setUser }) {
  const { state } = useLocation();
  const navigate = useNavigate();
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(state?.expiresIn || 0);
  const [resendUsed, setResendUsed] = useState(false);

  // countdown display (the backend decides the real expiry)
  useEffect(() => {
    const timer = setInterval(() => setSecondsLeft((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(timer);
  }, []);

  // opened /otp directly or refreshed the page -> go back to login
  if (!state) return <Navigate to="/" />;

  async function handleVerify(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    const res = await api("/verify-otp", "POST", { otp });
    if (res.ok) {
      setUser({ username: res.data.username, role: res.data.role });
      navigate("/" + res.data.role);          // admin -> /admin, analyst -> /analyst
    } else if (res.data.restart) {
      navigate("/");                          // attempt invalidated -> login screen
    } else {
      setError(res.data.error);
      setOtp("");
    }
  }

  async function handleResend() {
    setError("");
    const res = await api("/resend-otp", "POST");
    if (res.ok) {
      setResendUsed(true);
      setSecondsLeft(res.data.expires_in);
      setInfo("A new OTP was sent. The old one no longer works.");
    } else if (res.data.restart) {
      navigate("/");
    } else {
      setError(res.data.error);
    }
  }

  return (
    <div className="card">
      <h1>Verify OTP</h1>
      <p className="muted">We sent a 6-digit code to {state.email}</p>
      <form onSubmit={handleVerify}>
        <input value={otp} maxLength={6} inputMode="numeric" autoFocus
               placeholder="000000" onChange={(e) => setOtp(e.target.value)} />
        <p className="muted">
          {secondsLeft > 0 ? `Code expires in ${secondsLeft}s` : "Code expired"}
        </p>
        {error && <p className="error">{error}</p>}
        {info && <p className="ok">{info}</p>}
        <button>Verify</button>
      </form>
      <button className="link" onClick={handleResend} disabled={resendUsed}>
        {resendUsed ? "Resend already used" : "Resend OTP (one time only)"}
      </button>
      <button className="link" onClick={() => navigate("/")}>Back to login</button>
    </div>
  );
}

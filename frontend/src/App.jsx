// App.jsx - routes + a simple route guard.
// NOTE: the guard only decides what to SHOW. The real security check
// is done by the Flask backend (role_required) on every API call.
import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { api } from "./api.js";
import Login from "./pages/Login.jsx";
import Otp from "./pages/Otp.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import UploadDataset from "./pages/UploadDataset.jsx";
import AnalystDashboard from "./pages/AnalystDashboard.jsx";
import AnalysisWorkspace from "./pages/AnalysisWorkspace.jsx";

function Protected({ user, role, children }) {
  if (!user) return <Navigate to="/" />;
  if (user.role !== role) return <Navigate to={"/" + user.role} />;
  return children;
}

export default function App() {
  const [user, setUser] = useState(null);      // { username, role } or null
  const [loading, setLoading] = useState(true);

  // On page load, ask the backend if we already have a valid session
  useEffect(() => {
    api("/me").then((r) => {
      if (r.ok) setUser(r.data);
      setLoading(false);
    });
  }, []);

  if (loading) return <p className="center">Loading...</p>;

  return (
    <Routes>
      <Route path="/" element={user ? <Navigate to={"/" + user.role} /> : <Login />} />
      <Route path="/otp" element={<Otp setUser={setUser} />} />
      <Route path="/admin" element={
        <Protected user={user} role="admin"><AdminDashboard setUser={setUser} /></Protected>} />
      <Route path="/admin/upload" element={
        <Protected user={user} role="admin"><UploadDataset setUser={setUser} /></Protected>} />
      <Route path="/analyst" element={
        <Protected user={user} role="analyst"><AnalystDashboard setUser={setUser} /></Protected>} />
      <Route path="/analyst/dataset/:id" element={
        <Protected user={user} role="analyst"><AnalysisWorkspace setUser={setUser} /></Protected>} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}

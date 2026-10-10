import { NavLink, useNavigate } from "react-router-dom";
import { api } from "../api.js";

// Top bar shown on the admin and analyst pages.
export default function Header({ setUser, role = "admin" }) {
  const navigate = useNavigate();

  async function logout() {
    await api("/logout", "POST");
    setUser(null);
    navigate("/");
  }

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <span className="brand">
          PrivView<small>{role === "admin" ? "System Admin" : "External Cloud Analyst"}</small>
        </span>
        <nav className="nav">
          {role === "admin" ? (
            <>
              <NavLink to="/admin" end>Dashboard</NavLink>
              <NavLink to="/admin/upload">Upload dataset</NavLink>
            </>
          ) : (
            <NavLink to="/analyst">My datasets</NavLink>
          )}
        </nav>
        <button className="btn btn-ghost" onClick={logout}>Log out</button>
      </div>
    </header>
  );
}

import { useState } from "react";
import { Link } from "react-router-dom";
import Header from "../components/Header.jsx";
import DatasetsTab from "../components/DatasetsTab.jsx";
import UsersTab from "../components/UsersTab.jsx";
import LogsTab from "../components/LogsTab.jsx";

export default function AdminDashboard({ setUser }) {
  const [tab, setTab] = useState("datasets");
  const tabs = [["datasets", "Datasets"], ["users", "Users and roles"], ["logs", "Activity log"]];

  return (
    <div className="admin">
      <Header setUser={setUser} />
      <main className="page">
        <div className="page-head">
          <div>
            <h1>Admin dashboard</h1>
            <p className="muted">Manage protected datasets, user access and the audit trail.</p>
          </div>
          <Link className="btn" to="/admin/upload">Upload dataset</Link>
        </div>

        <div className="tabs">
          {tabs.map(([key, label]) => (
            <button key={key} className={tab === key ? "tab tab-active" : "tab"}
                    onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </div>

        {tab === "datasets" && <DatasetsTab />}
        {tab === "users" && <UsersTab />}
        {tab === "logs" && <LogsTab />}
      </main>
    </div>
  );
}

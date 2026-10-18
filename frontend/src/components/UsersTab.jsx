import { useEffect, useState } from "react";
import { api } from "../api.js";
import { formatDate } from "../format.js";
import Pill from "./Pill.jsx";

export default function UsersTab() {
  const [users, setUsers] = useState(null);
  const [message, setMessage] = useState(null);

  async function load() {
    const res = await api("/admin/users");
    if (res.ok) setUsers(res.data.users);
    else setMessage({ type: "bad", text: res.data.error || "Could not load users." });
  }

  useEffect(() => { load(); }, []);

  async function update(user, changes) {
    const res = await api(`/admin/users/${user.id}`, "PATCH", changes);
    setMessage(res.ok ? { type: "ok", text: res.data.message }
                      : { type: "bad", text: res.data.error });
    load();     
  }

  if (!users) return <p className="muted">Loading users...</p>;

  return (
    <>
      {message && <div className={"notice notice-" + message.type}>{message.text}</div>}
      <div className="panel">
        <div className="panel-head"><h2>Users and roles</h2></div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Username</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Access</th></tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <span className="cell-title">{u.username}</span>
                    {u.is_you && <span className="you">you</span>}
                  </td>
                  <td className="muted">{u.email}</td>
                  <td>
                    <select className="select-inline" value={u.role}
                            onChange={(e) => update(u, { role: e.target.value })}>
                      <option value="admin">System Admin</option>
                      <option value="analyst">External Cloud Analyst</option>
                    </select>
                  </td>
                  <td>
                    <Pill tone={u.is_active ? "ok" : "bad"}>{u.is_active ? "Active" : "Inactive"}</Pill>
                  </td>
                  <td>{formatDate(u.created_at)}</td>
                  <td>
                    <button className={u.is_active ? "btn btn-danger-outline btn-sm" : "btn btn-secondary btn-sm"}
                            onClick={() => update(u, { is_active: !u.is_active })}>
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          Changes apply on the user's very next request. Deactivating a user ends their access
          completely; their role is kept in case you activate them again.
        </p>
      </div>
    </>
  );
}

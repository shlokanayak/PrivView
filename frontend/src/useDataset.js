import { useEffect, useState } from "react";
import { api } from "./api.js";

export default function useDataset(id) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    if (!id) return;

    let stopped = false;
    let timer;

    async function load() {
      const res = await api(`/admin/datasets/${id}`);
      if (stopped) return;
      if (!res.ok) {
        setError(res.data.error || "Could not load the dataset.");
        return;
      }
      setData(res.data);
      if (res.data.status === "processing") timer = setTimeout(load, 600);
    }

    load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [id]);

  return { data, error };
}

export async function api(path, method = "GET", body) {
  const isForm = body instanceof FormData;
  const res = await fetch("/api" + path, {
    method,
    headers: isForm ? undefined : { "Content-Type": "application/json" },
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

export async function downloadFile(path, fallbackName) {
  const res = await fetch("/api" + path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return { ok: false, error: err.error || "Download failed." };
  }
  const blob = await res.blob();
  const header = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/.exec(header);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = match ? match[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return { ok: true, name: link.download };
}

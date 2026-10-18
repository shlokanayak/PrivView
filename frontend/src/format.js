export function formatDate(iso, withSeconds = false) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: withSeconds ? "medium" : "short",
  });
}

export function formatBytes(n) {
  if (n == null) return "-";
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / (1024 * 1024)).toFixed(2) + " MB";
}

export function fmtNum(value) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function actionLabel(action) {
  const text = action.replaceAll("_", " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

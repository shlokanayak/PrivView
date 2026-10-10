export default function Pill({ tone = "wait", children }) {
  return <span className={"pill pill-" + tone}>{children}</span>;
}

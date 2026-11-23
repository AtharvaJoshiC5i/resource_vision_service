import type { ToastTone } from "../components/ui/Toast";

export function toneFor(text: string): ToastTone {
  const t = text.toLowerCase();
  if (t.includes("failed") || t.includes("could not") || t.includes("error")) return "error";
  if (t.includes("done") || t.includes("confirmed") || t.includes("processed")) return "success";
  return "info";
}

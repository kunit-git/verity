import { useEffect, useId, useRef, useState } from "react";
import mermaid from "mermaid";

interface Props {
  source: string;
}

const MERMAID_CONFIG = {
  startOnLoad: false,
  // "strict" sanitizes rendered HTML and disables click/script directives.
  // Diagram source is user-supplied custom-field content shown to other users,
  // so a looser level would allow stored XSS.
  securityLevel: "strict" as const,
  theme: "base" as const,
  themeVariables: {
    // backgrounds
    background: "#ffffff",
    mainBkg: "#eff6ff",          // blue-50
    secondBkg: "#f8fafc",        // slate-50
    tertiaryColor: "#f1f5f9",    // slate-100
    // text
    primaryTextColor: "#1e293b", // slate-800
    secondaryTextColor: "#475569",
    tertiaryTextColor: "#475569",
    // borders / lines
    primaryBorderColor: "#bfdbfe", // blue-200
    secondaryBorderColor: "#e2e8f0",
    lineColor: "#64748b",          // slate-500
    // nodes
    primaryColor: "#eff6ff",       // blue-50
    nodeBkg: "#eff6ff",
    nodeBorder: "#93c5fd",         // blue-300
    clusterBkg: "#f8fafc",
    // sequence diagram
    actorBkg: "#eff6ff",
    actorBorder: "#93c5fd",
    actorTextColor: "#1e293b",
    actorLineColor: "#94a3b8",     // slate-400
    signalColor: "#475569",
    signalTextColor: "#475569",
    labelBoxBkgColor: "#eff6ff",
    labelTextColor: "#1e293b",
    loopTextColor: "#1e293b",
    // notes
    noteBkgColor: "#fefce8",       // yellow-50
    noteTextColor: "#1e293b",
    noteBorderColor: "#fde68a",    // yellow-200
    // flowchart
    edgeLabelBackground: "#ffffff",
    // misc
    titleColor: "#0f172a",         // slate-900
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
  },
};

export default function MermaidDiagram({ source }: Props) {
  const id = useId().replace(/:/g, "");
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!source.trim()) return;
    let cancelled = false;
    setError(null);
    mermaid.initialize(MERMAID_CONFIG);
    mermaid
      .render(`mermaid-${id}`, source)
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        if (ref.current) ref.current.innerHTML = "";
      });
    return () => { cancelled = true; };
  }, [source, id]);

  if (!source.trim()) {
    return (
      <div className="text-sm text-gray-400 italic">No diagram source.</div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div ref={ref} />
      {error && (
        <div className="mt-2 rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          <span className="font-semibold">Diagram error:</span> {error}
          <pre className="mt-1 whitespace-pre-wrap font-mono text-xs text-red-600">
            {source}
          </pre>
        </div>
      )}
    </div>
  );
}

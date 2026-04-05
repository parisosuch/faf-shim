import CodeMirror from "@uiw/react-codemirror";
import { json, jsonParseLinter } from "@codemirror/lang-json";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { linter, lintGutter, type Diagnostic } from "@codemirror/lint";
import { EditorView } from "@codemirror/view";
import { tags } from "@lezer/highlight";

export type EditorMode = "json" | "jinja-json";

interface Props {
  value: string;
  onChange: (value: string) => void;
  mode?: EditorMode;
  minRows?: number;
}

// ---------------------------------------------------------------------------
// DaisyUI-aware theme — reads CSS vars so it automatically matches whichever
// DaisyUI theme (caramellatte / coffee / anything else) is active.
// ---------------------------------------------------------------------------

const daisyEditorTheme = EditorView.theme({
  "&": {
    backgroundColor: "var(--color-base-100)",
    color: "var(--color-base-content)",
  },
  ".cm-content": {
    caretColor: "var(--color-base-content)",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
  },
  ".cm-cursor": { borderLeftColor: "var(--color-base-content)" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection": {
    backgroundColor: "color-mix(in oklch, var(--color-primary) 25%, transparent)",
  },
  ".cm-gutters": {
    backgroundColor: "var(--color-base-200)",
    color: "color-mix(in oklch, var(--color-base-content) 45%, transparent)",
    borderRight: "1px solid var(--color-base-300)",
  },
  ".cm-activeLineGutter": { backgroundColor: "var(--color-base-300)" },
  ".cm-activeLine": { backgroundColor: "transparent" },
  ".cm-tooltip": {
    backgroundColor: "var(--color-base-200)",
    border: "1px solid var(--color-base-300)",
    color: "var(--color-base-content)",
  },
});

const daisyHighlightStyle = HighlightStyle.define([
  // JSON keys
  { tag: tags.propertyName, color: "var(--color-primary)" },
  // String values
  { tag: tags.string, color: "var(--color-success)" },
  // Numbers
  { tag: tags.number, color: "var(--color-info)" },
  // true / false / null
  { tag: [tags.bool, tags.null], color: "var(--color-warning)" },
  // Punctuation: {} [] : ,
  {
    tag: tags.punctuation,
    color: "color-mix(in oklch, var(--color-base-content) 55%, transparent)",
  },
]);

// ---------------------------------------------------------------------------
// Linting
// ---------------------------------------------------------------------------

/** Replace Jinja2 blocks with valid JSON placeholders so the JSON linter
 *  doesn't flag them as errors.
 *  {{ expr }}  →  null   (safe whether inside quotes or not)
 *  {% stmt %}  →  ""     (control flow stripped) */
function stripJinja(text: string): string {
  return text.replace(/\{\{[\s\S]*?\}\}/g, "null").replace(/\{%[\s\S]*?%\}/g, "");
}

const _jsonLinter = jsonParseLinter();

function jsonLinter(view: EditorView): Diagnostic[] {
  if (!view.state.doc.toString().trim()) return [];
  return _jsonLinter(view);
}

function jinjaJsonLinter(view: EditorView): Diagnostic[] {
  const text = view.state.doc.toString();
  if (!text.trim()) return [];

  const diagnostics: Diagnostic[] = [];

  // Warn on {{ expr }} blocks that don't pipe through tojson — without it,
  // strings are unquoted and objects aren't serialized, producing invalid JSON.
  const blockRe = /\{\{([\s\S]*?)\}\}/g;
  let match;
  while ((match = blockRe.exec(text)) !== null) {
    if (!/\|\s*tojson/.test(match[1])) {
      diagnostics.push({
        from: match.index,
        to: match.index + match[0].length,
        severity: "warning",
        message: "Missing | tojson — without it the value may not be valid JSON",
      });
    }
  }

  const stripped = stripJinja(text);
  try {
    JSON.parse(stripped);
  } catch (e) {
    const msg = e instanceof SyntaxError ? e.message : "Invalid JSON";
    diagnostics.push({ from: 0, to: text.length, severity: "error", message: msg });
  }

  return diagnostics;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const EXTENSIONS_BASE = [
  daisyEditorTheme,
  syntaxHighlighting(daisyHighlightStyle),
  lintGutter(),
  EditorView.lineWrapping,
];

const EXTENSIONS_JSON = [...EXTENSIONS_BASE, json(), linter(jsonLinter)];
const EXTENSIONS_JINJA = [...EXTENSIONS_BASE, json(), linter(jinjaJsonLinter)];

export default function CodeEditor({ value, onChange, mode = "json", minRows = 4 }: Props) {
  function handleFormat() {
    if (!value.trim()) return;
    try {
      if (mode === "jinja-json" && /\{\{|\{%/.test(value)) return;
      onChange(JSON.stringify(JSON.parse(value), null, 2));
    } catch {
      // invalid JSON — leave as-is
    }
  }

  return (
    <div className="relative rounded-lg overflow-hidden border border-base-300">
      <CodeMirror
        value={value}
        onChange={onChange}
        extensions={mode === "jinja-json" ? EXTENSIONS_JINJA : EXTENSIONS_JSON}
        theme="none"
        basicSetup={{ foldGutter: false, dropCursor: false, highlightActiveLine: false }}
        style={{ fontSize: "0.8rem" }}
        minHeight={`${minRows * 1.6}rem`}
      />
      <button
        type="button"
        onClick={handleFormat}
        title="Format JSON"
        className="absolute top-1 right-1 btn btn-xs btn-ghost opacity-40 hover:opacity-100 z-10 font-mono"
      >
        {"{ }"}
      </button>
    </div>
  );
}

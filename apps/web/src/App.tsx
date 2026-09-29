import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { LocalModelPicker, useLocalModels } from "./LocalModelPicker";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Box,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Database,
  FileCheck2,
  FileText,
  Filter,
  GitBranch,
  Layers3,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  Menu,
  Play,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import {
  api,
  ApiError,
  command,
  date,
  downloadFindings,
  label,
  number,
  setToken,
} from "./api";
import type {
  Audit,
  Dataset,
  Detail,
  Finding,
  Material,
  Overview,
  Page,
  Plan,
} from "./types";

type View =
  "overview" | "review" | "materials" | "remediation" | "audit" | "about";
const navItems: { id: View; name: string; icon: typeof Activity }[] = [
  { id: "overview", name: "Overview", icon: LayoutDashboard },
  { id: "review", name: "Review queue", icon: FileCheck2 },
  { id: "materials", name: "Material explorer", icon: Layers3 },
  { id: "remediation", name: "Remediation plan", icon: Workflow },
  { id: "audit", name: "Activity & audit", icon: Activity },
];
const colors: Record<string, string> = {
  duplicate: "#d5f58c",
  uom: "#efb37a",
  price: "#ada7ef",
  purchasing: "#7fc6bf",
  lifecycle: "#e18d8d",
  lead_time: "#a9b3a4",
};
function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <ShieldCheck size={30} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Pager({
  total,
  offset,
  setOffset,
}: {
  total: number;
  offset: number;
  setOffset: (n: number) => void;
}) {
  return (
    <div className="pager">
      <span>
        {total
          ? `${number(offset + 1)}–${number(Math.min(offset + 30, total))} of ${number(total)}`
          : "0 results"}
      </span>
      <div>
        <button
          aria-label="Previous page"
          disabled={!offset}
          onClick={() => setOffset(Math.max(offset - 30, 0))}
        >
          <ChevronLeft size={16} />
        </button>
        <button
          aria-label="Next page"
          disabled={offset + 30 >= total}
          onClick={() => setOffset(offset + 30)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
function FindingTable({
  items,
  onSelect,
}: {
  items: Finding[];
  onSelect: (id: string) => void;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Finding / material</th>
            <th>Category</th>
            <th>Priority</th>
            <th>Detection</th>
            <th>Status</th>
            <th>
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} onClick={() => onSelect(item.id)}>
              <td>
                <button
                  className="table-link"
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelect(item.id);
                  }}
                >
                  {item.title}
                </button>
                <span className="mono muted block">
                  {item.material_ids.join(" · ")}
                </span>
              </td>
              <td>
                <span
                  className="category-dot"
                  style={{ background: colors[item.kind] }}
                />
                {label(item.kind)}
              </td>
              <td>
                <Badge tone={item.severity}>{item.severity}</Badge>
              </td>
              <td>
                <span className="method">
                  {item.method === "rule" ? (
                    <GitBranch size={13} />
                  ) : (
                    <Sparkles size={13} />
                  )}{" "}
                  {item.method === "rule"
                    ? "Rule engine"
                    : item.method === "statistical"
                      ? "Peer statistics"
                      : item.method === "semantic_embedding"
                        ? "Semantic model"
                        : "Lexical model"}
                </span>
              </td>
              <td>
                <span className={"status " + item.status}>{item.status}</span>
              </td>
              <td>
                <ArrowUpRight size={15} className="muted" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function App() {
  const [view, setView] = useState<View>("overview"),
    [mobile, setMobile] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]),
    [selectedDataset, setSelectedDataset] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null),
    [config, setConfig] = useState<{
      auth_mode: string;
      llm_runtime: string;
      embedding_mode: string;
    } | null>(null);
  const [findings, setFindings] = useState<Page<Finding>>({
    items: [],
    total: 0,
    offset: 0,
    limit: 30,
  });
  const [materials, setMaterials] = useState<Page<Material>>({
    items: [],
    total: 0,
    offset: 0,
    limit: 30,
  });
  const [audits, setAudits] = useState<Page<Audit>>({
      items: [],
      total: 0,
      offset: 0,
      limit: 30,
    }),
    [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [kind, setKind] = useState(""),
    [status, setStatus] = useState(""),
    [group, setGroup] = useState(""),
    [source, setSource] = useState(""),
    [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0);
  const [detail, setDetail] = useState<Detail | null>(null),
    [detailLoading, setDetailLoading] = useState(false),
    [detailOpen, setDetailOpen] = useState(false),
    [reason, setReason] = useState(""),
    [evidenceTab, setEvidenceTab] = useState("computed");
  const [narrative, setNarrative] = useState<{
    finding_id: string;
    model: string;
    status: string;
    summary: string;
    evidence_ids: string[];
    normalization_suggestions: string[];
    limitations: string[];
  } | null>(null);
  const [importOpen, setImportOpen] = useState(false),
    [file, setFile] = useState<File | null>(null),
    [importResult, setImportResult] = useState<{
      dataset_id: string;
      valid_count: number;
      invalid_count: number;
      total: number;
    } | null>(null),
    [invalidRows, setInvalidRows] = useState<unknown[]>([]);
  const [trend, setTrend] = useState("overall");
  const [modelsOpen, setModelsOpen] = useState(false);
  const localModels = useLocalModels(revision);
  const [authOpen, setAuthOpen] = useState(false),
    [authToken, setAuthToken] = useState("");
  const refresh = () => setRevision((n) => n + 1);
  const fail = useCallback((e: unknown) => {
    setError(e instanceof Error ? e.message : "Something went wrong");
    if (e instanceof ApiError && e.status === 401) setAuthOpen(true);
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
      setOffset(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Page<Dataset>>("/datasets"),
      api<typeof config>("/config"),
    ])
      .then(([data, cfg]) => {
        if (active) {
          setDatasets(data.items);
          setConfig(cfg);
          if (data.items.length)
            setSelectedDataset((current) => current || data.items[0].id);
        }
      })
      .catch(fail);
    return () => {
      active = false;
    };
  }, [revision, fail]);
  useEffect(() => {
    if (!selectedDataset) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    const suffix = "?dataset_id=" + selectedDataset;
    const run = async () => {
      const summary = await api<Overview>("/overview" + suffix);
      if (!active) return;
      setOverview(summary);
      if (view === "overview" || view === "review") {
        const data = await api<Page<Finding>>(
          "/findings" +
            suffix +
            `&limit=30&offset=${view === "overview" ? 0 : offset}&kind=${encodeURIComponent(kind)}&status=${encodeURIComponent(view === "overview" ? "open" : status)}&search=${encodeURIComponent(query)}`,
        );
        if (active) setFindings(data);
      }
      if (view === "materials") {
        const data = await api<Page<Material>>(
          "/materials" +
            suffix +
            `&offset=${offset}&search=${encodeURIComponent(query)}${group ? "&group=" + encodeURIComponent(group) : ""}${source ? "&source=" + encodeURIComponent(source) : ""}`,
        );
        if (active) setMaterials(data);
      }
      if (view === "audit") {
        const data = await api<Page<Audit>>("/audit?offset=" + offset);
        if (active) setAudits(data);
      }
      if (view === "remediation") {
        const data = await api<{ items: Plan[] }>("/remediation" + suffix);
        if (active) setPlans(data.items);
      }
    };
    run()
      .catch((e) => {
        if (active) fail(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    selectedDataset,
    view,
    query,
    kind,
    status,
    group,
    source,
    offset,
    revision,
    fail,
  ]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  function navigate(next: View) {
    setView(next);
    setMobile(false);
    setOffset(0);
    setSearch("");
    setQuery("");
    setKind("");
    setStatus("");
    setGroup("");
    setSource("");
  }
  async function selectFinding(id: string) {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetail(null);
    setReason("");
    setNarrative(null);
    setEvidenceTab("computed");
    try {
      setDetail(await api<Detail>("/findings/" + id));
    } catch (e) {
      fail(e);
    } finally {
      setDetailLoading(false);
    }
  }
  async function runScan() {
    setBusy(true);
    setError("");
    try {
      await command("/datasets/" + selectedDataset + "/scan");
      refresh();
      setNotice("Quality scan complete. Evidence and trend snapshot updated.");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function decide(decision: string) {
    if (!detail) return;
    setBusy(true);
    try {
      await command("/findings/" + detail.id + "/review", {
        decision,
        reason,
        expected_version: detail.version,
      });
      setDetail(await api<Detail>("/findings/" + detail.id));
      refresh();
      setNotice(
        "Decision recorded in the audit history. Source data is unchanged.",
      );
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function explainFinding() {
    if (!detail || !localModels.selection || localModels.loading) return;
    setBusy(true);
    try {
      const response = await command<{
        explanation: Omit<
          NonNullable<typeof narrative>,
          "finding_id" | "model"
        >;
        telemetry: { model: string };
      }>("/findings/" + detail.id + "/explain", localModels.selection);
      setNarrative({
        ...response.result.explanation,
        finding_id: detail.id,
        model: response.result.telemetry.model,
      });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  async function showValidation() {
    const dataset = datasets.find((item) => item.id === selectedDataset);
    if (!dataset) return;
    setImportResult({
      dataset_id: dataset.id,
      total: dataset.total,
      valid_count: dataset.valid,
      invalid_count: dataset.invalid,
    });
    setImportOpen(true);
    try {
      setInvalidRows(
        (await api<Page<unknown>>("/datasets/" + dataset.id + "/validation"))
          .items,
      );
    } catch (e) {
      fail(e);
    }
  }
  async function importFile() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await api<{ result: NonNullable<typeof importResult> }>(
        "/commands/import",
        {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body,
        },
      );
      setImportResult(response.result);
      if (response.result.invalid_count) {
        const rejected = await api<Page<unknown>>(
          "/datasets/" + response.result.dataset_id + "/validation",
        );
        setInvalidRows(rejected.items);
      }
      setSelectedDataset(response.result.dataset_id);
      refresh();
      setNotice("Import saved with a visible validation report.");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  const metrics = overview?.metrics;
  const hasScan =
    overview?.dataset_id === selectedDataset &&
    metrics?.total_materials !== undefined;
  const counts = metrics?.by_kind || {};
  const critical =
    (metrics?.by_severity?.critical || 0) + (metrics?.by_severity?.high || 0);
  const currentName =
    view === "about"
      ? "Architecture & principles"
      : navItems.find((item) => item.id === view)?.name;
  let gradientStart = 0;
  const gradient = Object.entries(counts)
    .map(([key, value]) => {
      const start = gradientStart;
      gradientStart += (value / (metrics?.findings || 1)) * 100;
      return `${colors[key]} ${start}% ${gradientStart}%`;
    })
    .join(",");
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <aside className={"sidebar " + (mobile ? "mobile-open" : "")}>
        <div className="brand">
          <img src="/favicon.svg" alt="" />
          <span>
            MaterialMaster<span className="brand-ai">AI</span>
          </span>
        </div>
        <button
          className="workspace-select"
          onClick={() =>
            setNotice(
              "Local workspace · synthetic demo data. Import your own dataset to begin.",
            )
          }
        >
          <span className="workspace-icon">
            <Box size={17} />
          </span>
          <span>
            Manufacturing workspace<small>Local environment</small>
          </span>
          <ChevronDown size={13} />
        </button>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {navItems.map(({ id, name, icon: Icon }) => (
            <button
              key={id}
              className={view === id ? "active" : ""}
              onClick={() => navigate(id)}
            >
              <Icon size={18} />
              <span>{name}</span>
              {id === "review" && overview ? (
                <span className="nav-count">
                  {number(overview.review_counts.open || 0)}
                </span>
              ) : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button
            className="local-model-link"
            onClick={() => setModelsOpen(true)}
          >
            <Sparkles size={17} />
            <span>
              Local AI models
              <small>
                {localModels.selection?.model || "No model selected"}
              </small>
            </span>
            <ChevronRight size={14} />
          </button>
          <div className="local-card">
            <span className="online-dot" /> Your data stays local
            <p>
              Deterministic by design.
              <br />
              Human decisions, always.
            </p>
            <span className="small mono">OPEN SOURCE · APACHE 2.0</span>
          </div>
          <button
            className={"about-link " + (view === "about" ? "selected" : "")}
            onClick={() => navigate("about")}
          >
            <CircleHelp size={17} />
            Architecture & about
            <ArrowUpRight size={14} />
          </button>
          <button className="profile" onClick={() => setAuthOpen(true)}>
            <span className="avatar">MD</span>
            <span>
              Master-data steward
              <small>
                {config?.auth_mode === "demo"
                  ? "Local demo access"
                  : "Token access"}
              </small>
            </span>
            <ChevronDown size={14} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-toggle icon-button"
              aria-label="Toggle navigation"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={19} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{currentName}</strong>
          </div>
          <div className="topbar-right">
            <span className="environment">
              <span className="online-dot" />
              Local demo
            </span>
            <span className="top-divider" />
            <button
              className="icon-button"
              aria-label="Open architecture"
              onClick={() => navigate("about")}
            >
              <CircleHelp size={18} />
            </button>
            <span className="avatar small-avatar">MD</span>
          </div>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span /> MATERIAL INTELLIGENCE
              </div>
              <h1>
                {view === "overview"
                  ? "Better data. Better decisions."
                  : currentName}
              </h1>
              <p>
                {view === "overview"
                  ? "A clear view of your material master. Catch issues before they reach your supply chain."
                  : view === "review"
                    ? "Inspect the evidence. Make a decision. Keep a complete history."
                    : view === "materials"
                      ? "Explore source records, purchasing attributes and provenance."
                      : view === "remediation"
                        ? "Evidence-backed next steps, ready for an accountable human owner."
                        : view === "audit"
                          ? "Every import, scan and review. Traceable from source to decision."
                          : "Rules do the math. Models suggest. People decide."}
              </p>
            </div>
            {view !== "about" && (
              <div className="heading-actions">
                <button
                  className="button"
                  disabled={!selectedDataset || busy}
                  onClick={() => downloadFindings(selectedDataset).catch(fail)}
                >
                  <ArrowDownToLine size={15} />
                  Export
                </button>
                <button
                  className="button primary"
                  disabled={!selectedDataset || busy}
                  onClick={runScan}
                >
                  {busy ? (
                    <LoaderCircle size={15} className="spin" />
                  ) : (
                    <Play size={14} />
                  )}
                  Run quality scan
                </button>
              </div>
            )}
          </div>
          {error && (
            <div role="alert" className="alert">
              <span>{error}</span>
              <button
                onClick={() => {
                  setError("");
                  refresh();
                }}
              >
                Retry
              </button>
            </div>
          )}
          {view !== "about" && (
            <div className="scope-bar">
              <div>
                <Database size={15} />
                <label htmlFor="dataset">Dataset</label>
                <select
                  id="dataset"
                  value={selectedDataset}
                  onChange={(e) => {
                    setSelectedDataset(e.target.value);
                    setOffset(0);
                  }}
                >
                  {datasets.length === 0 && (
                    <option value="">No datasets yet</option>
                  )}
                  {datasets.map((dataset) => (
                    <option key={dataset.id} value={dataset.id}>
                      {dataset.name}
                    </option>
                  ))}
                </select>
                <Badge>Snapshot</Badge>
                {Boolean(
                  datasets.find((item) => item.id === selectedDataset)?.invalid,
                ) && (
                  <button className="badge high" onClick={showValidation}>
                    {
                      datasets.find((item) => item.id === selectedDataset)
                        ?.invalid
                    }{" "}
                    quarantined
                  </button>
                )}
              </div>
              <button
                className="text-button"
                onClick={() => {
                  setImportOpen(true);
                  setImportResult(null);
                  setInvalidRows([]);
                  setFile(null);
                }}
              >
                <Plus size={15} />
                Import dataset
              </button>
            </div>
          )}
          {loading && (
            <div className="loading-line" aria-label="Loading workspace" />
          )}
          {!loading && !datasets.length && view !== "about" && (
            <Empty title="Your quality workspace is ready">
              Import a JSON, JSONL or CSV snapshot to create your first
              validation report.
            </Empty>
          )}
          {view === "overview" && hasScan && metrics && (
            <>
              <section
                className="kpi-grid"
                aria-label="Computed quality metrics"
              >
                <article className="kpi">
                  <div className="kpi-label">
                    Materials in scope
                    <Database size={17} />
                  </div>
                  <div className="kpi-value">
                    {number(metrics.total_materials)}
                    <span>records</span>
                  </div>
                  <div className="kpi-foot">
                    <span className="tiny-dot lime" />
                    {Object.keys(metrics.by_source).length} source systems
                    <span className="muted">·</span>
                    {Object.keys(metrics.by_group).length} material groups
                  </div>
                  <div className="mini-bars" aria-hidden="true">
                    {Object.values(metrics.by_group).map((group, index) => (
                      <i
                        key={index}
                        style={{
                          height:
                            Math.max(
                              8,
                              (group.total / metrics.total_materials) * 150,
                            ) + "px",
                        }}
                      />
                    ))}
                  </div>
                </article>
                <article className="kpi quality">
                  <div className="kpi-label">
                    Material quality score
                    <ShieldCheck size={18} />
                  </div>
                  <div className="kpi-value">
                    {metrics.quality_score?.toFixed(1) ?? "—"}
                    <span>/ 100</span>
                  </div>
                  <div className="quality-track">
                    <i style={{ width: `${metrics.quality_score || 0}%` }} />
                  </div>
                  <div className="kpi-foot">
                    {number(
                      metrics.total_materials - metrics.affected_materials,
                    )}{" "}
                    materials with no detected findings
                  </div>
                </article>
                <article className="kpi">
                  <div className="kpi-label">
                    High-priority findings
                    <Zap size={18} />
                  </div>
                  <div className="kpi-value">
                    {number(critical)}
                    <span className="attention-label">need attention</span>
                  </div>
                  <div className="kpi-foot">
                    <span className="tiny-dot amber" />
                    {number(metrics.by_severity.critical || 0)} critical
                    <span className="muted">·</span>
                    {number(metrics.by_severity.high || 0)} high priority
                  </div>
                  <button
                    className="kpi-arrow"
                    aria-label="Open review queue"
                    onClick={() => navigate("review")}
                  >
                    <ArrowUpRight size={19} />
                  </button>
                </article>
              </section>
              <section className="analytics-grid">
                <article className="panel groups-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Quality across material groups</h2>
                      <p>Share of materials without a detected finding</p>
                    </div>
                    <Badge tone="computed">
                      <GitBranch size={11} />
                      Computed
                    </Badge>
                  </div>
                  <div className="group-chart">
                    {Object.entries(metrics.by_group)
                      .sort((a, b) => b[1].total - a[1].total)
                      .map(([name, cohort]) => (
                        <button
                          className="group-row"
                          key={name}
                          onClick={() => {
                            navigate("materials");
                            setGroup(name);
                          }}
                        >
                          <span>{name}</span>
                          <div className="bar-track">
                            <div
                              style={{ width: cohort.quality_score + "%" }}
                            />
                            <i style={{ left: cohort.quality_score + "%" }} />
                          </div>
                          <strong>
                            {cohort.quality_score.toFixed(1)}
                            <small>%</small>
                          </strong>
                          <span className="group-count">
                            {number(cohort.total)}
                          </span>
                        </button>
                      ))}
                  </div>
                  <div className="chart-footer">
                    <span>
                      <i className="tiny-dot lime" />
                      No detected findings
                    </span>
                    <span>
                      <i className="tiny-dot dim" />
                      Needs review
                    </span>
                    <span className="right muted">Record count →</span>
                  </div>
                </article>
                <article className="panel mix-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>What needs attention</h2>
                      <p>Findings by category</p>
                    </div>
                    <Filter size={16} className="muted" />
                  </div>
                  <div className="mix-body">
                    <div
                      className="donut"
                      role="img"
                      aria-label={`${metrics.findings} total findings`}
                      style={{
                        background: gradient
                          ? `conic-gradient(${gradient})`
                          : "#30372f",
                      }}
                    >
                      <div>
                        <strong>{number(metrics.findings)}</strong>
                        <span>total findings</span>
                      </div>
                    </div>
                    <div className="legend">
                      {Object.entries(counts).map(([key, count]) => (
                        <button
                          key={key}
                          onClick={() => {
                            navigate("review");
                            setKind(key);
                          }}
                        >
                          <span
                            className="category-dot"
                            style={{ background: colors[key] }}
                          />
                          <span>{label(key)}</span>
                          <strong>{number(count)}</strong>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="insight-note">
                    <ShieldCheck size={15} />
                    <span>
                      Every finding includes evidence. Nothing is auto-merged.
                    </span>
                  </div>
                </article>
              </section>
              <section className="panel queue-preview">
                <div className="panel-heading">
                  <div className="inline-title">
                    <h2>Your next decisions</h2>
                    <Badge>
                      {number(overview?.review_counts.open || 0)} open
                    </Badge>
                  </div>
                  <button
                    className="text-button"
                    onClick={() => navigate("review")}
                  >
                    View review queue
                    <ArrowRight size={15} />
                  </button>
                </div>
                {findings.items.length ? (
                  <FindingTable
                    items={findings.items.slice(0, 5)}
                    onSelect={selectFinding}
                  />
                ) : (
                  <Empty title="No findings in this snapshot">
                    Continue monitoring with your next import.
                  </Empty>
                )}
                <div className="panel-footer">
                  <span>
                    <span className="tiny-dot lime" />
                    Evidence ready for review
                  </span>
                  <span className="mono">
                    {metrics.algorithm_version} · {metrics.duration_seconds}s
                    scan
                  </span>
                </div>
              </section>
              <div className="bottom-grid">
                <section className="panel source-panel">
                  <div className="panel-heading">
                    <h2>Source system health</h2>
                    <Badge>Computed</Badge>
                  </div>
                  {Object.entries(metrics.by_source).map(([name, value]) => (
                    <button
                      className="source-row"
                      key={name}
                      onClick={() => {
                        navigate("materials");
                        setSource(name);
                      }}
                    >
                      <span className="source-icon">
                        <Database size={16} />
                      </span>
                      <div>
                        <strong>{name}</strong>
                        <small>{number(value.total)} materials</small>
                      </div>
                      <span className="source-score">
                        {value.quality_score.toFixed(1)}%<small>quality</small>
                      </span>
                      <ArrowUpRight size={15} />
                    </button>
                  ))}
                </section>
                <section className="panel history-panel">
                  <div className="panel-heading">
                    <h2>Quality history</h2>
                    <select
                      aria-label="Quality trend cohort"
                      value={trend}
                      onChange={(e) => setTrend(e.target.value)}
                    >
                      <option value="overall">All materials</option>
                      {Object.keys(metrics.by_group).map((name) => (
                        <option key={name} value={"group:" + name}>
                          {name}
                        </option>
                      ))}
                      {Object.keys(metrics.by_source).map((name) => (
                        <option key={name} value={"source:" + name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </div>
                  {(overview?.history.length || 0) < 2 ? (
                    <div className="history-start">
                      <Activity size={25} />
                      <div>
                        <h3>Your baseline is set.</h3>
                        <p>
                          Run another scan to track quality across snapshots.
                          Reviews change queue status; source quality changes
                          when corrected data is imported.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="history-list">
                      {overview?.history
                        .slice(-5)
                        .reverse()
                        .map((snapshot, index) => (
                          <div key={index}>
                            <span>{date(snapshot.at)}</span>
                            <div className="bar-track">
                              <div
                                style={{
                                  width:
                                    (trend === "overall"
                                      ? snapshot.quality_score || 0
                                      : trend.startsWith("group:")
                                        ? snapshot.by_group[trend.slice(6)]
                                            ?.quality_score || 0
                                        : snapshot.by_source[trend.slice(7)]
                                            ?.quality_score || 0) + "%",
                                }}
                              />
                            </div>
                            <strong>
                              {(trend === "overall"
                                ? snapshot.quality_score
                                : trend.startsWith("group:")
                                  ? snapshot.by_group[trend.slice(6)]
                                      ?.quality_score
                                  : snapshot.by_source[trend.slice(7)]
                                      ?.quality_score) ?? "N/A"}
                              %
                            </strong>
                          </div>
                        ))}
                    </div>
                  )}
                  <div className="panel-footer">
                    Actual workspace snapshots. Compare equivalent dataset
                    scopes.
                  </div>
                </section>
              </div>
            </>
          )}
          {!loading && overview && !hasScan && view === "overview" && (
            <Empty title="Import complete. Ready to inspect.">
              Run a quality scan to calculate findings and establish your
              baseline.
            </Empty>
          )}
          {view === "review" && (
            <section className="panel">
              <div className="table-toolbar">
                <div className="search-field">
                  <Search size={16} />
                  <input
                    aria-label="Search findings"
                    placeholder="Search findings or material IDs…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                  <span className="keyboard-hint">⌕</span>
                </div>
                <select
                  aria-label="Finding category"
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All categories</option>
                  {Object.keys(colors).map((key) => (
                    <option value={key} key={key}>
                      {label(key)}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Review status"
                  value={status}
                  onChange={(e) => {
                    setStatus(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All statuses</option>
                  {["open", "accepted", "rejected", "deferred"].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </div>
              <div className="review-explainer">
                <GitBranch size={14} />
                <span>
                  Rule evidence is authoritative. Model similarity is a
                  suggestion. Human feedback adjusts queue priority.
                </span>
              </div>
              {findings.items.length ? (
                <FindingTable items={findings.items} onSelect={selectFinding} />
              ) : (
                !loading && (
                  <Empty title="No matching findings">
                    Try a different search or filter.
                  </Empty>
                )
              )}
              <Pager
                total={findings.total}
                offset={offset}
                setOffset={setOffset}
              />
            </section>
          )}
          {view === "materials" && (
            <section className="panel">
              <div className="table-toolbar">
                <div className="search-field">
                  <Search size={16} />
                  <input
                    aria-label="Search materials"
                    placeholder="Search descriptions or material IDs…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <select
                  aria-label="Material group"
                  value={group}
                  onChange={(e) => {
                    setGroup(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All groups</option>
                  {Object.keys(metrics?.by_group || {}).map((key) => (
                    <option key={key}>{key}</option>
                  ))}
                </select>
                <select
                  aria-label="Source system"
                  value={source}
                  onChange={(e) => {
                    setSource(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All sources</option>
                  {Object.keys(metrics?.by_source || {}).map((key) => (
                    <option key={key}>{key}</option>
                  ))}
                </select>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Material / description</th>
                      <th>Group / source</th>
                      <th>Base → order</th>
                      <th>Raw price</th>
                      <th>Supplier</th>
                      <th>Lifecycle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {materials.items.map((row) => (
                      <tr key={row.material_id}>
                        <td>
                          <strong>{row.description}</strong>
                          <span className="mono muted block">
                            {row.material_id}
                          </span>
                        </td>
                        <td>
                          {row.material_group}
                          <span className="muted block small">
                            {row.source_system}
                          </span>
                        </td>
                        <td className="mono">
                          {row.base_uom} → {row.order_uom}
                          <span className="muted block small">
                            × {row.order_to_base_factor ?? "missing"}
                          </span>
                        </td>
                        <td className="mono">
                          {row.unit_price === null
                            ? "Missing"
                            : `${row.currency} ${Number(row.unit_price).toFixed(2)}`}
                          <span className="muted block small">
                            per {row.price_unit} {row.order_uom}
                          </span>
                        </td>
                        <td>
                          {row.supplier_id || (
                            <Badge tone="high">Missing</Badge>
                          )}
                        </td>
                        <td>
                          <Badge
                            tone={
                              row.lifecycle === "OBSOLETE"
                                ? "critical"
                                : "neutral"
                            }
                          >
                            {row.lifecycle}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!materials.items.length && !loading && (
                <Empty title="No matching materials">
                  Change your filters to explore this dataset.
                </Empty>
              )}
              <Pager
                total={materials.total}
                offset={offset}
                setOffset={setOffset}
              />
            </section>
          )}
          {view === "remediation" && (
            <>
              <div className="guidance">
                <LockKeyhole size={20} />
                <div>
                  <strong>Proposed actions. Human approval required.</strong>
                  <p>
                    Acceptance confirms a finding. Corrections belong in your
                    controlled ERP change process. This application does not
                    write to your ERP.
                  </p>
                </div>
                <Badge>{plans.length} proposals</Badge>
              </div>
              <div className="plan-grid">
                {Object.keys(colors)
                  .filter((key) => plans.some((plan) => plan.kind === key))
                  .map((key) => {
                    const matching = plans.filter((plan) => plan.kind === key);
                    return (
                      <article className="panel plan-card" key={key}>
                        <div className="plan-top">
                          <span
                            className="category-dot"
                            style={{ background: colors[key] }}
                          />
                          <h2>{label(key)}</h2>
                          <Badge>{matching.length}</Badge>
                        </div>
                        <p>{matching[0].action}</p>
                        <div className="plan-owner">
                          <span className="avatar">
                            {key === "duplicate" ? "MD" : "PO"}
                          </span>
                          <div>
                            <small>RESPONSIBLE ROLE</small>
                            <strong>{matching[0].owner_role}</strong>
                          </div>
                        </div>
                        <button
                          className="button"
                          onClick={() => {
                            navigate("review");
                            setKind(key);
                          }}
                        >
                          Review supporting findings
                          <ArrowRight size={15} />
                        </button>
                      </article>
                    );
                  })}
              </div>
              {!plans.length && !loading && (
                <Empty title="No remediation proposals">
                  Run a scan or adjust reviewed findings to build a plan.
                </Empty>
              )}
            </>
          )}
          {view === "audit" && (
            <section className="panel">
              <div className="panel-heading">
                <h2>Audit trail</h2>
                <Badge tone="computed">
                  <LockKeyhole size={11} />
                  Append-only application history
                </Badge>
              </div>
              <div className="audit-list">
                {audits.items.map((event) => (
                  <details key={event.id}>
                    <summary>
                      <span className="audit-icon">
                        {event.action.includes("review") ? (
                          <CheckCheck size={17} />
                        ) : event.action.includes("scan") ? (
                          <ShieldCheck size={17} />
                        ) : (
                          <Database size={17} />
                        )}
                      </span>
                      <div>
                        <strong>{event.action.replaceAll(".", " · ")}</strong>
                        <small>
                          {event.actor} <span>·</span>{" "}
                          {event.entity_id.slice(0, 36)}
                        </small>
                      </div>
                      <time>{date(event.at)}</time>
                      <ChevronDown size={15} />
                    </summary>
                    <div className="audit-body">
                      <p className="mono">TRACE {event.trace_id}</p>
                      <pre>{JSON.stringify(event.data, null, 2)}</pre>
                    </div>
                  </details>
                ))}
              </div>
              <Pager
                total={audits.total}
                offset={offset}
                setOffset={setOffset}
              />
            </section>
          )}
          {view === "about" && <About />}
          {metrics?.warning && <div className="alert">{metrics.warning}</div>}
          <footer className="app-footer">
            <span>
              <img src="/favicon.svg" alt="" />
              MaterialMaster AI<span className="muted">/</span>Evidence before
              action.
            </span>
            <span>
              Local-first<span>·</span>Open source<span>·</span>v0.1.0
            </span>
          </footer>
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <Check size={17} />
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={14} />
          </button>
        </div>
      )}
      <Dialog.Root open={detailOpen} onOpenChange={setDetailOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="drawer">
            <div className="drawer-heading">
              <span className="eyebrow">EVIDENCE WORKSPACE</span>
              <Dialog.Close className="icon-button" aria-label="Close finding">
                <X size={20} />
              </Dialog.Close>
            </div>
            <Dialog.Title>{detail?.title || "Loading finding…"}</Dialog.Title>
            <Dialog.Description className="muted">
              Review source evidence before taking a decision.
            </Dialog.Description>
            {detailLoading ? (
              <div className="empty">
                <LoaderCircle className="spin" />
              </div>
            ) : (
              detail && (
                <>
                  <div className="detail-badges">
                    <Badge tone={detail.severity}>
                      {detail.severity} priority
                    </Badge>
                    <Badge>{label(detail.kind)}</Badge>
                    <span className={"status " + detail.status}>
                      {detail.status}
                    </span>
                  </div>
                  <div className="detail-meta">
                    <span>
                      FINDING ID{" "}
                      <b className="mono">{detail.finding_id.slice(0, 12)}</b>
                    </span>
                    <span>
                      VERSION <b className="mono">{detail.version}</b>
                    </span>
                  </div>
                  <div
                    className="evidence-tabs"
                    role="tablist"
                    aria-label="Evidence type"
                  >
                    {["computed", "source", "history"].map((tab) => (
                      <button
                        key={tab}
                        role="tab"
                        aria-selected={evidenceTab === tab}
                        onClick={() => setEvidenceTab(tab)}
                      >
                        {tab === "computed"
                          ? "Detection evidence"
                          : tab === "source"
                            ? "Raw records"
                            : "Review history"}
                      </button>
                    ))}
                  </div>
                  {evidenceTab === "computed" && (
                    <div className="evidence-content">
                      <div className="section-label">
                        <GitBranch size={14} />
                        {detail.method === "rule"
                          ? "DETERMINISTIC RULE"
                          : detail.method === "statistical"
                            ? "COMPUTED STATISTICS"
                            : "MODEL PREDICTION"}
                      </div>
                      <dl className="evidence-list">
                        {Object.entries(detail.evidence)
                          .filter(([, value]) => value !== null)
                          .map(([key, value]) => (
                            <div key={key}>
                              <dt>{key.replaceAll("_", " ")}</dt>
                              <dd>
                                {typeof value === "boolean"
                                  ? value
                                    ? "Yes"
                                    : "No"
                                  : Array.isArray(value)
                                    ? value.join(" · ")
                                    : typeof value === "object"
                                      ? JSON.stringify(value)
                                      : String(value)}
                              </dd>
                            </div>
                          ))}
                      </dl>
                      <div className="action-proposal">
                        <span className="section-label">
                          <Workflow size={14} />
                          PROPOSED REMEDIATION
                        </span>
                        <p>{detail.proposed_action}</p>
                      </div>
                      <div className="ai-box">
                        <div>
                          <Sparkles size={16} />
                          <strong>Local AI explanation</strong>
                          <Badge>Optional narrative</Badge>
                        </div>
                        <LocalModelPicker state={localModels} disabled={busy} />
                        {narrative?.finding_id === detail.id ? (
                          <>
                            <p className="small muted">
                              Generated by{" "}
                              <span className="mono">{narrative.model}</span>
                            </p>
                            <p>{narrative.summary}</p>
                            {narrative.evidence_ids.length > 0 && (
                              <p className="mono small">
                                Sources: {narrative.evidence_ids.join(", ")}
                              </p>
                            )}
                            {narrative.normalization_suggestions.map(
                              (text, index) => (
                                <p key={index}>{text}</p>
                              ),
                            )}
                            <Badge
                              tone={
                                narrative.status === "abstained"
                                  ? "high"
                                  : "computed"
                              }
                            >
                              {narrative.status}
                            </Badge>
                          </>
                        ) : (
                          <p>
                            Generate a structured explanation from these
                            records. The model cannot change findings or source
                            data.
                          </p>
                        )}
                        <button
                          className="button"
                          disabled={
                            busy ||
                            localModels.loading ||
                            !localModels.selection
                          }
                          onClick={explainFinding}
                        >
                          <Sparkles size={14} />
                          Generate explanation
                        </button>
                      </div>
                    </div>
                  )}
                  {evidenceTab === "source" && (
                    <div className="evidence-content">
                      {detail.records.map((row) => (
                        <div className="raw-card" key={row.raw.material_id}>
                          <h3>
                            {row.raw.material_id}
                            <Badge>Raw source</Badge>
                          </h3>
                          <p className="small muted">
                            {row.raw.source_system} · Ingested{" "}
                            {date(row.ingested_at)}
                          </p>
                          <pre>{JSON.stringify(row.raw, null, 2)}</pre>
                          <p className="mono small muted">
                            DATASET {row.dataset_id}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                  {evidenceTab === "history" && (
                    <div className="evidence-content">
                      {detail.reviews.length ? (
                        detail.reviews.map((item, index) => (
                          <div className="review-history" key={index}>
                            <Badge>{item.decision}</Badge>
                            <p>{item.reason}</p>
                            <small>
                              {item.actor} · {date(item.at)}
                            </small>
                          </div>
                        ))
                      ) : (
                        <Empty title="Awaiting its first decision">
                          Your decision and reason will appear here.
                        </Empty>
                      )}
                    </div>
                  )}
                  <div className="decision-box">
                    <label htmlFor="reason">
                      Review note <span>Required · at least 5 characters</span>
                    </label>
                    <textarea
                      id="reason"
                      placeholder="What did you verify? Capture the reason for your decision…"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      maxLength={1000}
                    />
                    <div className="decision-buttons">
                      <button
                        className="button primary"
                        disabled={busy || reason.trim().length < 5}
                        onClick={() => decide("accepted")}
                      >
                        <Check size={15} />
                        Accept finding
                      </button>
                      <button
                        className="button"
                        disabled={busy || reason.trim().length < 5}
                        onClick={() => decide("rejected")}
                      >
                        Reject
                      </button>
                      <button
                        className="text-button"
                        disabled={busy || reason.trim().length < 5}
                        onClick={() => decide("deferred")}
                      >
                        Defer
                      </button>
                    </div>
                    <small>
                      <LockKeyhole size={11} />
                      Accepting confirms the issue. It does not merge or modify
                      a material.
                    </small>
                  </div>
                </>
              )
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={importOpen} onOpenChange={setImportOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="modal">
            <Dialog.Close
              className="modal-close icon-button"
              aria-label="Close import"
            >
              <X size={19} />
            </Dialog.Close>
            <div className="modal-icon">
              <Upload size={24} />
            </div>
            <Dialog.Title>Bring your data into focus.</Dialog.Title>
            <Dialog.Description>
              Import your ERP material and purchasing export as a CSV, JSON or
              JSONL snapshot. Every invalid row is preserved in a validation
              report.
            </Dialog.Description>
            {!importResult ? (
              <>
                <label className="upload-zone">
                  <Upload size={28} />
                  <strong>{file?.name || "Choose a material data file"}</strong>
                  <span>JSON, JSONL or CSV · UTF-8 · up to 20 MiB</span>
                  <input
                    type="file"
                    accept=".json,.jsonl,.csv"
                    aria-label="Material data file"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
                <p className="small muted">
                  Start with <code>data/sample/import-template.csv</code> in the
                  repository. Map your export columns to the template before
                  uploading.
                </p>
                <button
                  className="text-button source-guide-link"
                  onClick={() => {
                    setImportOpen(false);
                    navigate("about");
                  }}
                >
                  <Database size={14} /> Where does workplace data come from?{" "}
                  <ArrowRight size={14} />
                </button>
                <button
                  className="button primary full"
                  disabled={!file || busy}
                  onClick={importFile}
                >
                  {busy ? (
                    <LoaderCircle size={15} className="spin" />
                  ) : (
                    <Upload size={15} />
                  )}
                  Validate & import
                </button>
              </>
            ) : (
              <>
                <div className="import-stats">
                  <div>
                    <strong>{number(importResult.total)}</strong>
                    <span>received</span>
                  </div>
                  <div>
                    <strong>{number(importResult.valid_count)}</strong>
                    <span>valid</span>
                  </div>
                  <div>
                    <strong>{number(importResult.invalid_count)}</strong>
                    <span>quarantined</span>
                  </div>
                </div>
                {invalidRows.length > 0 && (
                  <details className="validation-details">
                    <summary>Inspect rejected rows (first 30)</summary>
                    <pre>{JSON.stringify(invalidRows, null, 2)}</pre>
                  </details>
                )}
                <button
                  className="button primary full"
                  disabled={busy}
                  onClick={() => {
                    setImportOpen(false);
                    navigate("overview");
                    setNotice(
                      "Dataset imported. Run a quality scan to calculate findings.",
                    );
                  }}
                >
                  Open imported dataset
                  <ArrowRight size={15} />
                </button>
              </>
            )}
            {error && (
              <p role="alert" className="error-text">
                {error}
              </p>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={modelsOpen} onOpenChange={setModelsOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="modal">
            <Dialog.Close
              className="modal-close icon-button"
              aria-label="Close model settings"
            >
              <X size={19} />
            </Dialog.Close>
            <div className="modal-icon">
              <Sparkles size={24} />
            </div>
            <Dialog.Title>Your device. Your model.</Dialog.Title>
            <Dialog.Description>
              Choose an installed local model for optional explanations. No
              default, automatic downloads or fallback model.
            </Dialog.Description>
            <LocalModelPicker state={localModels} />
            <div className="model-setup">
              <h3>Connect your local runtime</h3>
              <p>
                Run Ollama or llama.cpp on the machine hosting MaterialMaster.
                Point the app at that runtime using the local setup guide in{" "}
                <code>docs/ai-design.md</code>, then refresh this list.
              </p>
              <p>
                Models are discovered on the API host. A Docker runtime has its
                own model library unless you connect it to your device’s
                runtime.
              </p>
              <p>
                Quality checks, review decisions and exports work without
                choosing a model.
              </p>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={authOpen} onOpenChange={setAuthOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="modal">
            <Dialog.Close
              className="modal-close icon-button"
              aria-label="Close access settings"
            >
              <X size={19} />
            </Dialog.Close>
            <Dialog.Title>Workspace access</Dialog.Title>
            <Dialog.Description>
              Demo mode is local. If token authentication is enabled, enter a
              configured read or steward token. Tokens stay in memory only.
            </Dialog.Description>
            <label className="field-label" htmlFor="token">
              Access token
            </label>
            <input
              className="token-input"
              id="token"
              type="password"
              value={authToken}
              onChange={(e) => setAuthToken(e.target.value)}
              autoComplete="off"
            />
            <button
              className="button primary full"
              onClick={() => {
                setToken(authToken);
                setAuthToken("");
                setAuthOpen(false);
                refresh();
              }}
            >
              Apply access token
            </button>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

function About() {
  return (
    <>
      <section className="about-hero">
        <Badge tone="computed">OPEN SOURCE · LOCAL FIRST</Badge>
        <h2>
          Confidence in every
          <br />
          <span>material decision.</span>
        </h2>
        <p>
          MaterialMaster AI turns fragmented material and purchasing records
          into an evidence-led review workflow. Built for the people who keep
          supply chains running.
        </p>
        <div className="principles">
          <span>
            <ShieldCheck size={16} />
            Deterministic quality checks
          </span>
          <span>
            <LockKeyhole size={16} />
            No paid APIs
          </span>
          <span>
            <CheckCheck size={16} />
            Human control
          </span>
        </div>
      </section>
      <div className="architecture-flow">
        {[
          {
            icon: Database,
            title: "1. Ingest",
            text: "Typed material contract. Raw data and invalid rows preserved.",
          },
          {
            icon: GitBranch,
            title: "2. Detect",
            text: "Rules, robust price statistics and bounded similarity candidates.",
          },
          {
            icon: FileCheck2,
            title: "3. Review",
            text: "Source evidence, reasoned decisions and learned queue priority.",
          },
          {
            icon: Workflow,
            title: "4. Propose",
            text: "Auditable remediation plans. Source records stay untouched.",
          },
        ].map(({ icon: Icon, title, text }) => (
          <div className="panel" key={title}>
            <Icon size={24} />
            <h3>{title}</h3>
            <p>{text}</p>
          </div>
        ))}
      </div>
      <div className="about-grid">
        <section className="panel prose data-sources-panel">
          <span className="section-label">
            <Database size={14} /> YOUR WORKPLACE DATA
          </span>
          <h2>Start with the records you already own.</h2>
          <p>
            The demo is synthetic. For real work, use authorized exports from
            your ERP, purchasing system or data warehouse, then map them into
            the material template.
          </p>
          <div className="data-source-grid">
            <div>
              <strong>Material / item master</strong>
              <p>
                Item IDs, descriptions, material groups, manufacturer part
                numbers and lifecycle status.
              </p>
            </div>
            <div>
              <strong>Purchasing records</strong>
              <p>
                Suppliers, purchasing organizations, lead times, minimum
                quantities and purchase blocks.
              </p>
            </div>
            <div>
              <strong>UOM & pricing</strong>
              <p>
                Base and order units, pack conversions, purchase prices, price
                units and currency.
              </p>
            </div>
          </div>
          <p>
            <strong>Export → map → validate → review.</strong> CSV, JSON and
            JSONL are supported. Use{" "}
            <code>data/sample/import-template.csv</code> and the field mapping
            guide in <code>docs/data-sources.md</code>.
          </p>
          <p>
            Systems such as SAP, Oracle, Dynamics and Odoo can be upstream
            sources through exports you prepare. This version has no direct ERP
            connectors or writeback. Keep one purchasing context per material in
            each snapshot; separate plants or suppliers into separate snapshots
            when needed.
          </p>
        </section>
        <section className="panel prose">
          <h2>AI with a clearly defined job.</h2>
          <p>
            Scikit-learn lexical embeddings work without downloads. A local
            sentence-transformers adapter adds semantic similarity when you
            provide model files.
          </p>
          <p>
            Ollama and llama.cpp can explain findings using a strict response
            schema. Every explanation cites source IDs, and missing evidence or
            invalid output triggers abstention. Models have no tools that can
            mutate your data.
          </p>
          <Badge>Rules ≠ predictions ≠ generated narrative</Badge>
        </section>
        <section className="panel prose">
          <h2>Know the boundaries.</h2>
          <p>
            This is a runnable engineering reference with synthetic data, not a
            certified ERP connector. Price anomalies depend on comparable groups
            and currency; this version does not perform FX conversion.
          </p>
          <p>
            Candidate blocking trades recall for bounded computation. Human
            acceptance confirms a finding, not a completed ERP correction.
            Quality scores reflect detected findings and are not guarantees of
            correctness.
          </p>
          <a
            className="text-button"
            href="http://localhost:8120/docs"
            target="_blank"
            rel="noreferrer"
          >
            <FileText size={15} />
            Explore the local API reference
            <ArrowUpRight size={14} />
          </a>
        </section>
      </div>
    </>
  );
}

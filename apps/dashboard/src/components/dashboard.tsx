"use client";
import {
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
  type FormEvent,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Activity,
  ArrowDown,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BookOpen,
  Box,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  CircleHelp,
  Clock3,
  Code2,
  Download,
  ExternalLink,
  Eye,
  FileText,
  FlaskConical,
  Gauge,
  GitBranch,
  KeyRound,
  Layers3,
  Loader2,
  LogOut,
  Menu,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  Shield,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  Users,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link, Logo, Badge, Empty, Button, CopyButton, FormField } from "./ui";
import { Editor, type Modal } from "./editor";
import { BusinessView, OperationsSettings } from "./business";
import {
  api,
  money,
  number,
  type Customer,
  type Plan,
  type Alias,
  type Key,
  type Provider,
  type Tenant,
  type Log,
  type Usage,
} from "@/lib/api";

const nav = [
  { section: "overview", label: "Overview", icon: Gauge },
  { section: "insights", label: "Insights & alerts", icon: Activity },
  { section: "customers", label: "Customers", icon: Users },
  { section: "logs", label: "Request logs", icon: FileText },
  { section: "plans", label: "Plans & budgets", icon: Layers3 },
  { section: "aliases", label: "Model routing", icon: GitBranch },
  { section: "keys", label: "API keys", icon: KeyRound },
  { section: "providers", label: "Providers", icon: Box },
];
const providersLabel: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google Gemini",
  mock: "Mock provider",
};
const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
export default function Dashboard({
  section,
  detail,
}: {
  section: string;
  detail?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<{
    email: string;
    demo: boolean;
    role: string;
  } | null>(null);
  const [tenant, setTenant] = useState(
    searchParams.get("workspace") || "default",
  );
  const activeTenant = useRef(tenant);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [keys, setKeys] = useState<Key[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [system, setSystem] = useState<{
    status: string;
    worker: string;
    pending_events: number;
    checked_at: string;
  } | null>(null);
  const [logs, setLogs] = useState<Log[]>([]);
  const [totalLogs, setTotalLogs] = useState(0);
  const [days, setDays] = useState(Number(searchParams.get("days")) || 14);
  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [filter, setFilter] = useState(searchParams.get("status") || "all");
  const [offset, setOffset] = useState(Number(searchParams.get("offset")) || 0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState<Modal | null>(null);
  const [alerts, setAlerts] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const base = `/tenants/${tenant}`;
  const customerFilter = searchParams.get("customer") || "";
  const loadVersion = useRef(0);
  const loadAbort = useRef<AbortController | null>(null);
  const requestedWorkspace = searchParams.get("workspace") || "default";
  useEffect(() => {
    if (section === "login" || requestedWorkspace === activeTenant.current)
      return;
    activeTenant.current = requestedWorkspace;
    loadAbort.current?.abort();
    ++loadVersion.current;
    setTenant(requestedWorkspace);
    setWorkspaceOpen(false);
    setQuery("");
    setFilter("all");
    setOffset(0);
    setModal(null);
    setLoading(true);
  }, [requestedWorkspace, section]);
  const notify = (text: string) => {
    setToast(text);
    setTimeout(() => setToast(""), 4500);
  };
  const load = useCallback(async () => {
    if (activeTenant.current !== tenant) return;
    const version = ++loadVersion.current;
    loadAbort.current?.abort();
    const controller = new AbortController();
    loadAbort.current = controller;
    const get = <T,>(path: string) =>
      api<T>(path, { signal: controller.signal });
    try {
      const [u, t, c, p, a, k, v, stats, l, sys] = await Promise.all([
        get<{ email: string; demo: boolean; role: string }>("/auth/me"),
        get<Tenant[]>("/tenants"),
        get<Customer[]>(`${base}/customers`),
        get<Plan[]>(`${base}/plans`),
        get<Alias[]>(`${base}/aliases`),
        get<Key[]>(`${base}/keys`),
        get<Provider[]>(`/providers?tenant_id=${tenant}`),
        get<Usage>(`${base}/usage?days=${days}`),
        get<{ items: Log[]; total: number }>(
          `${base}/logs?limit=20&offset=${offset}&days=${days}&customer=${encodeURIComponent(customerFilter)}&q=${encodeURIComponent(query)}${filter === "success" || filter === "error" ? `&status=${filter}` : ""}`,
        ),
        get<{
          status: string;
          worker: string;
          pending_events: number;
          checked_at: string;
        }>("/status"),
      ]);
      if (version !== loadVersion.current) return;
      setUser(u);
      setTenants(t);
      setCustomers(c);
      setPlans(p);
      setAliases(a);
      setKeys(k);
      setProviders(v);
      setUsage(stats);
      setSystem(sys);
      setLogs(l.items);
      setTotalLogs(l.total);
      setError("");
      setLoading(false);
    } catch (e) {
      // A newer read owns the view; cancellation does not invalidate a completed write.
      if (!controller.signal.aborted) throw e;
    }
  }, [base, tenant, days, offset, query, filter, customerFilter]);
  useEffect(() => {
    if (section === "login") return;
    let alive = true;
    const timer = setTimeout(
      () => {
        load().catch((e) => {
          if (alive && e.name !== "AbortError") {
            setError(e.message);
            setLoading(false);
          }
        });
      },
      query ? 250 : 0,
    );
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [load, section, query]);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, []);
  useEffect(() => {
    if (!mobile) return;
    const previous = document.activeElement as HTMLElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const drawer = document.querySelector<HTMLElement>(".sidebar");
    const focusables = () =>
      Array.from(
        drawer?.querySelectorAll<HTMLElement>("a[href],button,select,input") ||
          [],
      ).filter((e) => !e.hasAttribute("disabled"));
    focusables()[0]?.focus();
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobile(false);
      if (e.key === "Tab") {
        const list = focusables(),
          first = list[0],
          last = list.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handle);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", handle);
      previous?.focus();
    };
  }, [mobile]);
  useEffect(() => {
    if (section === "login" || activeTenant.current !== tenant) return;
    const url = new URL(window.location.href);
    url.searchParams.set("workspace", tenant);
    url.searchParams.set("days", String(days));
    if (query) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    if (filter !== "all") url.searchParams.set("status", filter);
    else url.searchParams.delete("status");
    if (offset) url.searchParams.set("offset", String(offset));
    else url.searchParams.delete("offset");
    if (url.href !== window.location.href)
      window.history.replaceState({}, "", url);
  }, [tenant, days, query, filter, offset, section]);
  const refresh = async () => {
    setRefreshing(true);
    try {
      await load();
      notify("Workspace is up to date");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  };
  const switchWorkspace = (value: string) => {
    activeTenant.current = value;
    loadAbort.current?.abort();
    ++loadVersion.current;
    setMobile(false);
    setTenant(value);
    setWorkspaceOpen(false);
    setQuery("");
    setFilter("all");
    setOffset(0);
    setModal(null);
    setLoading(true);
    const url = new URL(window.location.href);
    url.searchParams.set("workspace", value);
    url.searchParams.delete("customer");
    window.history.replaceState({}, "", url);
  };
  const save = async (path: string, method: string, value?: unknown) => {
    const scope = tenant;
    const result = await api<unknown>(path, {
      method,
      ...(value ? { body: JSON.stringify(value) } : {}),
    });
    if (activeTenant.current === scope) await load();
    return result;
  };
  const exportLogs = () => {
    const rows = [
      [
        "Request ID",
        "Customer",
        "Model",
        "Tier",
        "Cost USD",
        "Latency ms",
        "Status",
        "Time",
      ],
      ...logs.map((l) => [
        l.id,
        l.customer_id,
        l.model,
        String(l.tier_served),
        String(l.cost / 1e6),
        String(l.latency_ms),
        l.status,
        l.created_at,
      ]),
    ];
    const csv = rows
      .map((r) =>
        r
          .map(
            (v) =>
              '"' +
              (/^[=+@\-\t\r]/.test(v) ? "'" + v : v).replaceAll('"', '""') +
              '"',
          )
          .join(","),
      )
      .join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "tollgate-requests.csv";
    a.click();
    URL.revokeObjectURL(url);
    notify("Current page exported");
  };
  if (section === "login") return <Login onSuccess={() => router.push("/")} />;
  const current =
    nav.find((n) => n.section === section)?.label ||
    { playground: "Playground", settings: "Settings & setup" }[section] ||
    "Page not found";
  const atRisk = customers.filter(
    (c) => c.tier > 0 || c.status === "exhausted",
  );
  const filteredCustomers = customers.filter(
    (c) =>
      (!query ||
        `${c.display_name} ${c.name}`
          .toLowerCase()
          .includes(query.toLowerCase())) &&
      (filter === "all" || c.status === filter),
  );
  const selectedCustomer = detail
    ? customers.find((c) => c.id === detail)
    : null;
  const aggregate = new Map<
    string,
    { day: string; cost: number; requests: number }
  >();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - i);
    const key = d.toISOString().slice(0, 10);
    aggregate.set(key, { day: key, cost: 0, requests: 0 });
  }
  usage?.daily.forEach((d) => {
    const a = aggregate.get(d.day);
    if (a) {
      a.cost += d.cost / 1e6;
      a.requests += d.requests;
    }
  });
  const chartData = [...aggregate.values()];
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobile && (
        <div className="mobile-backdrop" onClick={() => setMobile(false)} />
      )}
      <aside
        className={`sidebar ${mobile ? "is-open" : ""}`}
        role={mobile ? "dialog" : undefined}
        aria-modal={mobile ? true : undefined}
        aria-label="Workspace navigation"
        onClickCapture={(e) => {
          if ((e.target as HTMLElement).closest("a")) setMobile(false);
        }}
      >
        <Link href="/" className="brand-link" aria-label="Tollgate home">
          <Logo />
        </Link>
        <div className="workspace-wrap">
          <button
            className="workspace-switch"
            onClick={() => setWorkspaceOpen(!workspaceOpen)}
            aria-expanded={workspaceOpen}
          >
            <div className="workspace-avatar">A</div>
            <span>
              <strong>
                {tenants.find((t) => t.name === tenant)?.display_name ||
                  "Workspace"}
              </strong>
              <small>{user?.demo ? "Demo workspace" : "Workspace"}</small>
            </span>
            <ChevronsUpDown size={15} />
          </button>
          {workspaceOpen && (
            <div className="workspace-menu">
              {tenants.map((t) => (
                <button
                  key={t.id}
                  onClick={() => {
                    switchWorkspace(t.name);
                  }}
                >
                  {t.display_name}
                  {tenant === t.name && <Check size={15} />}
                </button>
              ))}
              <button
                onClick={() => {
                  setModal({ type: "tenant" });
                  setWorkspaceOpen(false);
                }}
              >
                <Plus size={15} /> Create workspace
              </button>
            </div>
          )}
        </div>
        <div className="sidebar-scroll">
          <div className="nav-label">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {nav.map((n) => (
              <Link
                onClick={() => {
                  setMobile(false);
                  setQuery("");
                  setFilter("all");
                  setOffset(0);
                }}
                key={n.section}
                className={`nav-item ${section === n.section ? "active" : ""}`}
                href={n.section === "overview" ? "/" : `/${n.section}`}
              >
                <n.icon size={18} />
                <span>{n.label}</span>
                {n.section === "customers" && customers.length > 0 && (
                  <small>{customers.length}</small>
                )}
              </Link>
            ))}
          </nav>
          <div className="nav-label tools-label">BUILD & TEST</div>
          <Link
            className={`nav-item ${section === "playground" ? "active" : ""}`}
            href="/playground"
          >
            <FlaskConical size={18} />
            <span>Playground</span>
            <span className="tiny-badge">TRY IT</span>
          </Link>
        </div>
        <div className="sidebar-bottom">
          <div className="gateway-status">
            <div className="status-orbit">
              <ShieldCheck size={18} />
            </div>
            <strong>
              {system?.status === "ready"
                ? "Gateway ready"
                : "Checking gateway…"}
            </strong>
            <small>
              {system
                ? `Worker: ${system.worker} · ${system.pending_events} events pending`
                : "Connecting to gateway"}
            </small>
            <Link href="/providers">
              Manage providers <ArrowUpRight size={13} />
            </Link>
          </div>
          <Link
            className={`nav-item ${section === "settings" ? "active" : ""}`}
            href="/settings"
          >
            <Settings2 size={18} />
            <span>Settings & setup</span>
          </Link>
          <a
            className="nav-item"
            href="/api/docs"
            target="_blank"
            rel="noreferrer"
          >
            <BookOpen size={18} />
            <span>API documentation</span>
            <ExternalLink size={13} />
          </a>
          <div className="user-menu">
            <div className="user-avatar">AD</div>
            <div>
              <strong>Administrator</strong>
              <small>{user?.email || "Connecting…"}</small>
            </div>
            <button
              className="icon-btn"
              title="Sign out"
              aria-label="Sign out"
              onClick={async () => {
                await api("/auth/logout", { method: "POST" });
                router.push("/login");
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-btn mobile-toggle"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{current}</strong>
          </div>
          <div className="topbar-right">
            <Link href="/settings" className="top-docs">
              <CircleHelp size={16} /> Quickstart guide{" "}
              <ArrowUpRight size={13} />
            </Link>
            <span className="top-divider" />
            <button
              className="icon-btn notification"
              aria-label="Budget alerts"
              aria-expanded={alerts}
              onClick={() => setAlerts(!alerts)}
            >
              <Bell size={18} />
              {atRisk.length > 0 && <i />}
            </button>
            <div className="top-avatar">A</div>
          </div>
          {alerts && (
            <div className="alert-popover">
              <h3>
                Budget alerts <span>{atRisk.length}</span>
              </h3>
              {atRisk.length ? (
                atRisk.map((c) => (
                  <Link
                    key={c.id}
                    href={`/customers/${c.id}`}
                    onClick={() => setAlerts(false)}
                  >
                    <span className="avatar amber">
                      {initials(c.display_name)}
                    </span>
                    <span>
                      <strong>{c.display_name}</strong>
                      <small>
                        {Math.round(c.ratio * 100)}% of budget used · Tier{" "}
                        {c.tier}
                      </small>
                    </span>
                    <ChevronRight size={15} />
                  </Link>
                ))
              ) : (
                <p>No budget alerts. Your customers are on track.</p>
              )}
            </div>
          )}
        </header>
        <main
          id="main-content"
          key={tenant}
          className={user?.role === "viewer" ? "read-only" : ""}
        >
          <div className="page-heading">
            <div>
              <div className="eyebrow">YOUR AI OPERATIONS, AT A GLANCE</div>
              <h1>
                {section === "overview"
                  ? "Overview"
                  : selectedCustomer?.display_name || current}
              </h1>
              <p>
                {
                  (
                    {
                      overview:
                        "A clear view of your AI usage. Every customer, every request, every dollar.",
                      customers:
                        "Know who’s using AI, what they spend, and when to step in.",
                      logs: "Trace every request from your application to the model and back.",
                      plans:
                        "Keep costs predictable. Keep the experience running.",
                      aliases:
                        "One model name in your code. A smarter route behind the scenes.",
                      keys: "Secure access to your gateway, scoped to this workspace.",
                      providers:
                        "Connect your models. Let Tollgate handle the rest.",
                      playground:
                        "See your gateway in action, before it reaches your users.",
                      settings:
                        "Everything you need to connect your application.",
                      insights:
                        "Know which features cost money, understand your margins, and act before a budget runs out.",
                    } as Record<string, string>
                  )[section]
                }
              </p>
            </div>
            <div className="heading-actions">
              {["overview", "logs", "insights"].includes(section) && (
                <>
                  <Button
                    variant="icon-only"
                    onClick={refresh}
                    disabled={refreshing}
                  >
                    <RefreshCw size={16} className={refreshing ? "spin" : ""} />
                    <span className="sr-only">Refresh data</span>
                  </Button>
                  <div className="select-wrap">
                    <Clock3 size={15} />
                    <select
                      aria-label="Date range"
                      value={days}
                      onChange={(e) => {
                        setDays(Number(e.target.value));
                        setOffset(0);
                      }}
                    >
                      <option value={7}>Last 7 days</option>
                      <option value={14}>Last 14 days</option>
                      <option value={30}>Last 30 days</option>
                    </select>
                    <ChevronDown size={14} />
                  </div>
                </>
              )}
              {section === "overview" && (
                <Link href="/playground" className="btn primary">
                  <FlaskConical size={16} /> Open playground
                </Link>
              )}
              {section === "customers" && (
                <Button
                  variant="primary"
                  onClick={() => setModal({ type: "customer" })}
                >
                  <Plus size={16} /> Add customer
                </Button>
              )}
              {section === "logs" && (
                <Button onClick={exportLogs}>
                  <Download size={16} /> Export page
                </Button>
              )}
              {section === "plans" && (
                <Button
                  variant="primary"
                  onClick={() => setModal({ type: "plan" })}
                >
                  <Plus size={16} /> Create plan
                </Button>
              )}
              {section === "aliases" && (
                <Button
                  variant="primary"
                  onClick={() => setModal({ type: "alias" })}
                >
                  <Plus size={16} /> Create alias
                </Button>
              )}
              {section === "keys" && (
                <Button
                  variant="primary"
                  onClick={() => setModal({ type: "key" })}
                >
                  <Plus size={16} /> Create API key
                </Button>
              )}
            </div>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button onClick={refresh}>Retry</button>
            </div>
          )}
          {!loading && system && (
            <div className="data-status">
              <span className="live-dot" /> Gateway checked{" "}
              {new Date(system.checked_at).toLocaleTimeString()} ·{" "}
              {system.worker === "inline"
                ? "Inline accounting"
                : `Ledger worker ${system.worker}`}{" "}
              · {system.pending_events} events awaiting ledger
            </div>
          )}
          {loading ? (
            <div className="page-loading">
              <Loader2 className="spin" size={28} />
              <p>Connecting to your workspace…</p>
            </div>
          ) : (
            <>
              {section === "overview" && usage && (
                <>
                  <div className="insight-banner">
                    <div className="insight-icon">
                      <Sparkles size={20} />
                    </div>
                    <div>
                      <strong>
                        Your AI keeps working. Your budget stays in check.
                      </strong>
                      <p>
                        {atRisk.length ? (
                          <>
                            {atRisk.length} customers are approaching their plan
                            limits. Review their budget eligibility.
                          </>
                        ) : (
                          "Automatic model tiers and sensitive data protection are ready for every request."
                        )}
                      </p>
                    </div>
                    <Link href="/plans">
                      View budget rules <ArrowRight size={16} />
                    </Link>
                    <span className="banner-decoration" />
                  </div>
                  <div className="stat-grid">
                    <Stat
                      label="Total AI spend"
                      value={money(usage.cost)}
                      icon={<span className="currency-icon">$</span>}
                      foot={`Across ${number(usage.requests)} requests`}
                      detail="Recorded usage · estimates are labeled"
                    />
                    <Stat
                      label="Gateway requests"
                      value={number(usage.requests)}
                      icon={<Activity size={19} />}
                      foot={`${usage.avg_latency_ms} ms average response`}
                      detail="All models, one gateway"
                    />
                    <Stat
                      label="Active customers"
                      value={number(usage.active_customers)}
                      icon={<Users size={19} />}
                      foot={`${usage.degraded_requests} requests served at lower tiers`}
                      detail="Graceful degradation active"
                    />
                    <Stat
                      label="Sensitive values protected"
                      value={number(usage.pii_protected)}
                      icon={<ShieldCheck size={19} />}
                      foot="Redacted before reaching providers"
                      detail="Policy-based detection, not a compliance guarantee"
                      green
                    />
                  </div>
                  <div className="overview-chart-grid">
                    <section className="panel spend-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Usage over time</h2>
                          <p>AI spend across your customers</p>
                        </div>
                        <span className="chart-legend">
                          <i /> Total spend
                        </span>
                      </div>
                      <div className="chart-summary">
                        <strong>{money(usage.cost)}</strong>
                        <span>over the last {days} days</span>
                      </div>
                      <div className="chart-area">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart
                            data={chartData}
                            margin={{
                              top: 12,
                              right: 10,
                              left: -28,
                              bottom: 0,
                            }}
                          >
                            <defs>
                              <linearGradient
                                id="spendGradient"
                                x1="0"
                                y1="0"
                                x2="0"
                                y2="1"
                              >
                                <stop
                                  offset="0%"
                                  stopColor="#8063db"
                                  stopOpacity={0.22}
                                />
                                <stop
                                  offset="100%"
                                  stopColor="#8063db"
                                  stopOpacity={0.01}
                                />
                              </linearGradient>
                            </defs>
                            <CartesianGrid
                              strokeDasharray="3 5"
                              vertical={false}
                              stroke="#eae9f0"
                            />
                            <XAxis
                              dataKey="day"
                              tickFormatter={(d) =>
                                new Date(d + "T12:00:00").toLocaleDateString(
                                  "en-US",
                                  { month: "short", day: "numeric" },
                                )
                              }
                              axisLine={false}
                              tickLine={false}
                              minTickGap={30}
                              tick={{ fill: "#95939f", fontSize: 11 }}
                              dy={9}
                            />
                            <YAxis
                              tickFormatter={(v) => `$${v}`}
                              axisLine={false}
                              tickLine={false}
                              tick={{ fill: "#95939f", fontSize: 11 }}
                            />
                            <Tooltip
                              formatter={(v) => [
                                `$${Number(v).toFixed(2)}`,
                                "Spend",
                              ]}
                              labelFormatter={(l) =>
                                new Date(
                                  String(l) + "T12:00:00",
                                ).toLocaleDateString("en-US", {
                                  month: "long",
                                  day: "numeric",
                                })
                              }
                              contentStyle={{
                                border: "1px solid #ece9f3",
                                borderRadius: 10,
                                fontSize: 12,
                              }}
                            />
                            <Area
                              isAnimationActive={false}
                              type="monotone"
                              dataKey="cost"
                              stroke="#8063db"
                              strokeWidth={2.5}
                              fill="url(#spendGradient)"
                              activeDot={{
                                r: 5,
                                stroke: "#fff",
                                strokeWidth: 3,
                              }}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="chart-footer">
                        <span>
                          <span className="live-dot" /> All costs recorded in
                          USD
                        </span>
                        <Link href="/logs">
                          Explore requests <ArrowUpRight size={14} />
                        </Link>
                      </div>
                    </section>
                    <section className="panel protection-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Your gateway at work</h2>
                          <p>Quietly keeping things under control</p>
                        </div>
                        <Shield size={18} className="muted" />
                      </div>
                      <ProtectionRow
                        icon={<GitBranch size={18} />}
                        title="Graceful degradation"
                        value={`${usage.degraded_requests} requests`}
                        desc="Lower cost. Zero interruptions."
                        color="purple"
                      />
                      <ProtectionRow
                        icon={<ShieldCheck size={18} />}
                        title="PII protection"
                        value={`${number(usage.pii_protected)} values`}
                        desc="Detected values protected by plan policy."
                        color="green"
                      />
                      <ProtectionRow
                        icon={<Zap size={18} />}
                        title="Response cache"
                        value={`${usage.requests ? Math.round((usage.cache_hits / usage.requests) * 100) : 0}% hit rate`}
                        desc="Faster answers. Fewer provider calls."
                        color="amber"
                      />
                      <div className="protection-note">
                        <span className="live-dot" />
                        <span>Protection follows each customer’s plan</span>
                      </div>
                    </section>
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <div className="title-inline">
                        <h2>Customer budgets</h2>
                        <span className="count-badge">{customers.length}</span>
                      </div>
                      <Link href="/customers" className="text-link">
                        View all customers <ArrowRight size={15} />
                      </Link>
                    </div>
                    <CustomerTable
                      customers={[...customers]
                        .sort((a, b) => b.ratio - a.ratio)
                        .slice(0, 5)}
                      onEdit={(c) => setModal({ type: "customer", value: c })}
                    />
                  </section>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Recent requests</h2>
                        <p>The latest activity through your gateway</p>
                      </div>
                      <Link href="/logs" className="text-link">
                        View request logs <ArrowRight size={15} />
                      </Link>
                    </div>
                    <LogTable
                      logs={usage.recent}
                      onSelect={(l) => setModal({ type: "log", value: l })}
                    />
                  </section>
                </>
              )}
              {section === "customers" && !selectedCustomer && (
                <>
                  <div className="mini-stats">
                    <span>
                      <strong>{customers.length}</strong> total customers
                    </span>
                    <span>
                      <i className="live-dot" />
                      <strong>
                        {customers.filter((c) => c.status === "healthy").length}
                      </strong>{" "}
                      on track
                    </span>
                    <span>
                      <i className="status-dot amber" />
                      <strong>{atRisk.length}</strong> automatically optimized
                    </span>
                    <span className="right">Current billing month</span>
                  </div>
                  <section className="panel">
                    <TableToolbar
                      query={query}
                      setQuery={setQuery}
                      inputRef={searchRef}
                      placeholder="Search by customer name or ID…"
                      filter={filter}
                      setFilter={setFilter}
                      options={[
                        ["all", "All customers"],
                        ["healthy", "On track"],
                        ["degraded", "Degraded"],
                        ["exhausted", "Exhausted"],
                      ]}
                    />
                    <CustomerTable
                      customers={filteredCustomers}
                      onEdit={(c) => setModal({ type: "customer", value: c })}
                    />
                  </section>
                  <div className="help-note">
                    <CircleHelp size={15} /> Customers are also created
                    automatically when their first request reaches your gateway.
                  </div>
                </>
              )}
              {section === "customers" && selectedCustomer && (
                <>
                  <Link href="/customers" className="back-link">
                    <ChevronLeft size={16} /> All customers
                  </Link>
                  <div className="stat-grid three">
                    <Stat
                      label="Monthly spend"
                      value={money(selectedCustomer.spend)}
                      icon={<Activity size={18} />}
                      foot={`${money(selectedCustomer.budget)} budget`}
                      detail="Current billing month"
                    />
                    <Stat
                      label="Budget consumed"
                      value={`${Math.round(selectedCustomer.ratio * 100)}%`}
                      icon={<Gauge size={18} />}
                      foot={`${money(Math.max(0, selectedCustomer.budget - selectedCustomer.spend))} remaining`}
                      detail={selectedCustomer.status}
                    />
                    <Stat
                      label="Current plan"
                      value={selectedCustomer.plan}
                      icon={<Layers3 size={18} />}
                      foot={`Budget eligibility tier ${selectedCustomer.tier} · ${selectedCustomer.name}`}
                      detail="Actual served tier depends on alias"
                    />
                  </div>
                  <section className="panel detail-panel">
                    <h2>Customer settings</h2>
                    <p>
                      Update the plan or set a custom budget for this customer.
                    </p>
                    <Button
                      variant="primary"
                      onClick={() =>
                        setModal({ type: "customer", value: selectedCustomer })
                      }
                    >
                      Edit customer
                    </Button>
                    <Link
                      className="btn"
                      href={`/logs?workspace=${tenant}&customer=${encodeURIComponent(selectedCustomer.name)}`}
                    >
                      Open request logs <ArrowUpRight size={15} />
                    </Link>
                  </section>
                </>
              )}
              {section === "logs" && (
                <section className="panel">
                  {customerFilter && (
                    <div className="info-banner">
                      Showing customer: <code>{customerFilter}</code>
                      <Link
                        className="text-link"
                        href={`/logs?workspace=${tenant}&days=${days}`}
                      >
                        Clear customer filter
                      </Link>
                    </div>
                  )}
                  <TableToolbar
                    query={query}
                    setQuery={(v) => {
                      setQuery(v);
                      setOffset(0);
                    }}
                    inputRef={searchRef}
                    placeholder="Search customer, request ID, model…"
                    filter={filter}
                    setFilter={(v) => {
                      setFilter(v);
                      setOffset(0);
                    }}
                    options={[
                      ["all", "All statuses"],
                      ["success", "Successful"],
                      ["error", "Failed"],
                    ]}
                  />
                  <LogTable
                    logs={logs}
                    onSelect={(l) => setModal({ type: "log", value: l })}
                  />
                  <div className="table-pagination">
                    <span>
                      {totalLogs
                        ? `${offset + 1}–${Math.min(offset + 20, totalLogs)}`
                        : "0"}{" "}
                      of {totalLogs} requests
                    </span>
                    <div>
                      <Button
                        disabled={offset === 0}
                        onClick={() => setOffset(Math.max(0, offset - 20))}
                      >
                        <ChevronLeft size={15} /> Previous
                      </Button>
                      <Button
                        disabled={offset + 20 >= totalLogs}
                        onClick={() => setOffset(offset + 20)}
                      >
                        Next <ChevronRight size={15} />
                      </Button>
                    </div>
                  </div>
                </section>
              )}
              {section === "plans" && (
                <>
                  <div className="info-banner">
                    <GitBranch size={18} />
                    <span>
                      <strong>
                        Degrade gracefully, instead of cutting customers off.
                      </strong>{" "}
                      Model tiers step down at the thresholds you set. Hard
                      limits apply only when the budget runs out.
                    </span>
                  </div>
                  <div className="plan-grid">
                    {plans.map((p) => (
                      <section className="panel plan-card" key={p.id}>
                        <div className="plan-top">
                          <span className="plan-icon">
                            <Layers3 size={21} />
                          </span>
                          <Badge tone={p.name === "Pro" ? "purple" : "neutral"}>
                            {customers.filter((c) => c.plan === p.name).length}{" "}
                            customers
                          </Badge>
                        </div>
                        <h2>{p.name}</h2>
                        <div className="plan-price">
                          {money(p.monthly_budget)}
                          <span>/ customer / month</span>
                        </div>
                        <div className="plan-feature">
                          <Check size={16} />
                          {p.rpm} requests per minute
                        </div>
                        <div className="plan-feature">
                          <ShieldCheck size={16} />
                          {p.pii_mode === "reversible"
                            ? "Reversible PII protection"
                            : `${p.pii_mode} redaction`}
                        </div>
                        <div className="plan-divider" />
                        <div className="eyebrow">DEGRADATION LADDER</div>
                        <div className="ladder-step">
                          <span>0</span>
                          <div>
                            <strong>Full quality</strong>
                            <small>At the start of the budget</small>
                          </div>
                        </div>
                        {p.degradation.map((s, i) => (
                          <div className="ladder-step" key={i}>
                            <span>{s.tier}</span>
                            <div>
                              <strong>Tier {s.tier}</strong>
                              <small>
                                At {s.at * 100}% of the monthly budget
                              </small>
                            </div>
                            <ArrowDown size={14} />
                          </div>
                        ))}
                        <div className="plan-exhaust">
                          At 100%{" "}
                          <span>
                            {p.on_exhausted === "block"
                              ? "Pause requests"
                              : `Allow ${money(p.overage_cap)} overage`}
                          </span>
                        </div>
                        <Button
                          onClick={() => setModal({ type: "plan", value: p })}
                        >
                          Edit plan <ArrowRight size={15} />
                        </Button>
                      </section>
                    ))}
                  </div>
                </>
              )}
              {section === "aliases" && (
                <>
                  <div className="info-banner">
                    <GitBranch size={18} />
                    <span>
                      <strong>
                        Degradation moves down. Fallback moves across.
                      </strong>{" "}
                      Your budget chooses the tier; provider health chooses a
                      target within it.
                    </span>
                  </div>
                  {aliases.map((a) => (
                    <section className="panel alias-card" key={a.id}>
                      <div className="panel-heading">
                        <div className="title-inline">
                          <code>{a.name}</code>
                          <Badge tone={a.allow_degrade ? "green" : "neutral"}>
                            {a.allow_degrade
                              ? "Degradation on"
                              : "Quality locked"}
                          </Badge>
                        </div>
                        <Button
                          onClick={() => setModal({ type: "alias", value: a })}
                        >
                          Edit routing <Settings2 size={14} />
                        </Button>
                      </div>
                      <div className="routing-ladder">
                        {a.tiers.map((tier, i) => (
                          <div className="routing-row" key={i}>
                            <div className="tier-label">
                              Tier {i}
                              <small>
                                {["Best quality", "Balanced", "Lowest cost"][
                                  i
                                ] || "Economy"}
                              </small>
                            </div>
                            {tier.map((target, j) => (
                              <div
                                className="routing-target-wrap"
                                key={target + j}
                              >
                                {j > 0 && (
                                  <>
                                    <ArrowRight size={16} />
                                    <small className="fallback-label">
                                      fallback
                                    </small>
                                  </>
                                )}
                                <div className="routing-target">
                                  <span
                                    className={`provider-glyph ${target.split("/")[0]}`}
                                  >
                                    <Sparkles size={15} />
                                  </span>
                                  <code>{target}</code>
                                </div>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </>
              )}
              {section === "keys" && (
                <>
                  <div className="info-banner">
                    <KeyRound size={18} />
                    <span>
                      <strong>Keys are only shown once.</strong> Store them
                      securely on your server. Revoking a key takes effect
                      immediately.
                    </span>
                  </div>
                  <section className="panel">
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>NAME</th>
                            <th>KEY PREFIX</th>
                            <th>ACCESS</th>
                            <th>CREATED</th>
                            <th>STATUS</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {keys.map((k) => (
                            <tr key={k.id}>
                              <td>
                                <div className="name-cell">
                                  <span className="table-icon">
                                    <KeyRound size={17} />
                                  </span>
                                  <strong>{k.name}</strong>
                                </div>
                              </td>
                              <td>
                                <code>{k.prefix}••••••••</code>
                              </td>
                              <td>
                                {k.scope === "usage"
                                  ? `Usage only · ${k.customer}`
                                  : "Gateway"}
                              </td>
                              <td>
                                {new Date(k.created_at).toLocaleDateString(
                                  "en-US",
                                  {
                                    month: "short",
                                    day: "numeric",
                                    year: "numeric",
                                  },
                                )}
                              </td>
                              <td>
                                <Badge
                                  tone={k.revoked_at ? "neutral" : "green"}
                                >
                                  {k.revoked_at ? "Revoked" : "Active"}
                                </Badge>
                              </td>
                              <td>
                                {!k.revoked_at && (
                                  <Button
                                    variant="danger-quiet"
                                    onClick={() =>
                                      setModal({ type: "revoke", value: k })
                                    }
                                  >
                                    <Trash2 size={14} /> Revoke
                                  </Button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {!keys.length && (
                      <Empty
                        title="No API keys yet"
                        description="Create your first key to connect an application."
                      />
                    )}
                  </section>
                </>
              )}
              {section === "providers" && (
                <>
                  <div className="provider-grid">
                    {providers.map((p, i) => (
                      <section className="panel provider-card" key={p.name}>
                        <div className="provider-card-top">
                          <div className={`provider-logo ${p.name}`}>
                            {p.name === "openai" ? (
                              <Sparkles size={27} />
                            ) : p.name === "anthropic" ? (
                              <span>AI</span>
                            ) : p.name === "google" ? (
                              <Sparkles size={28} />
                            ) : (
                              <Terminal size={25} />
                            )}
                          </div>
                          <Badge tone={p.configured ? "green" : "neutral"}>
                            {p.configured
                              ? p.name === "mock"
                                ? "Ready"
                                : "Key configured"
                              : "Not configured"}
                          </Badge>
                        </div>
                        <h2>{providersLabel[p.name]}</h2>
                        <p>
                          {
                            [
                              "Versatile models for everyday intelligence.",
                              "Thoughtful reasoning for complex tasks.",
                              "Fast, efficient intelligence from Google.",
                              "Explore the full gateway with zero API keys.",
                            ][i]
                          }
                        </p>
                        <div className="provider-models">
                          {p.models
                            .filter((m) => !m.includes("outage"))
                            .slice(0, 3)
                            .map((m) => (
                              <code key={m}>{m.split("/")[1]}</code>
                            ))}
                        </div>
                        {p.name !== "mock" ? (
                          <Button
                            variant={p.configured ? "" : "primary"}
                            onClick={() =>
                              setModal({ type: "provider", value: p })
                            }
                          >
                            {p.configured
                              ? "Update API key"
                              : "Connect provider"}
                            <ArrowRight size={15} />
                          </Button>
                        ) : (
                          <Link href="/playground" className="btn">
                            Try mock provider <FlaskConical size={15} />
                          </Link>
                        )}
                      </section>
                    ))}
                  </div>
                  <div className="help-note">
                    <ShieldCheck size={16} /> Provider keys are encrypted at
                    rest and are never returned after saving. Connect a
                    provider, then update your model routing.
                  </div>
                </>
              )}
              {section === "playground" && (
                <Playground
                  key={tenant}
                  customers={customers}
                  aliases={aliases}
                  base={base}
                  onRequest={() => {
                    load().catch(() => {});
                  }}
                />
              )}
              {section === "insights" && usage && (
                <BusinessView
                  usage={usage}
                  customers={customers}
                  workspace={tenant}
                />
              )}
              {section === "settings" && (
                <SettingsView
                  key={tenant}
                  workspace={tenant}
                  readOnly={user?.role === "viewer"}
                  tenant={tenants.find((t) => t.name === tenant)}
                  plans={plans}
                  demo={user?.demo || false}
                  save={save}
                  notify={notify}
                />
              )}
              {![
                "overview",
                "insights",
                "customers",
                "logs",
                "plans",
                "aliases",
                "keys",
                "providers",
                "playground",
                "settings",
              ].includes(section) && (
                <Empty
                  title="This page couldn’t be found"
                  description="Use the navigation to return to your workspace."
                  action={
                    <Link href="/" className="btn primary">
                      Back to overview
                    </Link>
                  }
                />
              )}
            </>
          )}
          <footer className="page-footer">
            <span>
              <Logo small /> Tollgate{" "}
              <span className="footer-version">v0.2.0</span>
            </span>
            <span>
              Meter. Limit. Protect. <span className="footer-separator">·</span>{" "}
              Built for a better AI experience.
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCheck size={18} />
          {toast}
          <button
            className="icon-btn"
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {modal && (
        <Editor
          key={
            tenant +
            modal.type +
            (modal.value && "id" in modal.value ? modal.value.id : "new")
          }
          modal={modal}
          close={() => setModal(null)}
          plans={plans}
          providers={providers}
          base={base}
          tenant={tenant}
          save={save}
          notify={notify}
        />
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
  foot,
  detail,
  green = false,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  foot: string;
  detail: string;
  green?: boolean;
}) {
  return (
    <section className="stat-card">
      <div className="stat-top">
        <span>{label}</span>
        <div className={`stat-icon ${green ? "green" : ""}`}>{icon}</div>
      </div>
      <strong className="stat-value">{value}</strong>
      <div className="stat-foot">
        {green ? <ShieldCheck size={13} /> : <span className="small-dot" />}
        {foot}
      </div>
      <small>{detail}</small>
    </section>
  );
}
function ProtectionRow({
  icon,
  title,
  value,
  desc,
  color,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  desc: string;
  color: string;
}) {
  return (
    <div className="protection-row">
      <span className={`protection-icon ${color}`}>{icon}</span>
      <div>
        <strong>{title}</strong>
        <small>{desc}</small>
      </div>
      <span className="protection-value">{value}</span>
    </div>
  );
}
function CustomerTable({
  customers,
  onEdit,
}: {
  customers: Customer[];
  onEdit: (c: Customer) => void;
}) {
  return customers.length ? (
    <>
      <div className="table-scroll customer-table-wrap">
        <table className="customer-table">
          <thead>
            <tr>
              <th>CUSTOMER</th>
              <th>PLAN</th>
              <th>MONTHLY SPEND</th>
              <th>BUDGET USED</th>
              <th>BUDGET TIER ELIGIBILITY</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {customers.map((c, i) => (
              <tr key={c.id}>
                <td>
                  <Link href={`/customers/${c.id}`} className="name-cell">
                    <span className={`avatar color-${i % 5}`}>
                      {initials(c.display_name)}
                    </span>
                    <span>
                      <strong>{c.display_name}</strong>
                      <small>{c.name}</small>
                    </span>
                  </Link>
                </td>
                <td>
                  <span className="plan-tag">{c.plan}</span>
                </td>
                <td>
                  <strong className="spend-amount">{money(c.spend)}</strong>
                  <span className="budget-total"> / {money(c.budget, 0)}</span>
                </td>
                <td>
                  <div
                    className={`budget-meter ${c.ratio >= 0.95 ? "danger" : c.ratio >= 0.8 ? "warning" : ""}`}
                  >
                    <div>
                      <span
                        style={{ width: `${Math.min(100, c.ratio * 100)}%` }}
                      />
                    </div>
                    <span>{Math.round(c.ratio * 100)}%</span>
                  </div>
                </td>
                <td>
                  <span className={`tier-pill tier-${c.tier}`}>
                    {c.tier === 0 ? (
                      <span className="tier-dot" />
                    ) : (
                      <ArrowDownLeft size={12} />
                    )}
                    Tier {c.tier}
                    <small>
                      {["Standard", "Balanced", "Economy"][c.tier] || ""}
                    </small>
                  </span>
                </td>
                <td>
                  <button
                    className="icon-btn"
                    aria-label={`Edit ${c.display_name}`}
                    onClick={() => onEdit(c)}
                  >
                    <MoreHorizontal size={18} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mobile-customer-list">
        {customers.map((c, i) => (
          <article className="mobile-customer-card" key={c.id}>
            <div>
              <Link className="name-cell" href={`/customers/${c.id}`}>
                <span className={`avatar color-${i % 5}`}>
                  {initials(c.display_name)}
                </span>
                <span>
                  <strong>{c.display_name}</strong>
                  <small>{c.name}</small>
                </span>
              </Link>
              <button
                className="icon-btn"
                aria-label={`Edit ${c.display_name} mobile`}
                onClick={() => onEdit(c)}
              >
                <MoreHorizontal size={18} />
              </button>
            </div>
            <div className="mobile-budget">
              <span>
                <strong>{money(c.spend)}</strong> of {money(c.budget, 0)}
              </span>
              <span>{Math.round(c.ratio * 100)}%</span>
            </div>
            <div
              className={`mobile-budget-track ${c.ratio >= 0.95 ? "danger" : c.ratio >= 0.8 ? "warning" : ""}`}
            >
              <span style={{ width: `${Math.min(100, c.ratio * 100)}%` }} />
            </div>
            <div className="mobile-customer-foot">
              <span>{c.plan} plan</span>
              <span className={`tier-pill tier-${c.tier}`}>
                Tier {c.tier} · {["Standard", "Balanced", "Economy"][c.tier]}
              </span>
            </div>
          </article>
        ))}
      </div>
    </>
  ) : (
    <Empty
      title="No customers found"
      description="Add a customer or try a different search."
    />
  );
}
function LogTable({
  logs,
  onSelect,
}: {
  logs: Log[];
  onSelect: (l: Log) => void;
}) {
  return logs.length ? (
    <div className="table-scroll">
      <table className="log-table">
        <thead>
          <tr>
            <th>REQUEST / CUSTOMER</th>
            <th>MODEL</th>
            <th>STATUS</th>
            <th>TOKENS</th>
            <th>COST</th>
            <th>LATENCY</th>
            <th>TIME</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <tr
              key={l.id}
              onClick={() => onSelect(l)}
              className="clickable-row"
            >
              <td>
                <strong className="request-id">{l.id.slice(0, 8)}…</strong>
                <small className="cell-small">{l.customer_id}</small>
              </td>
              <td>
                <code>{l.model}</code>
                {l.cache_hit && (
                  <span className="cache-tag">
                    <Zap size={10} /> Cached
                  </span>
                )}
              </td>
              <td>
                <Badge tone={l.status === "success" ? "green" : "red"}>
                  {l.status === "success" ? "Success" : "Failed"}
                </Badge>
              </td>
              <td>{number(l.input_tokens + l.output_tokens)}</td>
              <td>{money(l.cost, 4)}</td>
              <td>
                {l.latency_ms} <span className="muted">ms</span>
              </td>
              <td className="nowrap">
                {new Date(l.created_at).toLocaleTimeString("en-US", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </td>
              <td>
                <button
                  className="icon-btn"
                  aria-label={`View request ${l.id}`}
                  onClick={() => onSelect(l)}
                >
                  <ArrowUpRight size={15} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty
      title="No requests found"
      description="Send a request from the playground or adjust your filters."
    />
  );
}
function TableToolbar({
  query,
  setQuery,
  placeholder,
  filter,
  setFilter,
  options,
  inputRef,
}: {
  query: string;
  setQuery: (s: string) => void;
  placeholder: string;
  filter: string;
  setFilter: (s: string) => void;
  options: string[][];
  inputRef: React.RefObject<HTMLInputElement | null>;
}) {
  return (
    <div className="table-toolbar">
      <div className="table-search">
        <Search size={17} />
        <input
          ref={inputRef}
          aria-label="Search records"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
        />
        <kbd>/</kbd>
      </div>
      <div className="select-wrap">
        <select
          aria-label="Filter records"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {options.map(([v, l]) => (
            <option value={v} key={v}>
              {l}
            </option>
          ))}
        </select>
        <ChevronDown size={14} />
      </div>
    </div>
  );
}

function Playground({
  customers,
  aliases,
  base,
  onRequest,
}: {
  customers: Customer[];
  aliases: Alias[];
  base: string;
  onRequest: () => void;
}) {
  const [feature, setFeature] = useState("general");
  const [environment, setEnvironment] = useState("production");
  const [prompt, setPrompt] = useState(
    "Draft a friendly refund update to ali@example.com. Let them know we’ll call 0300-1234567 with the next steps.",
  );
  const [customer, setCustomer] = useState(customers[0]?.name || "playground");
  const [alias, setAlias] = useState(aliases[0]?.name || "smart");
  const [stream, setStream] = useState(true);
  const [deterministic, setDeterministic] = useState(false);
  const [output, setOutput] = useState("");
  const [preview, setPreview] = useState<{
    redacted: string;
    counts: Record<string, number>;
    blocked: boolean;
    category?: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState<{
    tier: string;
    model: string;
    cache: string;
    remaining: string;
  } | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  const previewPrompt = async () => {
    try {
      const p = await api<typeof preview>("/pii/preview", {
        method: "POST",
        body: JSON.stringify({
          text: prompt,
          tenant_id: base.split("/")[2],
          customer,
        }),
      });
      setPreview(p);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const send = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setOutput("");
    setInfo(null);
    const controller = new AbortController();
    abort.current = controller;
    try {
      const c = customers.find((c) => c.name === customer);
      const response = await fetch(`/api/admin/v1${base}/playground`, {
        method: "POST",
        signal: controller.signal,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Tollgate-Admin": "1",
        },
        body: JSON.stringify({
          model: alias,
          user: customer,
          feature,
          environment,
          messages: [{ role: "user", content: prompt }],
          stream,
          temperature: deterministic ? 0 : 0.7,
          max_tokens: 512,
        }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Request failed");
      }
      setInfo({
        tier: response.headers.get("x-tollgate-tier") || String(c?.tier || 0),
        model: response.headers.get("x-tollgate-model-served") || alias,
        cache: response.headers.get("x-tollgate-cache") || "MISS",
        remaining:
          response.headers.get("x-tollgate-budget-remaining-usd") || "0",
      });
      if (!stream) {
        const data = await response.json();
        setOutput(data.choices[0].message.content);
      } else {
        const reader = response.body!.getReader(),
          decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() || "";
          for (const f of frames) {
            const data = f
              .split("\n")
              .find((l) => l.startsWith("data: "))
              ?.slice(6);
            if (!data || data === "[DONE]") continue;
            const chunk = JSON.parse(data);
            if (chunk.error) throw new Error(chunk.error.message);
            const text = chunk.choices?.[0]?.delta?.content;
            if (text) setOutput((prev) => prev + text);
          }
        }
      }
      onRequest();
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="playground-grid">
        <section className="panel playground-input">
          <div className="panel-heading">
            <h2>
              <Terminal size={17} /> Request
            </h2>
            <span className="subtle-tag">OpenAI compatible</span>
          </div>
          <form onSubmit={send}>
            <div className="form-grid">
              <FormField label="Customer">
                <select
                  value={customer}
                  onChange={(e) => setCustomer(e.target.value)}
                >
                  <option value="playground">Playground customer</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.name}>
                      {c.display_name}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField label="Model alias">
                <select
                  value={alias}
                  onChange={(e) => setAlias(e.target.value)}
                >
                  {aliases.map((a) => (
                    <option key={a.id}>{a.name}</option>
                  ))}
                </select>
              </FormField>
            </div>
            <div className="form-grid">
              <FormField label="Feature tag">
                <input
                  value={feature}
                  onChange={(e) => setFeature(e.target.value)}
                  pattern="[a-zA-Z0-9_-]{1,64}"
                  required
                  placeholder="support"
                />
              </FormField>
              <FormField label="Environment">
                <select
                  value={environment}
                  onChange={(e) => setEnvironment(e.target.value)}
                >
                  <option>production</option>
                  <option>staging</option>
                  <option>development</option>
                </select>
              </FormField>
            </div>
            <FormField label="Your prompt">
              <textarea
                rows={9}
                value={prompt}
                onChange={(e) => {
                  setPrompt(e.target.value);
                  setPreview(null);
                }}
                required
                placeholder="Try a prompt containing an email or phone number…"
              />
            </FormField>
            <div className="playground-options">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={stream}
                  onChange={(e) => setStream(e.target.checked)}
                />{" "}
                Stream response
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={deterministic}
                  onChange={(e) => setDeterministic(e.target.checked)}
                />{" "}
                Enable exact cache (temperature 0)
              </label>
            </div>
            <div className="playground-actions">
              <Button onClick={previewPrompt}>
                <Eye size={16} /> Preview redaction
              </Button>
              {busy ? (
                <Button
                  variant="primary"
                  onClick={() => abort.current?.abort()}
                >
                  <X size={16} /> Stop
                </Button>
              ) : (
                <Button type="submit" variant="primary">
                  <Send size={15} /> Send request
                </Button>
              )}
            </div>
          </form>
          {preview && (
            <div className="redaction-preview">
              <div>
                <ShieldCheck size={16} />
                <strong>
                  {preview.blocked
                    ? `Blocked: ${preview.category}`
                    : "What the provider sees"}
                </strong>
                <span>
                  {Object.values(preview.counts).reduce((a, b) => a + b, 0)}{" "}
                  values protected
                </span>
              </div>
              <pre>
                {preview.redacted ||
                  "This request contains a blocked category."}
              </pre>
            </div>
          )}
        </section>
        <section className="panel playground-output">
          <div className="panel-heading">
            <h2>
              <Sparkles size={17} /> Response
            </h2>
            {output && <CopyButton text={output} />}
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          {!output && !busy ? (
            <div className="response-empty">
              <div>
                <Sparkles size={28} />
              </div>
              <h3>A safe journey from prompt to answer.</h3>
              <p>
                Send a request to see model routing, budget protection, and
                reversible redaction working together.
              </p>
              <span>
                YOUR APP <ArrowRight size={13} /> TOLLGATE{" "}
                <ArrowRight size={13} /> MODEL
              </span>
            </div>
          ) : (
            <>
              <div className="response-body" aria-live="polite">
                {output}
                {busy && <span className="typing-cursor" />}
              </div>
              {info && (
                <div className="response-meta">
                  <Badge tone="purple">Tier {info.tier}</Badge>
                  <code>{info.model}</code>
                  <span>
                    {info.cache === "HIT" ? "Cache hit" : "Fresh response"}
                  </span>
                </div>
              )}
            </>
          )}
        </section>
      </div>
      <div className="info-banner">
        <ShieldCheck size={18} />
        <span>
          <strong>Try it with sensitive data.</strong> Email addresses and phone
          numbers become placeholders on the way out, then return to their
          original values in the answer.
        </span>
      </div>
    </>
  );
}

function SettingsView({
  workspace,
  readOnly,
  tenant,
  plans,
  demo,
  save,
  notify,
}: {
  workspace: string;
  readOnly: boolean;
  tenant?: Tenant;
  plans: Plan[];
  demo: boolean;
  save: (p: string, m: string, v?: unknown) => Promise<unknown>;
  notify: (s: string) => void;
}) {
  const [display, setDisplay] = useState(tenant?.display_name || "");
  const [rpm, setRpm] = useState(String(tenant?.rpm || 1000));
  const [plan, setPlan] = useState(tenant?.default_plan || "Pro");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const code = `from openai import OpenAI\n\nclient = OpenAI(\n    base_url="http://localhost:8187/v1",\n    api_key="YOUR_TOLLGATE_API_KEY",\n)\n\nresponse = client.chat.completions.create(\n    model="smart",\n    messages=[{"role": "user", "content": "Hello!"}],\n    extra_headers={"X-Tollgate-Customer": "cus_acme"},\n    extra_body={"feature": "support", "environment": "production"},\n)\nprint(response.choices[0].message.content)`;
  return (
    <>
      <div className="settings-grid">
        <section className="panel settings-card">
          <div className="panel-heading">
            <div>
              <h2>Workspace settings</h2>
              <p>Defaults for new customers and requests</p>
            </div>
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await save(`/tenants/${tenant?.name}`, "PATCH", {
                  name: tenant?.name,
                  revision: tenant?.revision,
                  display_name: display,
                  rpm: Number(rpm),
                  default_plan: plan,
                });
                setError("");
                notify("Workspace updated");
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {error && <div className="error-banner">{error}</div>}
            <FormField label="Workspace name">
              <input
                value={display}
                onChange={(e) => setDisplay(e.target.value)}
                required
              />
            </FormField>
            <FormField label="Default customer plan">
              <select value={plan} onChange={(e) => setPlan(e.target.value)}>
                {plans.map((p) => (
                  <option key={p.id}>{p.name}</option>
                ))}
              </select>
            </FormField>
            <FormField label="Workspace requests per minute">
              <input
                type="number"
                min="1"
                max="1000000"
                value={rpm}
                onChange={(e) => setRpm(e.target.value)}
                required
              />
            </FormField>
            <Button type="submit" variant="primary" disabled={busy || readOnly}>
              {busy ? (
                <Loader2 size={15} className="spin" />
              ) : (
                <Check size={15} />
              )}{" "}
              Save settings
            </Button>
          </form>
          <div className="workspace-info">
            <Badge tone={demo ? "amber" : "green"}>
              {demo ? "Demo mode" : "Live workspace"}
            </Badge>
            <p>
              {demo
                ? "Sample activity is included to help you explore. All default aliases use the mock provider. No external model calls are made until you configure routing."
                : "Your runtime configuration is stored in the database."}
            </p>
          </div>
        </section>
        <section className="panel setup-card">
          <div className="panel-heading">
            <div>
              <h2>Connect in a few minutes</h2>
              <p>Your existing OpenAI SDK. One new base URL.</p>
            </div>
            <Code2 size={20} />
          </div>
          <ol className="setup-steps">
            <li>
              <span>1</span>
              <div>
                <strong>Create an API key</strong>
                <p>
                  Generate a workspace key from{" "}
                  <Link href="/keys">
                    API keys <ArrowUpRight size={12} />
                  </Link>
                  .
                </p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Point your SDK to Tollgate</strong>
                <p>Use your gateway URL and tag each customer.</p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Send a request and explore</strong>
                <p>
                  Usage, budgets, and protected data appear in your dashboard.
                </p>
              </div>
            </li>
          </ol>
          <div className="code-block">
            <div>
              <span>Python · OpenAI SDK</span>
              <CopyButton text={code} />
            </div>
            <pre>{code}</pre>
          </div>
          {demo && (
            <div className="demo-key-hint">
              <KeyRound size={15} />
              <span>
                Local demo key: <code>tg_live_demo_tollgate_local_only</code>
              </span>
              <CopyButton text="tg_live_demo_tollgate_local_only" />
            </div>
          )}
        </section>
      </div>
      <OperationsSettings key={workspace} workspace={workspace} />
    </>
  );
}

function Login({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [isDemo, setIsDemo] = useState(false);
  useEffect(() => {
    fetch("/api/healthz")
      .then((r) => r.json())
      .then((r) => setIsDemo(r.demo))
      .catch(() => {});
  }, []);
  return (
    <div className="login-page">
      <div className="login-art">
        <Logo />
        <div>
          <div className="login-orbit">
            <ShieldCheck size={60} />
            <span className="orbit-one" />
            <span className="orbit-two" />
          </div>
          <span className="eyebrow">
            A LITTLE CONTROL. A LOT OF POSSIBILITY.
          </span>
          <h1>
            Let your AI grow.
            <br />
            Keep your costs grounded.
          </h1>
          <p>
            One gateway to meter usage, protect customer data, and keep every AI
            feature running smoothly.
          </p>
          <div className="login-features">
            <span>
              <Check size={16} /> Customer-aware budgets
            </span>
            <span>
              <Check size={16} /> Reversible PII protection
            </span>
            <span>
              <Check size={16} /> Graceful model degradation
            </span>
          </div>
        </div>
        <small>Open source. Self hosted. Built around your customers.</small>
      </div>
      <div className="login-form-wrap">
        <div className="login-form">
          <span className="eyebrow">WELCOME TO YOUR CONTROL ROOM</span>
          <h2>Good to see you.</h2>
          <p>Sign in to your Tollgate workspace.</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setError("");
              setBusy(true);
              try {
                await api("/auth/login", {
                  method: "POST",
                  body: JSON.stringify({ email, password }),
                });
                onSuccess();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {error && (
              <div className="error-banner" role="alert">
                {error}
              </div>
            )}
            <FormField label="Email address">
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
              />
            </FormField>
            <FormField label="Password">
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Your workspace password"
              />
            </FormField>
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? (
                <Loader2 className="spin" size={16} />
              ) : (
                "Sign in to workspace"
              )}
              <ArrowRight size={16} />
            </Button>
          </form>
          {isDemo && (
            <div className="demo-login">
              <FlaskConical size={18} />
              <div>
                <strong>Just exploring?</strong>
                <p>This local demo has everything set up.</p>
                <button
                  onClick={() => {
                    setEmail("admin@tollgate.local");
                    setPassword("tollgate-demo-2026");
                  }}
                >
                  Use demo credentials <ArrowRight size={13} />
                </button>
              </div>
            </div>
          )}
          <div className="login-security">
            <ShieldCheck size={14} /> Your data stays in your infrastructure.
          </div>
        </div>
      </div>
    </div>
  );
}

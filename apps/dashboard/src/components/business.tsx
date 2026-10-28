"use client";
import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  Bell,
  Check,
  Copy,
  KeyRound,
  ShieldCheck,
  Users,
} from "lucide-react";
import Link from "next/link";
import { api, money, number, type Usage, type Customer } from "@/lib/api";

interface Alert {
  id: string;
  payload: {
    type: string;
    customer_id: string;
    spend: number;
    budget: number;
    created_at: string;
    tier?: number;
    threshold?: number;
  };
  delivery_status: string;
  attempts: number;
}
export function BusinessView({
  usage,
  customers,
  workspace,
}: {
  usage: Usage;
  customers: Customer[];
  workspace: string;
}) {
  const [alerts, setAlerts] = useState<Alert[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Alert[]>(`/tenants/${workspace}/alerts`)
      .then((r) => {
        if (active) setAlerts(r);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [workspace]);
  return (
    <>
      <div className="info-banner">
        <ShieldCheck size={18} />
        <span>
          Tag requests with a feature and environment to understand where AI
          costs come from. Costs marked estimated use configured rates, not
          reconciled provider invoices.
        </span>
      </div>
      <div className="stat-grid three">
        <div className="stat-card">
          <span>Active customers in this period</span>
          <strong className="stat-value">
            {number(usage.active_customers)}
          </strong>
          <small>Customers with successful requests</small>
        </div>
        <div className="stat-card">
          <span>Actually degraded requests</span>
          <strong className="stat-value">
            {number(usage.degraded_requests)}
          </strong>
          <small>Served below Tier 0; quality locks are respected</small>
        </div>
        <div className="stat-card">
          <span>Requests with estimated usage</span>
          <strong className="stat-value">
            {number(usage.estimated_requests)}
          </strong>
          <small>Review estimates before financial reporting</small>
        </div>
      </div>
      <div className="business-grid">
        {["feature", "environment", "model", "customer"].map((group) => (
          <section className="panel" key={group}>
            <div className="panel-heading">
              <h2>Cost by {group}</h2>
              <span>Selected reporting period</span>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{group.toUpperCase()}</th>
                    <th>REQUESTS</th>
                    <th>MODEL COST</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.breakdown?.[group]?.map((row) => (
                    <tr key={row.name}>
                      <td>
                        <code>{row.name}</code>
                      </td>
                      <td>{number(row.requests)}</td>
                      <td>{money(row.cost, 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!usage.breakdown?.[group]?.length && (
                <p className="panel-empty">No usage in this period yet.</p>
              )}
            </div>
          </section>
        ))}
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Monthly AI contribution</h2>
            <p>
              Optional customer revenue reference minus model cost. Other
              business costs are excluded.
            </p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>CUSTOMER</th>
                <th>MONTHLY REVENUE REFERENCE</th>
                <th>MODEL COST THIS UTC MONTH</th>
                <th>AI CONTRIBUTION</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => {
                const cost =
                  usage.monthly_customer_costs?.find((r) => r.name === c.name)
                    ?.cost || 0;
                return (
                  <tr key={c.id}>
                    <td>{c.display_name}</td>
                    <td>
                      {c.monthly_revenue == null
                        ? "Not provided"
                        : money(c.monthly_revenue)}
                    </td>
                    <td>{money(cost, 4)}</td>
                    <td>
                      {c.monthly_revenue == null
                        ? "Set a reference"
                        : money(c.monthly_revenue - cost)}
                    </td>
                    <td>
                      <Link
                        className="text-link"
                        href={`/customers/${c.id}?workspace=${workspace}`}
                      >
                        Edit customer <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>
            <Bell size={17} /> Budget and routing events
          </h2>
          <span>Deduplicated per customer and billing month</span>
        </div>
        {error && <p className="error-banner">{error}</p>}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>EVENT</th>
                <th>CUSTOMER</th>
                <th>SPEND / BUDGET</th>
                <th>DELIVERY</th>
                <th>TIME</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td>
                    <code>{a.payload.type}</code>
                    {a.payload.threshold != null && (
                      <small> · {Math.round(a.payload.threshold * 100)}%</small>
                    )}
                  </td>
                  <td>{a.payload.customer_id}</td>
                  <td>
                    {money(a.payload.spend)} / {money(a.payload.budget)}
                  </td>
                  <td>
                    {a.delivery_status} · {a.attempts} attempts
                  </td>
                  <td>{new Date(a.payload.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!alerts.length && (
            <p className="panel-empty">
              Events appear when actual usage crosses a budget threshold or a
              request is degraded.
            </p>
          )}
        </div>
      </section>
    </>
  );
}

interface Session {
  id: string;
  created_at: string;
  expires_at: number;
  current: boolean;
}
interface Audit {
  id: string;
  actor_id: string;
  method: string;
  resource: string;
  created_at: string;
}
export function OperationsSettings({ workspace }: { workspace: string }) {
  const [sessions, setSessions] = useState<Session[]>([]),
    [audit, setAudit] = useState<Audit[]>([]),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [url, setUrl] = useState(""),
    [enabled, setEnabled] = useState(false),
    [signingSecret, setSigningSecret] = useState("");
  const [currentPassword, setCurrentPassword] = useState(""),
    [newPassword, setNewPassword] = useState("");
  const [email, setEmail] = useState(""),
    [initialPassword, setInitialPassword] = useState(""),
    [role, setRole] = useState("viewer");
  const [owner, setOwner] = useState(false),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Session[]>("/auth/sessions"),
      api<Audit[]>(`/tenants/${workspace}/audit`),
      api<{ url: string; enabled: boolean }>(`/tenants/${workspace}/webhook`),
      api<{ role: string }>("/auth/me"),
    ])
      .then(([s, a, w, u]) => {
        if (active) {
          setSessions(s);
          setAudit(a);
          setUrl(w.url);
          setEnabled(w.enabled);
          setOwner(u.role === "owner");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [workspace]);
  const act = async (action: () => Promise<void>) => {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const changePassword = (e: FormEvent) => {
    e.preventDefault();
    act(async () => {
      await api("/auth/password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      window.location.assign(new URL("/login", window.location.origin).href);
    });
  };
  return (
    <div className="operations-settings">
      {error && (
        <div role="alert" className="error-banner">
          {error}
        </div>
      )}
      {message && (
        <div role="status" className="info-banner">
          <Check size={17} />
          {message}
        </div>
      )}
      <div className="business-grid">
        <section className="panel settings-card">
          <div className="panel-heading">
            <div>
              <h2>
                <KeyRound size={17} /> Change your password
              </h2>
              <p>
                Changing it revokes every existing session, including this one.
              </p>
            </div>
          </div>
          <form onSubmit={changePassword}>
            <label className="form-field">
              <span>Current password</span>
              <input
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </label>
            <label className="form-field">
              <span>New password (12+ characters)</span>
              <input
                type="password"
                minLength={12}
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </label>
            <button className="btn primary" disabled={busy}>
              Change password and sign out
            </button>
          </form>
        </section>
        <section className="panel settings-card">
          <div className="panel-heading">
            <div>
              <h2>
                <ShieldCheck size={17} /> Your sessions
              </h2>
              <p>Revoke a session you no longer recognize.</p>
            </div>
          </div>
          <div className="session-list">
            {sessions.map((s) => (
              <div key={s.id}>
                <span>
                  {s.current ? "This session" : "Other session"}
                  <small>
                    Expires {new Date(s.expires_at * 1000).toLocaleString()}
                  </small>
                </span>
                <button
                  className="btn"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api(`/auth/sessions/${s.id}`, { method: "DELETE" });
                      if (s.current)
                        window.location.assign(
                          new URL("/login", window.location.origin).href,
                        );
                      else setSessions(sessions.filter((r) => r.id !== s.id));
                    })
                  }
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        </section>
      </div>
      {owner && (
        <div className="business-grid">
          <section className="panel settings-card">
            <div className="panel-heading">
              <div>
                <h2>
                  <Bell size={17} /> Signed budget webhooks
                </h2>
                <p>
                  Disabled by default. Delivery is initiated only after you
                  enable a destination.
                </p>
              </div>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(async () => {
                  const result = await api<{ signing_secret?: string }>(
                    `/tenants/${workspace}/webhook`,
                    { method: "PUT", body: JSON.stringify({ url, enabled }) },
                  );
                  if (result.signing_secret)
                    setSigningSecret(result.signing_secret);
                  setMessage(
                    "Webhook settings saved. New events follow this delivery policy.",
                  );
                });
              }}
            >
              <label className="form-field">
                <span>Public HTTPS endpoint (port 443)</span>
                <input
                  type="url"
                  placeholder="https://your-app.example/hooks/tollgate"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                />
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                />{" "}
                Enable signed event delivery
              </label>
              <p className="form-hint">
                Verify the timestamp and HMAC-SHA256 signature, and deduplicate
                by event ID. Retries are visible in Insights.
              </p>
              <button className="btn primary" disabled={busy}>
                Save delivery settings
              </button>
              {signingSecret && (
                <div className="secret-key">
                  <span>
                    <strong>
                      Copy this signing secret now; it is shown once.
                    </strong>
                    <code>{signingSecret}</code>
                  </span>
                  <button
                    className="icon-btn"
                    type="button"
                    aria-label="Copy signing secret"
                    onClick={() => navigator.clipboard.writeText(signingSecret)}
                  >
                    <Copy size={16} />
                  </button>
                </div>
              )}
            </form>
          </section>
          <section className="panel settings-card">
            <div className="panel-heading">
              <div>
                <h2>
                  <Users size={17} /> Add an administrator account
                </h2>
                <p>
                  Accounts apply to this deployment and can access all
                  workspaces.
                </p>
              </div>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(async () => {
                  await api("/users", {
                    method: "POST",
                    body: JSON.stringify({
                      email,
                      password: initialPassword,
                      role,
                    }),
                  });
                  setInitialPassword("");
                  setEmail("");
                  setMessage(
                    "Account created. Share its initial password through your own secure channel.",
                  );
                });
              }}
            >
              <label className="form-field">
                <span>Account email</span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label className="form-field">
                <span>Initial password</span>
                <input
                  type="password"
                  required
                  minLength={12}
                  autoComplete="new-password"
                  value={initialPassword}
                  onChange={(e) => setInitialPassword(e.target.value)}
                />
              </label>
              <label className="form-field">
                <span>Role</span>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="viewer">Viewer — read only</option>
                  <option value="admin">
                    Admin — manage workspace configuration
                  </option>
                  <option value="owner">
                    Owner — manage accounts and delivery
                  </option>
                </select>
              </label>
              <button className="btn primary" disabled={busy}>
                Create account
              </button>
            </form>
          </section>
        </div>
      )}
      <section className="panel">
        <div className="panel-heading">
          <h2>Configuration audit history</h2>
          <span>Metadata only · no secrets or prompt content</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>ACTION</th>
                <th>RESOURCE</th>
                <th>ACTOR ID</th>
                <th>TIME</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id}>
                  <td>{a.method}</td>
                  <td>
                    <code>{a.resource}</code>
                  </td>
                  <td>
                    <code>{a.actor_id?.slice(0, 8)}</code>
                  </td>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!audit.length && (
            <p className="panel-empty">
              Configuration changes will appear here.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

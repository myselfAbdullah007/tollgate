"use client";
import { useState, useEffect, useRef, type FormEvent } from "react";
import {
  Check,
  KeyRound,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import {
  money,
  type Customer,
  type Plan,
  type Alias,
  type Key,
  type Provider,
  type Log,
} from "@/lib/api";
import { Badge, Button, CopyButton, FormField } from "./ui";
export type Modal = {
  type: string;
  value?: Customer | Plan | Alias | Key | Provider | Log;
};
const providersLabel: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google Gemini",
  mock: "Mock provider",
};
export function Editor({
  modal,
  close,
  plans,
  providers,
  base,
  tenant,
  save,
  notify,
}: {
  modal: Modal;
  close: () => void;
  plans: Plan[];
  providers: Provider[];
  base: string;
  tenant: string;
  save: (p: string, m: string, v?: unknown) => Promise<unknown>;
  notify: (s: string) => void;
}) {
  const row = modal.value;
  const rowId = row && "id" in row ? row.id : undefined;
  const customer =
    modal.type === "customer" ? (row as Customer | undefined) : undefined;
  const plan = modal.type === "plan" ? (row as Plan | undefined) : undefined;
  const alias = modal.type === "alias" ? (row as Alias | undefined) : undefined;
  const provider =
    modal.type === "provider" ? (row as Provider | undefined) : undefined;
  const log = modal.type === "log" ? (row as Log) : undefined;
  const [name, setName] = useState(
    (row && "name" in row ? row.name : "") || "",
  );
  const [displayName, setDisplayName] = useState(customer?.display_name || "");
  const [selectedPlan, setSelectedPlan] = useState(
    customer?.plan || plans[0]?.name || "Pro",
  );
  const [budget, setBudget] = useState(
    String(
      plan
        ? plan.monthly_budget / 1e6
        : customer?.budget_override != null
          ? customer.budget_override / 1e6
          : "",
    ),
  );
  const [revenue, setRevenue] = useState(
    customer?.monthly_revenue == null
      ? ""
      : String(customer.monthly_revenue / 1e6),
  );
  const [rpm, setRpm] = useState(String(plan?.rpm || 60));
  const [thresholds, setThresholds] = useState(
    plan?.degradation || [
      { at: 0.8, tier: 1 },
      { at: 0.95, tier: 2 },
    ],
  );
  const [piiMode, setPiiMode] = useState(plan?.pii_mode || "reversible");
  const [blockCategories, setBlockCategories] = useState(
    plan?.pii_block_categories || ["CARD"],
  );
  const [policy, setPolicy] = useState(plan?.on_exhausted || "block");
  const [overage, setOverage] = useState(
    String((plan?.overage_cap || 0) / 1e6),
  );
  const [allowDegrade, setAllowDegrade] = useState(
    alias?.allow_degrade ?? true,
  );
  const [tiers, setTiers] = useState(
    alias?.tiers || [
      ["mock/premium", "mock/backup"],
      ["mock/balanced"],
      ["mock/economy"],
    ],
  );
  const [keyScope, setKeyScope] = useState("gateway");
  const [keyCustomer, setKeyCustomer] = useState("");
  const [secret, setSecret] = useState("");
  const [createdKey, setCreatedKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    dialog.current
      ?.querySelector<HTMLElement>("input, button, select, textarea")
      ?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "Tab") {
        const elements = dialog.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), select, textarea, a[href]",
        );
        if (!elements?.length) return;
        const first = elements[0],
          last = elements[elements.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [close]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (modal.type === "customer")
        await save(
          `${base}/customers${row ? `/${rowId}` : ""}`,
          row ? "PATCH" : "POST",
          {
            name,
            revision: customer?.revision,
            monthly_revenue:
              revenue === "" ? null : Math.round(Number(revenue) * 1e6),
            display_name: displayName,
            plan: selectedPlan,
            budget_override:
              budget === "" ? null : Math.round(Number(budget) * 1e6),
          },
        );
      else if (modal.type === "plan") {
        if (
          thresholds.some(
            (step, i) =>
              i > 0 &&
              (step.at <= thresholds[i - 1].at ||
                step.tier <= thresholds[i - 1].tier),
          )
        )
          throw new Error("Threshold percentages and tiers must increase.");
        await save(
          `${base}/plans${row ? `/${rowId}` : ""}`,
          row ? "PATCH" : "POST",
          {
            name,
            monthly_budget: Math.round(Number(budget) * 1e6),
            rpm: Number(rpm),
            revision: plan?.revision,
            degradation: thresholds,
            pii_mode: piiMode,
            pii_block_categories: blockCategories,
            on_exhausted: policy,
            overage_cap: Math.round(Number(overage) * 1e6),
          },
        );
      } else if (modal.type === "alias")
        await save(
          `${base}/aliases${row ? `/${rowId}` : ""}`,
          row ? "PATCH" : "POST",
          {
            name,
            revision: alias?.revision,
            allow_degrade: allowDegrade,
            tiers,
          },
        );
      else if (modal.type === "key") {
        const result = (await save(`${base}/keys`, "POST", {
          name,
          scope: keyScope,
          customer: keyScope === "usage" ? keyCustomer : null,
        })) as Key;
        setCreatedKey(result.key || "");
        notify("API key created");
        return;
      } else if (modal.type === "revoke" && row)
        await save(`${base}/keys/${rowId}`, "DELETE");
      else if (modal.type === "provider" && provider)
        await save("/providers", "PUT", {
          provider: provider.name,
          key: secret,
          tenant_id: tenant,
        });
      else if (modal.type === "tenant")
        await save("/tenants", "POST", {
          name,
          display_name: displayName,
          rpm: 1000,
          default_plan: "Pro",
        });
      notify(modal.type === "revoke" ? "API key revoked" : "Changes saved");
      close();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const title =
    modal.type === "log"
      ? "Request details"
      : modal.type === "revoke"
        ? "Revoke API key?"
        : modal.type === "provider"
          ? `Connect ${providersLabel[provider?.name || ""]}`
          : modal.type === "tenant"
            ? "Create workspace"
            : createdKey
              ? "Your API key is ready"
              : `${row ? "Edit" : "Create"} ${modal.type === "alias" ? "model alias" : modal.type === "key" ? "API key" : modal.type}`;
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) close();
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        ref={dialog}
      >
        <div className="modal-heading">
          <div>
            <span className="eyebrow">WORKSPACE CONFIGURATION</span>
            <h2 id="modal-title">{title}</h2>
          </div>
          <button
            className="icon-btn"
            aria-label="Close dialog"
            onClick={close}
          >
            <X size={20} />
          </button>
        </div>
        {log ? (
          <div className="request-detail">
            <Badge tone={log.status === "success" ? "green" : "red"}>
              {log.http_status} · {log.status}
            </Badge>
            <div className="detail-id">
              <code>{log.id}</code>
              <CopyButton text={log.id} />
            </div>
            <dl>
              {[
                ["Customer", log.customer_id],
                ["Model alias", log.alias],
                ["Model served", log.model],
                ["Tier served", log.tier_served],
                ["Cost", money(log.cost, 6)],
                [
                  "Input / output tokens",
                  `${log.input_tokens} / ${log.output_tokens}`,
                ],
                [
                  "Usage measured",
                  log.tokens_estimated ? "Estimated" : "Provider reported",
                ],
                ["Latency", `${log.latency_ms} ms`],
                ["Cache", log.cache_hit ? "Hit" : "Miss"],
                ["Fallbacks", log.fallback_count],
                [
                  "PII detected",
                  Object.entries(log.pii_counts)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(", ") || "None",
                ],
                ["Time", new Date(log.created_at).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <div className="info-banner">
              <ShieldCheck size={18} />
              <span>
                Prompts, responses, and original sensitive values are never
                stored in request logs.
              </span>
            </div>
          </div>
        ) : createdKey ? (
          <div className="key-created">
            <div className="success-circle">
              <Check size={28} />
            </div>
            <p>Copy this key now. It won’t be shown again.</p>
            <div className="secret-key">
              <code>{createdKey}</code>
              <CopyButton text={createdKey} />
            </div>
            <Button variant="primary" onClick={close}>
              I’ve saved my key <Check size={16} />
            </Button>
          </div>
        ) : (
          <form onSubmit={submit}>
            {error && (
              <div className="error-banner" role="alert">
                {error}
              </div>
            )}
            {["customer", "plan", "alias", "key", "tenant"].includes(
              modal.type,
            ) && (
              <FormField
                label={
                  modal.type === "customer"
                    ? "Customer ID"
                    : modal.type === "tenant"
                      ? "Workspace slug"
                      : "Name"
                }
                hint={
                  row
                    ? "This identifier stays the same after creation."
                    : modal.type === "customer"
                      ? "Send this value in the X-Tollgate-Customer header."
                      : undefined
                }
              >
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={100}
                  readOnly={!!row}
                  placeholder={
                    modal.type === "customer"
                      ? "cus_example"
                      : modal.type === "alias"
                        ? "smart"
                        : "e.g. Production"
                  }
                />
              </FormField>
            )}
            {modal.type === "key" && (
              <>
                <FormField label="Key access">
                  <select
                    value={keyScope}
                    onChange={(e) => setKeyScope(e.target.value)}
                  >
                    <option value="gateway">
                      Gateway — send AI requests in this workspace
                    </option>
                    <option value="usage">
                      Customer usage — read only, one customer
                    </option>
                  </select>
                </FormField>
                {keyScope === "usage" && (
                  <FormField
                    label="Customer ID"
                    hint="This key cannot send model requests or read another customer's usage."
                  >
                    <input
                      required
                      value={keyCustomer}
                      onChange={(e) => setKeyCustomer(e.target.value)}
                      placeholder="cus_acme"
                    />
                  </FormField>
                )}
              </>
            )}
            {["customer", "tenant"].includes(modal.type) && (
              <FormField label="Display name">
                <input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  placeholder="Acme Inc."
                />
              </FormField>
            )}
            {modal.type === "customer" && (
              <>
                <FormField label="Plan">
                  <select
                    value={selectedPlan}
                    onChange={(e) => setSelectedPlan(e.target.value)}
                  >
                    {plans.map((p) => (
                      <option key={p.id}>{p.name}</option>
                    ))}
                  </select>
                </FormField>
                <FormField
                  label="Monthly revenue reference (USD)"
                  hint="Optional. Used for the AI contribution report; excludes other business costs."
                >
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={revenue}
                    onChange={(e) => setRevenue(e.target.value)}
                    placeholder="Not provided"
                  />
                </FormField>
                <FormField
                  label="Custom monthly budget (USD)"
                  hint="Leave empty to use the plan’s budget."
                >
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    placeholder="Use plan budget"
                  />
                </FormField>
              </>
            )}
            {modal.type === "plan" && (
              <>
                <div className="form-grid">
                  <FormField label="Monthly budget (USD)">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={budget}
                      onChange={(e) => setBudget(e.target.value)}
                      required
                    />
                  </FormField>
                  <FormField label="Requests per minute">
                    <input
                      type="number"
                      min="1"
                      max="100000"
                      value={rpm}
                      onChange={(e) => setRpm(e.target.value)}
                      required
                    />
                  </FormField>
                </div>
                <div className="form-section-label">
                  Step down to cheaper models
                </div>
                {thresholds.map((step, i) => (
                  <div className="threshold-row" key={i}>
                    <FormField label={`Step ${i + 1} at (% used)`}>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={Math.round(step.at * 10000) / 100}
                        onChange={(e) =>
                          setThresholds(
                            thresholds.map((s, j) =>
                              j === i
                                ? { ...s, at: Number(e.target.value) / 100 }
                                : s,
                            ),
                          )
                        }
                        required
                      />
                    </FormField>
                    <FormField label={`Step ${i + 1} tier`}>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        value={step.tier}
                        onChange={(e) =>
                          setThresholds(
                            thresholds.map((s, j) =>
                              j === i
                                ? { ...s, tier: Number(e.target.value) }
                                : s,
                            ),
                          )
                        }
                        required
                      />
                    </FormField>
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label={`Remove threshold ${i + 1}`}
                      onClick={() =>
                        setThresholds(thresholds.filter((_, j) => j !== i))
                      }
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
                <Button
                  onClick={() =>
                    setThresholds([
                      ...thresholds,
                      {
                        at: Math.min(1, (thresholds.at(-1)?.at || 0) + 0.01),
                        tier: (thresholds.at(-1)?.tier || 0) + 1,
                      },
                    ])
                  }
                >
                  <Plus size={14} /> Add threshold
                </Button>
                <FormField label="When the budget runs out">
                  <select
                    value={policy}
                    onChange={(e) => setPolicy(e.target.value)}
                  >
                    <option value="block">Pause requests (hard limit)</option>
                    <option value="allow_overage">Allow limited overage</option>
                  </select>
                </FormField>
                {policy === "allow_overage" && (
                  <FormField label="Maximum overage (USD)">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={overage}
                      onChange={(e) => setOverage(e.target.value)}
                      required
                    />
                  </FormField>
                )}
                <FormField label="Sensitive data protection">
                  <select
                    value={piiMode}
                    onChange={(e) => setPiiMode(e.target.value)}
                  >
                    <option value="reversible">
                      Reversible — restore values in the answer
                    </option>
                    <option value="mask">Mask — hide values permanently</option>
                    <option value="block">
                      Block — reject requests with sensitive data
                    </option>
                    <option value="off">
                      Off — send original values to providers
                    </option>
                  </select>
                </FormField>
                <fieldset className="category-options">
                  <legend>Always block these sensitive categories</legend>
                  {[
                    "CARD",
                    "EMAIL",
                    "PHONE",
                    "SECRET",
                    "CNIC",
                    "MYNUMBER",
                    "IBAN",
                    "IP",
                  ].map((category) => (
                    <label className="checkbox-label" key={category}>
                      <input
                        type="checkbox"
                        checked={blockCategories.includes(category)}
                        onChange={(e) =>
                          setBlockCategories(
                            e.target.checked
                              ? [...blockCategories, category]
                              : blockCategories.filter((c) => c !== category),
                          )
                        }
                      />
                      {category}
                    </label>
                  ))}
                </fieldset>
              </>
            )}
            {modal.type === "alias" && (
              <>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={allowDegrade}
                    onChange={(e) => setAllowDegrade(e.target.checked)}
                  />{" "}
                  Allow automatic degradation to lower tiers
                </label>
                <p className="form-hint">
                  Targets are tried left to right within each tier. Add a
                  fallback to keep requests working during an outage.
                </p>
                {tiers.map((tier, i) => (
                  <div className="tier-editor" key={i}>
                    <div>
                      <strong>Tier {i}</strong>
                      {i > 0 && (
                        <button
                          type="button"
                          className="icon-btn"
                          aria-label={`Remove tier ${i}`}
                          onClick={() =>
                            setTiers(tiers.filter((_, j) => j !== i))
                          }
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                    {tier.map((target, j) => (
                      <div className="target-editor" key={j}>
                        <select
                          aria-label={`Tier ${i} target ${j + 1}`}
                          value={target}
                          onChange={(e) =>
                            setTiers(
                              tiers.map((t, n) =>
                                n === i
                                  ? t.map((v, k) =>
                                      k === j ? e.target.value : v,
                                    )
                                  : t,
                              ),
                            )
                          }
                        >
                          {providers
                            .flatMap((p) => p.models)
                            .map((m) => (
                              <option key={m}>{m}</option>
                            ))}
                        </select>
                        {j > 0 && (
                          <button
                            type="button"
                            className="icon-btn"
                            aria-label={`Remove fallback ${j}`}
                            onClick={() =>
                              setTiers(
                                tiers.map((t, n) =>
                                  n === i ? t.filter((_, k) => k !== j) : t,
                                ),
                              )
                            }
                          >
                            <X size={15} />
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      className="text-button"
                      onClick={() =>
                        setTiers(
                          tiers.map((t, n) =>
                            n === i ? [...t, "mock/backup"] : t,
                          ),
                        )
                      }
                    >
                      <Plus size={13} /> Add fallback
                    </button>
                  </div>
                ))}
                <Button onClick={() => setTiers([...tiers, ["mock/economy"]])}>
                  <Plus size={14} /> Add tier
                </Button>
              </>
            )}
            {modal.type === "provider" && (
              <>
                <p className="form-hint">
                  Your credential is encrypted before storage. Saving a new key
                  replaces the previous one.
                </p>
                <FormField label="Provider API key">
                  <input
                    type="password"
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                    required
                    minLength={8}
                    autoComplete="off"
                    placeholder="Paste your provider API key"
                  />
                </FormField>
              </>
            )}
            {modal.type === "revoke" && (
              <div className="revoke-message">
                <span className="danger-icon">
                  <KeyRound size={26} />
                </span>
                <p>
                  Applications using{" "}
                  <strong>{row && "name" in row ? row.name : ""}</strong> will
                  lose access immediately.
                </p>
                <p>
                  Create and deploy a replacement key before revoking this one.
                </p>
              </div>
            )}
            <div className="modal-actions">
              <Button onClick={close}>Cancel</Button>
              <Button
                type="submit"
                variant={modal.type === "revoke" ? "danger" : "primary"}
                disabled={busy}
              >
                {busy ? (
                  <Loader2 className="spin" size={16} />
                ) : modal.type === "revoke" ? (
                  <Trash2 size={15} />
                ) : (
                  <Check size={15} />
                )}{" "}
                {modal.type === "revoke"
                  ? "Revoke key"
                  : modal.type === "key"
                    ? "Create API key"
                    : "Save changes"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

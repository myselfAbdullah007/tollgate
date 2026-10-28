"use client";
import { useState, type ReactNode } from "react";
import NextLink from "next/link";
import { useSearchParams } from "next/navigation";
import { Box, Check, Copy } from "lucide-react";
export function Link(props: React.ComponentProps<typeof NextLink>) {
  const params = useSearchParams();
  const workspace = params.get("workspace");
  let href = props.href;
  if (
    workspace &&
    typeof href === "string" &&
    href.startsWith("/") &&
    !href.startsWith("/api") &&
    href !== "/login"
  ) {
    const url = new URL(href, "http://tollgate.local");
    if (!url.searchParams.has("workspace"))
      url.searchParams.set("workspace", workspace);
    href = url.pathname + url.search;
  }
  return <NextLink {...props} href={href} />;
}

export function Logo({ small = false }: { small?: boolean }) {
  return (
    <div className={`logo ${small ? "small" : ""}`}>
      <div className="logo-mark">
        <span />
        <span />
        <span />
      </div>
      {!small && (
        <span>
          tollgate<span className="logo-dot">.</span>
        </span>
      )}
    </div>
  );
}
export function Badge({
  children,
  tone = "green",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <span className={`badge ${tone}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Box size={30} />
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Button({
  children,
  onClick,
  variant = "",
  disabled = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: string;
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      className={`btn ${variant}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="icon-btn"
      aria-label="Copy to clipboard"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }}
    >
      {copied ? <Check size={16} /> : <Copy size={16} />}
    </button>
  );
}
export function FormField({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="form-field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

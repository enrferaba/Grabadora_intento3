import { ReactNode, useMemo } from "react";

export type MessageTone = "info" | "success" | "warning" | "error";

interface MessageBannerProps {
  tone?: MessageTone;
  onClose?: () => void;
  children: ReactNode;
}

const toneStyles: Record<MessageTone, { background: string; border: string; color: string; icon: string }> = {
  info: {
    background: "rgba(56,189,248,0.15)",
    border: "rgba(56,189,248,0.35)",
    color: "#e0f2fe",
    icon: "ℹ️",
  },
  success: {
    background: "rgba(34,197,94,0.18)",
    border: "rgba(34,197,94,0.35)",
    color: "#dcfce7",
    icon: "✅",
  },
  warning: {
    background: "rgba(250,204,21,0.18)",
    border: "rgba(250,204,21,0.35)",
    color: "#fef08a",
    icon: "⚠️",
  },
  error: {
    background: "rgba(239,68,68,0.18)",
    border: "rgba(239,68,68,0.35)",
    color: "#fee2e2",
    icon: "⛔",
  },
};

export function MessageBanner({ tone = "info", onClose, children }: MessageBannerProps) {
  const style = useMemo(() => toneStyles[tone], [tone]);

  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "1rem",
        padding: "0.85rem 1.1rem",
        borderRadius: "16px",
        border: `1px solid ${style.border}`,
        background: style.background,
        color: style.color,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.65rem", lineHeight: 1.4 }}>
        <span aria-hidden="true" style={{ fontSize: "1.15rem" }}>
          {style.icon}
        </span>
        <div>{children}</div>
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          style={{
            background: "transparent",
            border: "1px solid transparent",
            color: style.color,
            cursor: "pointer",
            fontSize: "0.85rem",
            padding: "0.35rem 0.6rem",
            borderRadius: "12px",
          }}
          aria-label="Cerrar aviso"
        >
          ×
        </button>
      )}
    </div>
  );
}

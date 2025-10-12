import { forwardRef, useCallback, useImperativeHandle, useMemo, useRef, useState } from "react";

interface UploaderProps {
  onSelect: (file: File) => void;
  accept?: string;
  busy?: boolean;
}

export interface UploaderHandle {
  open: () => void;
}

export const Uploader = forwardRef<UploaderHandle, UploaderProps>(function Uploader(
  { onSelect, accept = "audio/*", busy = false }: UploaderProps,
  ref,
) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const borderColor = useMemo(() => (dragActive ? "#38bdf8" : "rgba(148,163,184,0.4)"), [dragActive]);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || !files.length) return;
      const [file] = Array.from(files);
      onSelect(file);
    },
    [onSelect],
  );

  useImperativeHandle(
    ref,
    () => ({
      open() {
        if (!busy) {
          inputRef.current?.click();
        }
      },
    }),
    [busy],
  );

  return (
    <label
      htmlFor="audio-uploader"
      style={{
        border: `2px dashed ${borderColor}`,
        borderRadius: "24px",
        padding: "2rem",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.75rem",
        background: "rgba(15, 23, 42, 0.65)",
        cursor: busy ? "not-allowed" : "pointer",
        opacity: busy ? 0.6 : 1,
        transition: "border-color 0.2s ease, opacity 0.2s ease",
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        setDragActive(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragActive(false);
        handleFiles(event.dataTransfer?.files ?? null);
      }}
    >
      <input
        ref={inputRef}
        id="audio-uploader"
        type="file"
        accept={accept}
        style={{ display: "none" }}
        disabled={busy}
        onChange={(event) => handleFiles(event.target.files)}
      />
      <div style={{ fontSize: "1.25rem", fontWeight: 600, color: "#e2e8f0" }}>
        Arrastra tu audio o haz clic para seleccionarlo
      </div>
      <p style={{ color: "#94a3b8", textAlign: "center", maxWidth: "360px" }}>
        MP3, WAV, AAC, hasta 200&nbsp;MB. También puedes grabar directamente desde la pestaña "Grabar".
      </p>
      <button
        className="primary"
        type="button"
        disabled={busy}
        onClick={(event) => {
          event.preventDefault();
          inputRef.current?.click();
        }}
      >
        Explorar archivos
      </button>
    </label>
  );
});

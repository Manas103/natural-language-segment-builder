import { useState } from "react";
import type { SegmentPreviewResponse } from "./types";

interface Props {
  preview: SegmentPreviewResponse | null;
  onConfirm: (preview: SegmentPreviewResponse) => void;
}

// The confirmation gate the pipeline design property refers to: a segment is
// schema-validated and previewed as a live count (preview.liveCount, computed
// server-side by segment_builder.store.ProfileStore.execute_segment against
// the synthetic profile store) before this button can fire. No profile row
// content is rendered here, only the count and the typed definition tree.
export function SegmentPreview({ preview, onConfirm }: Props) {
  const [confirmed, setConfirmed] = useState(false);

  if (!preview) {
    return <p data-testid="empty-state">Enter a plain-English request to preview a segment.</p>;
  }

  return (
    <div data-testid="segment-preview">
      <p>
        Request: <em>{preview.requestText}</em>
      </p>
      <pre data-testid="definition-json">{JSON.stringify(preview.definition, null, 2)}</pre>
      <p data-testid="live-count">Live count: {preview.liveCount}</p>
      <button
        data-testid="confirm-button"
        disabled={confirmed}
        onClick={() => {
          setConfirmed(true);
          onConfirm(preview);
        }}
      >
        {confirmed ? "Confirmed" : "Confirm segment"}
      </button>
    </div>
  );
}

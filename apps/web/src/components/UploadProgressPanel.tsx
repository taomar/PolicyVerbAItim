import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Tag, Tooltip, Typography } from "antd";
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  CloudUploadOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LoadingOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { api, type UploadProgress } from "../api";
import { formatFileSize } from "../uploadFeedback";
import "./extractionProgressPanel.css";

const { Text } = Typography;

/**
 * What the server is actually doing with a document being uploaded.
 *
 * The upload request does five things in one call and, until this existed,
 * reported none of them: the page showed a spinner and an elapsed clock for the
 * whole minute-plus a real policy document takes to read. A reviewer could not
 * tell a slow parse from a hung request, or know whether the wait was in the
 * parser or in the search index.
 *
 * TRUTHFUL, OR ABSENT — the rule this panel is built around
 * --------------------------------------------------------
 * Every figure shown here is one the server measured and published. There is
 * deliberately no percentage and no progress bar, because the request has no
 * denominator: the clause count is unknown until the document has been read, so
 * any bar would be interpolated from elapsed time — a guess wearing the clothes
 * of a measurement, and the number someone would use to decide whether to wait.
 *
 * What replaces it is a fixed, ordered pipeline, so "step 2 of 5" is exactly
 * true even while no stage has a count of its own, and motion on the active
 * stage that says work is happening without claiming how much is left. A count
 * appears only once the server has one; `null` renders as "—", never as 0,
 * because "not read yet" and "no clauses found" are different facts about a
 * document and must not look identical.
 */
interface Props {
  /** True while the upload request is open. */
  running: boolean;
  /** The id this page generated and sent with the POST. Progress is keyed on it
   *  because the client cannot learn any server-side id until the response
   *  arrives — which is after the work it wanted to watch has ended. */
  operationId: string | null;
  fileName: string;
  fileSizeBytes: number | null | undefined;
  /** Client-measured wall clock for the whole request, including the browser's
   *  own transfer of the body — a phase the server cannot see. */
  elapsedMs: number;
}

/** Poll interval. Upload stages turn over in seconds, not the tens of seconds an
 *  extraction batch takes, so this is faster than the extraction panel's. */
const POLL_MS = 1000;

/** How long a running upload may go without publishing before the panel stops
 *  presenting it as freshly active and says so — a policy, not a measurement.
 *
 *  The registry is written at stage boundaries, and the longest stage (reading)
 *  is a single uninterrupted parse of the whole document with no intermediate
 *  write. So a healthy upload of a long document legitimately sits still for
 *  minutes. A threshold in the tens of seconds would call working uploads
 *  stalled constantly — a worse and far more frequent error than the stuck
 *  request it is trying to catch. The copy states the fact ("no update for X")
 *  rather than a verdict, so a slow parse that does cross the line still reads
 *  true and clears itself the moment the next stage lands. */
const QUIET_AFTER_SECONDS = 120;

/** The only two statuses the server finishes with. Polling stops on these
 *  rather than on `active`, which stays true through the retention window. */
const TERMINAL_STATUSES = new Set(["completed", "failed"]);

/** Compact duration: "2m 05s", or "45s" under a minute. */
function duration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  if (whole < 60) return `${whole}s`;
  return `${Math.floor(whole / 60)}m ${String(whole % 60).padStart(2, "0")}s`;
}

/**
 * Animate a number towards its target instead of snapping to it.
 *
 * A counter that jumps from 0 to 412 reads as a glitch; the same change rolling
 * up reads as work being done. Deliberately short so the figure on screen is
 * never meaningfully behind the truth — decoration on a real number, not a
 * substitute for one. Motion is skipped entirely under `prefers-reduced-motion`,
 * where the value is set directly and the reading is identical.
 */
function useCountUp(target: number, ms = 400): number {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);

  useEffect(() => {
    const from = fromRef.current;
    if (from === target) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      fromRef.current = target;
      setValue(target);
      return;
    }
    const started = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - started) / ms);
      const eased = 1 - (1 - t) ** 3;
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) frame = requestAnimationFrame(step);
      else fromRef.current = target;
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, ms]);

  return value;
}

/** One stage's figure. Only a bare number is animated — "—" is a composite and
 *  would count up into nonsense. */
function StageValue({ text }: { text: string }) {
  const numeric = /^\d+$/.test(text) ? Number(text) : null;
  const shown = useCountUp(numeric ?? 0);
  return <span className="extract-stage-value">{numeric === null ? text : shown}</span>;
}

/** The pipeline, keyed by the server's own stage names so the two cannot drift.
 *  Each entry says what the stage does and what its figure counts; a stage with
 *  no count shows "—" rather than a fabricated one. */
const STAGE_VIEW: Record<
  string,
  { label: string; icon: ReactNode; hint: string }
> = {
  storing: {
    label: "stored",
    icon: <CloudUploadOutlined />,
    hint: "The uploaded file has arrived and is being written to storage as a new version. The original bytes are kept unchanged.",
  },
  reading: {
    label: "read",
    icon: <FileTextOutlined />,
    hint: "The whole document is being read and split into clauses. This is the longest step and runs in one pass, so it publishes nothing until it finishes — its length follows the length of the document.",
  },
  checking: {
    label: "checks",
    icon: <SafetyCertificateOutlined />,
    hint: "The extracted text is checked for ingestion problems — unreadable pages, coverage loss, interleaved text. Findings are reported; nothing is rewritten and nothing is withheld.",
  },
  saving: {
    label: "clauses",
    icon: <DatabaseOutlined />,
    hint: "The clauses are being written to the register in the same transaction as the version.",
  },
  indexing: {
    label: "indexed",
    icon: <SearchOutlined />,
    hint: "Clauses are being added to search so Ask-AI and rule extraction have grounding text. Best-effort: a failure here does not lose the document.",
  },
};

/** The figure each stage reports, or null where the server has no count for it.
 *  Absence is deliberate: inventing a figure for a stage that measures nothing
 *  is the same defect as inventing a percentage. */
function figureFor(stage: string, p: UploadProgress): number | null | undefined {
  if (stage === "reading" || stage === "saving") return p.clause_count;
  if (stage === "checking") return p.warning_count;
  if (stage === "indexing") return p.indexed_count;
  return undefined;
}

export default function UploadProgressPanel({
  running,
  operationId,
  fileName,
  fileSizeBytes,
  elapsedMs,
}: Props) {
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  // Two consecutive quiet readings before the panel says so, so a single slow
  // poll never flags a healthy upload.
  const [quietReadings, setQuietReadings] = useState(0);

  useEffect(() => {
    if (!operationId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const next = await api.uploadProgress(operationId);
        if (cancelled) return;
        setProgress(next);
        // Stop on a terminal status. `active` is not the signal: it stays true
        // through the server's retention window, so keying on it would poll a
        // finished upload for the whole of it.
        if (next.active && next.status && TERMINAL_STATUSES.has(next.status)) return;
      } catch {
        // A failed poll is not a failed upload, and must never be shown as one.
        // The panel keeps its last reading and the elapsed clock keeps running.
        if (cancelled) return;
      }
      timer = setTimeout(poll, POLL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [operationId]);

  // Reset between uploads so a new file never inherits the previous one's
  // counts for the moment before its first poll lands.
  useEffect(() => {
    if (running) {
      setProgress(null);
      setQuietReadings(0);
    }
  }, [running, operationId]);

  const live = progress?.active ? progress : null;
  const status = live?.status;
  const failed = status === "failed";
  const done = status === "completed";
  const stages = live?.stages ?? [];
  const stageIndex = live?.stage_index ?? 0;

  // Seconds since the upload last wrote anything, computed entirely from
  // server-stamped values so no client clock enters it. Using `Date.now()`
  // against a server timestamp would fold clock skew into the answer: a browser
  // running a few minutes ahead of the server would mark a perfectly healthy
  // upload quiet on its first poll, and a browser running behind would never
  // report a stalled one. Both readings would be wrong for a reason that has
  // nothing to do with the upload.
  //
  //   elapsed_seconds recomputes on each read as now − started_at;
  //   updated_at − started_at freezes at the last write.
  //
  // Their difference is the server-time gap between "now" and "last write", and
  // it is correct on the very first poll, before any cross-poll diff exists.
  // This mirrors `ExtractionProgressPanel`, which already gets this right.
  const secondsSinceUpdate =
    live?.started_at !== undefined &&
    live?.updated_at !== undefined &&
    live?.elapsed_seconds !== undefined
      ? Math.max(0, live.elapsed_seconds - (live.updated_at - live.started_at))
      : null;

  useEffect(() => {
    if (secondsSinceUpdate === null || done || failed) {
      setQuietReadings(0);
      return;
    }
    setQuietReadings((n) => (secondsSinceUpdate > QUIET_AFTER_SECONDS ? n + 1 : 0));
  }, [progress, secondsSinceUpdate, done, failed]);

  const goneQuiet = quietReadings >= 2 && !done && !failed;

  const size = formatFileSize(fileSizeBytes);
  const elapsed = Math.floor(elapsedMs / 1000);

  // Before the first poll lands, the only honest statement is that the file is
  // on its way: the browser is sending the body and the handler has not started.
  // Elapsed and size are measured; the fraction sent is NOT, because fetch does
  // not report upload progress for a body of this kind — so no share of the
  // transfer is claimed.
  const headline = live
    ? failed
      ? `Could not read ${fileName}`
      : done
        ? `Finished ${fileName}`
        : `Reading ${fileName}`
    : `Sending ${fileName}`;

  const counters = [
    size,
    elapsed > 0 ? `${duration(elapsed)} elapsed` : null,
    live && stageIndex > 0 ? `step ${stageIndex} of ${live.stage_total ?? stages.length}` : null,
  ].filter(Boolean);

  return (
    <div
      className={`extract-progress upload-progress${failed ? " extract-progress--failed" : ""}${
        goneQuiet ? " extract-progress--quiet" : ""
      }`}
    >
      {stages.length > 0 && (
        <div className="extract-pipeline" aria-label="Upload pipeline">
          {stages.map((name, i) => {
            const view = STAGE_VIEW[name];
            if (!view) return null;
            const position = i + 1;
            // A stage is done once the run has moved past it, and every stage is
            // done on completion. Nothing is drawn done while it is still the
            // live stage — that is the "says finished when it is not" defect.
            const isActive = !done && !failed && position === stageIndex;
            const isDone = done || position < stageIndex;
            const figure = live ? figureFor(name, live) : undefined;
            return (
              <div className="extract-pipeline-item" key={name}>
                <Tooltip title={view.hint}>
                  <div
                    className={`extract-stage${isActive ? " extract-stage--active" : ""}${
                      isDone ? " extract-stage--done" : ""
                    }`}
                  >
                    <span className="extract-stage-icon">
                      {isDone ? <CheckCircleFilled /> : view.icon}
                    </span>
                    {/* An em dash, not 0: this stage has no count, or has not
                        produced one yet. Rendering 0 would state a measurement
                        nobody took. */}
                    <StageValue
                      text={
                        figure === undefined || figure === null ? "—" : String(figure)
                      }
                    />
                    <span className="extract-stage-label">{view.label}</span>
                  </div>
                </Tooltip>
                {i < stages.length - 1 && (
                  <div
                    className={`extract-flow${isActive ? " extract-flow--moving" : ""}${
                      isDone ? " extract-flow--done" : ""
                    }`}
                    aria-hidden
                  >
                    <span className="extract-flow-dot" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* THE PANEL'S ONE LIVE REGION.
          A screen reader needs the state changes — which stage, gone quiet,
          finished, failed — and must not be read the things that change for
          decorative or continuous reasons. Two rules follow, and they are why
          one wrapper carries the announcement instead of scattering the
          attribute across every row:

            - nesting is not allowed. This panel sits inside the page's upload
              wait area; if both are live regions a change announces twice, or
              ambiguously. Exactly one owner, and it is this one.
            - the pipeline and the counters are deliberately OUTSIDE it. The
              stage figures animate frame by frame and the elapsed clock ticks
              every second, so including them would narrate every intermediate
              number of a count-up. Their content is reachable on demand; it is
              not news.

          The literal attribute is deliberately not repeated in this comment:
          everyLongRequestAnnouncesItself.test.tsx checks this file's source for
          it, and prose that mentions it would satisfy that guard without any
          element actually announcing anything. */}
      <div role="status" aria-live="polite">
        <div className={`extract-progress-line${goneQuiet ? " extract-progress-line--muted" : ""}`}>
          {done ? (
            <CheckCircleFilled style={{ color: "var(--success)" }} />
          ) : failed ? (
            <CloseCircleFilled style={{ color: "var(--danger)" }} />
          ) : goneQuiet ? (
            // Not a spinner: an upload that has gone quiet must not carry the same
            // "work in progress" motion as one that is publishing.
            <ClockCircleOutlined className="extract-quiet-icon" />
          ) : (
            <LoadingOutlined spin />
          )}
          <Text strong>{headline}</Text>
          {live?.has_interleaved_warning && (
            <Tooltip title="Some text in the original file has two languages interleaved character by character. It is reported for you to fix in the source file and upload a new version. Loading, extraction and indexing carry on unchanged — nothing is skipped or rewritten.">
              <Tag color="gold">interleaved text found in the source file</Tag>
            </Tooltip>
          )}
        </div>

        {goneQuiet && secondsSinceUpdate !== null && (
          <div className="extract-progress-line extract-quiet extract-quiet--raised">
            <ClockCircleOutlined className="extract-quiet-icon" aria-hidden />
            <Text className="extract-quiet-text">
              No update for <strong>{duration(secondsSinceUpdate)}</strong> &mdash; the figures below are
              the last this upload reported. A document is read in a single pass, so a gap like this can
              be a long parse rather than a stopped upload.
            </Text>
          </div>
        )}

        {failed && live?.error && (
          <div className="extract-progress-line">
            <Text type="danger">
              The file is stored and kept, but reading it did not complete: {live.error}
            </Text>
          </div>
        )}
      </div>

      <div
        className={`extract-progress-line extract-progress-counters${
          goneQuiet ? " extract-progress-line--muted" : ""
        }`}
      >
        <Text type="secondary">{counters.join(" · ")}</Text>
      </div>
    </div>
  );
}

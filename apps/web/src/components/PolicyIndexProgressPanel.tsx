import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Tag, Tooltip, Typography } from "antd";
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  CloudUploadOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  LoadingOutlined,
  PauseCircleOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  TranslationOutlined,
} from "@ant-design/icons";
import { api, type PolicyIndexBuildProgress } from "../api";
import "./extractionProgressPanel.css";

const { Text } = Typography;

/**
 * What the server is actually doing while it rebuilds a project's policy index.
 *
 * ONE PANEL, TWO SURFACES, BECAUSE IT IS ONE OPERATION
 *
 * An administrator watching a repair from the index console and a publisher
 * watching the best-effort build that follows their own publish are watching the
 * same server-side operation, with the same stages and the same counts. So this
 * is one component used by both, reading one endpoint, in the visual language
 * `UploadProgressPanel` and `ExtractionProgressPanel` already established. Two
 * panels would have been two vocabularies for one thing, and they would have
 * drifted the first time a stage was added.
 *
 * TRUTHFUL, OR ABSENT — the rule this panel is built around
 * --------------------------------------------------------
 * Every figure here is one the server measured and published. There is
 * deliberately no percentage and no progress bar: the stages before rendering
 * have no denominator at all, because how many documents a build will write is
 * unknown until the whole corpus has been rendered. A bar spanning them would be
 * interpolated from elapsed time — a guess wearing the clothes of a measurement,
 * and the number somebody would use to decide whether to wait.
 *
 * What replaces it is a fixed, ordered pipeline, so "step 4 of 8" is exactly
 * true even while a stage has no count of its own; motion on the active stage
 * that says work is happening without claiming how much is left; and, once
 * rendering has finished, the one real denominator the build does have —
 * documents acknowledged against documents expected.
 *
 * A count appears only once the server has one. `null` renders as "—", never as
 * 0, because "not measured yet" and "none found" are different facts about a
 * project and must not look identical.
 *
 * IT RESTORES ITSELF FROM THE SERVER
 * ----------------------------------
 * The record is a database row, not a process-local dict, so a page that
 * navigates away and comes back reads the same build back — running or finished
 * — by polling the operation id. Nothing here treats component state or browser
 * storage as an authority on what a build did.
 */
interface Props {
  /** The id this build is watched on. Null before one exists, which renders
   *  nothing at all rather than an empty frame. */
  operationId: string | null;
  /** A progress record the caller already holds — from a history read, or from
   *  the response to the request that started the build. Used as the first
   *  reading so the panel is never blank for a poll interval, and replaced by
   *  the server's answer as soon as one arrives. */
  initial?: PolicyIndexBuildProgress | null;
  /** Called once the build reaches a terminal status, so a parent can refresh
   *  the recorded index state it shows beside this. */
  onSettled?: (progress: PolicyIndexBuildProgress) => void;
}

/** Poll interval. Index stages turn over in seconds to tens of seconds — slower
 *  than an upload's, faster than an extraction batch's. */
const POLL_MS = 1500;

/** How long a running build may go without publishing before the panel stops
 *  presenting it as freshly active and says so — a policy, not a measurement.
 *
 *  The row is written at stage boundaries, and the longest stage is a single
 *  rendering pass over a whole corpus through a rate-limited model endpoint. On
 *  a large project that legitimately sits still for minutes. A threshold in the
 *  tens of seconds would call working builds stalled constantly, which is a
 *  worse and far more frequent error than the stuck build it is trying to catch.
 *  The copy states the fact ("no update for X") rather than a verdict, so a slow
 *  render that does cross the line still reads true and clears itself the moment
 *  the next stage lands. */
const QUIET_AFTER_SECONDS = 180;

/** The statuses the server finishes with. Polling stops on these rather than on
 *  `active`, which stays true for as long as the row exists. */
const TERMINAL_STATUSES = new Set(["completed", "failed", "deferred"]);

/** Compact duration: "2m 05s", or "45s" under a minute. */
export function buildDuration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  if (whole < 60) return `${whole}s`;
  return `${Math.floor(whole / 60)}m ${String(whole % 60).padStart(2, "0")}s`;
}

/**
 * Animate a number towards its target instead of snapping to it.
 *
 * A counter that jumps from 0 to 412 reads as a glitch; the same change rolling
 * up reads as work being done. Deliberately short so the figure on screen is
 * never meaningfully behind the truth. Motion is skipped entirely under
 * `prefers-reduced-motion`, where the value is set directly and the reading is
 * identical — the number is the content, the movement is decoration on it.
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
const STAGE_VIEW: Record<string, { label: string; icon: ReactNode; hint: string }> = {
  collecting: {
    label: "policies",
    icon: <FileTextOutlined />,
    hint: "The project's published policies are being read out of the register. Only the active approved version is indexed, so this is what the corpus will be built from.",
  },
  rendering: {
    label: "rendered",
    icon: <TranslationOutlined />,
    hint: "Each policy's retrieval text — and each rule's, for a policy holding more rules than one case can read — is being rendered into the language the pipeline matches in. This is the longest step: one model call per policy, so it grows with the corpus rather than with its size in bytes. The rendering is never served as policy content.",
  },
  embedding: {
    label: "embedded",
    icon: <ExperimentOutlined />,
    hint: "The renderings are being embedded. Everything is rendered and embedded before anything touches the index, so a failure here leaves the previous index exactly as it was.",
  },
  indexing: {
    label: "index",
    icon: <DatabaseOutlined />,
    hint: "The index is created if it does not exist and its manifest is moved out of ready. From here the project is not matchable, which is exactly true: it is being rewritten.",
  },
  uploading: {
    label: "accepted",
    icon: <CloudUploadOutlined />,
    hint: "Documents are being written and every acknowledgement counted. The count is documents that actually landed, not documents sent: a partly-rejected batch comes back as a 207 the transport does not raise.",
  },
  sweeping: {
    label: "swept",
    icon: <DeleteOutlined />,
    hint: "Documents this build did not recognise are being removed — superseded versions, and rules of a policy that has shrunk. The manifest is never swept: it is the record of what just happened.",
  },
  validating: {
    label: "checked",
    icon: <SafetyCertificateOutlined />,
    hint: "The corpus is checked against the record it was rendered from. A call that returned and an upload that was acknowledged are facts about transport; this is the separate question of whether what landed is a rendering of what it names.",
  },
  publishing: {
    label: "ready",
    icon: <SearchOutlined />,
    hint: "The manifest is moved to ready. This is the only write that changes what a query may do, and it happens only when every expected document was acknowledged and the corpus passed validation.",
  },
};

/** The figure each stage reports, or undefined where the server has no count for
 *  it. Absence is deliberate: inventing a figure for a stage that measures
 *  nothing is the same defect as inventing a percentage. */
export function figureForStage(
  stage: string,
  progress: PolicyIndexBuildProgress,
): number | null | undefined {
  if (stage === "collecting") return progress.projection_count;
  if (stage === "rendering") return progress.rendered_count;
  if (stage === "embedding") return progress.embedded_count;
  if (stage === "uploading") return progress.acknowledged_count;
  if (stage === "sweeping") return progress.swept_count;
  if (stage === "validating") return progress.quality_checked_documents;
  if (stage === "publishing") return progress.document_count;
  return undefined;
}

/** The headline, from the status and the trigger.
 *
 *  `deferred` gets its own sentence rather than borrowing the failure one,
 *  because the repair is different: wait for the running build to finish and
 *  retry, rather than investigate a build that broke. */
export function buildHeadline(progress: PolicyIndexBuildProgress): string {
  const started = progress.trigger === "publish" ? "after publishing" : "requested";
  switch (progress.status) {
    case "completed":
      return `Policy index rebuilt (${started})`;
    case "failed":
      return `Policy index build did not finish (${started})`;
    case "deferred":
      return "Policy index build has not started yet";
    default:
      return `Rebuilding the policy index (${started})`;
  }
}

export default function PolicyIndexProgressPanel({ operationId, initial, onSettled }: Props) {
  const [progress, setProgress] = useState<PolicyIndexBuildProgress | null>(initial ?? null);
  // Two consecutive quiet readings before the panel says so, so a single slow
  // poll never flags a healthy build.
  const [quietReadings, setQuietReadings] = useState(0);
  const settledRef = useRef<string | null>(null);

  useEffect(() => {
    setProgress(initial ?? null);
    setQuietReadings(0);
    settledRef.current = null;
  }, [operationId, initial]);

  useEffect(() => {
    if (!operationId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const next = await api.policyIndexBuildProgress(operationId);
        if (cancelled) return;
        setProgress(next);
        if (next.active && next.status && TERMINAL_STATUSES.has(next.status)) {
          // Announced once per operation. A terminal record stays readable for
          // as long as the row exists, so keying this on the status alone would
          // refresh the parent on every mount for the rest of the session.
          if (settledRef.current !== operationId) {
            settledRef.current = operationId;
            onSettled?.(next);
          }
          return;
        }
      } catch {
        // A failed poll is not a failed build, and must never be shown as one.
        // The panel keeps its last reading and carries on.
        if (cancelled) return;
      }
      timer = setTimeout(poll, POLL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // `onSettled` is deliberately not a dependency: a parent that redefines it
    // each render would restart the poll on every render, and the ref above
    // already makes the call idempotent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operationId]);

  const live = progress?.active ? progress : null;
  const secondsSinceUpdate = live?.seconds_since_update ?? null;
  const status = live?.status;
  const failed = status === "failed";
  const deferred = status === "deferred";
  const done = status === "completed";
  const settled = done || failed || deferred;

  useEffect(() => {
    if (secondsSinceUpdate === null || settled) {
      setQuietReadings(0);
      return;
    }
    setQuietReadings((n) => (secondsSinceUpdate > QUIET_AFTER_SECONDS ? n + 1 : 0));
  }, [progress, secondsSinceUpdate, settled]);

  const goneQuiet = quietReadings >= 2 && !settled;

  const stages = live?.stages ?? [];
  const stageIndex = live?.stage_index ?? 0;

  const counters = useMemo(() => {
    if (!live) return [];
    const parts: string[] = [];
    if (typeof live.elapsed_seconds === "number" && live.elapsed_seconds > 0) {
      parts.push(`${buildDuration(live.elapsed_seconds)} elapsed`);
    }
    if (stageIndex > 0) {
      parts.push(`step ${stageIndex} of ${live.stage_total ?? stages.length}`);
    }
    // The one honest denominator, and only once the build has it. Before
    // rendering finishes nobody knows how many documents there will be, so this
    // line is absent rather than showing a total of zero.
    if (typeof live.expected_document_count === "number") {
      parts.push(
        `${live.acknowledged_count ?? 0} of ${live.expected_document_count} documents accepted`,
      );
    }
    if (live.trigger) parts.push(live.trigger === "publish" ? "started by publish" : "manual rebuild");
    return parts;
  }, [live, stageIndex, stages.length]);

  if (!operationId || !live) return null;

  return (
    <div
      className={`extract-progress policy-index-progress${
        failed ? " extract-progress--failed" : ""
      }${goneQuiet || deferred ? " extract-progress--quiet" : ""}`}
      data-testid="policy-index-progress"
    >
      {stages.length > 0 && !deferred && (
        <div className="extract-pipeline" aria-label="Policy index build pipeline">
          {stages.map((name, i) => {
            const view = STAGE_VIEW[name];
            if (!view) return null;
            const position = i + 1;
            // A stage is done once the run has moved past it, and every stage is
            // done on completion. Nothing is drawn done while it is still the
            // live stage — that is the "says finished when it is not" defect.
            const isActive = !settled && position === stageIndex;
            const isDone = done || position < stageIndex;
            const figure = figureForStage(name, live);
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
                      text={figure === undefined || figure === null ? "—" : String(figure)}
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
          finished, failed, deferred — and must not be read the things that
          change for decorative or continuous reasons. Two rules follow, and they
          are why one wrapper carries the announcement rather than the attribute
          being scattered across every row:

            - nesting is not allowed. This panel sits inside pages that have
              their own wait areas; if both are live regions a change announces
              twice, or ambiguously. Exactly one owner, and it is this one.
            - the pipeline and the counters are deliberately OUTSIDE it. The
              stage figures animate frame by frame and the elapsed clock ticks,
              so including them would narrate every intermediate number of a
              count-up. Their content is reachable on demand; it is not news.

          The literal attribute is deliberately not repeated in this comment:
          everyLongRequestAnnouncesItself.test.tsx checks this file's source for
          it, and prose that mentioned it would satisfy that guard without any
          element actually announcing anything. */}
      <div role="status" aria-live="polite">
        <div className={`extract-progress-line${goneQuiet ? " extract-progress-line--muted" : ""}`}>
          {done ? (
            <CheckCircleFilled style={{ color: "var(--success)" }} />
          ) : failed ? (
            <CloseCircleFilled style={{ color: "var(--danger)" }} />
          ) : deferred ? (
            // Not a failure icon and not a spinner: nothing is wrong and nothing
            // is happening.
            <PauseCircleOutlined />
          ) : goneQuiet ? (
            // Not a spinner: a build that has gone quiet must not carry the same
            // "work in progress" motion as one that is publishing.
            <ClockCircleOutlined className="extract-quiet-icon" />
          ) : (
            <LoadingOutlined spin />
          )}
          <Text strong>{buildHeadline(live)}</Text>
          {live.policy_set_key && <Tag>{live.policy_set_key}</Tag>}
        </div>

        {deferred && (
          <div className="extract-progress-line">
            <Text type="secondary">
              Another policy index build is running, and only one runs at a time across this
              deployment. Nothing about this project changed and nothing is broken — the build has
              not happened yet. Retry once the running build finishes.
            </Text>
          </div>
        )}

        {goneQuiet && secondsSinceUpdate !== null && (
          <div className="extract-progress-line extract-quiet extract-quiet--raised">
            <ClockCircleOutlined className="extract-quiet-icon" aria-hidden />
            <Text className="extract-quiet-text">
              No update for <strong>{buildDuration(secondsSinceUpdate)}</strong> &mdash; the figures
              below are the last this build reported. A corpus is rendered one policy at a time
              through a rate-limited model, so a gap like this can be a long render rather than a
              stopped build.
            </Text>
          </div>
        )}

        {failed && live.error && (
          <div className="extract-progress-line">
            <Text type="danger">
              The published policies are unchanged and nothing was deleted; the index did not
              finish: {live.error}
            </Text>
          </div>
        )}

        {done && live.manifest_state && live.manifest_state !== "ready" && (
          <div className="extract-progress-line">
            <Text type="warning">
              The manifest is {live.manifest_state}, so project-wide case testing will refuse rather
              than answer from part of the corpus.
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

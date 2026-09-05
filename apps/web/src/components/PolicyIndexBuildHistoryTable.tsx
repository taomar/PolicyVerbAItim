import { Empty, Table, Tag, Tooltip, Typography } from "antd";
import type { PolicyIndexBuildProgress } from "../api";

const { Text } = Typography;

/**
 * A project's index build attempts, newest first.
 *
 * WHY A HISTORY IS A SEPARATE THING FROM A STATE
 *
 * The project Overview already shows the *recorded state* of the index: one row
 * per project, overwritten by every attempt. It answers "can this index be
 * matched against right now", which is the right question for a badge and the
 * wrong one for somebody deciding whether to press rebuild again. A publisher
 * whose build failed an hour ago, was retried, and failed again sees one row
 * saying "failed" — indistinguishable from a first failure, and useless.
 *
 * This reads the append-only record instead. Every attempt is here, with what
 * started it, who asked, how it ended and what it counted, so a pattern is
 * visible as a pattern.
 *
 * The same component serves the administrator's console and the publisher's
 * project view, because a history entry means the same thing to both.
 *
 * WHAT IS NOT HERE
 *
 * No policy text, no rendered text, no service reply. Counts, stage keys,
 * timestamps, an actor and a bounded failure description — which is all the
 * server will send, and all this renders.
 */

/** What a history status means to a reader, in one word plus a colour.
 *
 *  `deferred` is deliberately not folded into `failed`. The build never ran, so
 *  nothing about the project changed and nothing is broken; the repair is to
 *  retry once the running build finishes. Showing it in red would send somebody
 *  looking for a fault that does not exist. */
export const BUILD_STATUS_VIEW: Record<
  string,
  { label: string; color: string; hint: string }
> = {
  running: {
    label: "Running",
    color: "processing",
    hint: "This build is in progress and holds the single global build slot.",
  },
  completed: {
    label: "Built",
    color: "success",
    hint: "Every expected document was acknowledged, the corpus passed validation, and the manifest reached ready.",
  },
  failed: {
    label: "Failed",
    color: "error",
    hint: "The build did not finish. Nothing was deleted — the previous corpus is still in the index and the manifest keeps queries off it until a rebuild succeeds.",
  },
  deferred: {
    label: "Not started",
    color: "default",
    hint: "Another build was already running, and only one runs at a time across this deployment. Nothing about this project changed; retry once the running build finishes.",
  },
};

/** A timestamp as something a person reads, or an em dash when there is none. */
export function buildMoment(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString();
}

/** What this attempt counted, in a phrase — or an em dash when it counted
 *  nothing, which is a real state for a build that failed before it rendered.
 *
 *  Deliberately never "0 documents" for a build that never got as far as
 *  counting: zero is a measurement and absence is not. */
export function buildCounts(build: PolicyIndexBuildProgress): string {
  const parts: string[] = [];
  if (typeof build.document_count === "number") {
    const policy = build.policy_document_count;
    const rule = build.rule_document_count;
    parts.push(
      typeof policy === "number" && typeof rule === "number"
        ? `${build.document_count} documents (${policy} policy, ${rule} rule)`
        : `${build.document_count} documents`,
    );
  }
  if (typeof build.expected_document_count === "number" && build.status === "running") {
    parts.push(`${build.acknowledged_count ?? 0} of ${build.expected_document_count} accepted`);
  }
  if (typeof build.version_number === "number") parts.push(`v${build.version_number}`);
  return parts.length ? parts.join(" · ") : "—";
}

/** The quality verdict as a phrase, or an em dash when none was reached.
 *
 *  Null is not a pass and is not a failure: it means the build never got far
 *  enough to ask. Those are three different facts and the readiness gate treats
 *  the middle one exactly as it treats the last. */
export function buildQuality(build: PolicyIndexBuildProgress): string {
  if (!build.quality_state) return "—";
  const scored =
    typeof build.quality_checked_documents === "number"
      ? `, ${build.quality_checked_documents} scored`
      : "";
  const findings =
    typeof build.quality_structural_findings === "number" && build.quality_structural_findings > 0
      ? `, ${build.quality_structural_findings} structural`
      : "";
  return `${build.quality_state}${build.quality_profile ? ` (${build.quality_profile})` : ""}${scored}${findings}`;
}

interface Props {
  builds: PolicyIndexBuildProgress[];
  /** Rendered when there are none. Phrased by the caller because "no builds yet"
   *  means something different on a project page than in an estate console. */
  emptyText: string;
}

export default function PolicyIndexBuildHistoryTable({ builds, emptyText }: Props) {
  if (builds.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} />;
  }

  return (
    <Table
      size="small"
      rowKey={(build) => build.operation_id ?? String(build.started_at)}
      pagination={false}
      dataSource={builds}
      data-testid="policy-index-build-history"
      columns={[
        {
          title: "When",
          dataIndex: "started_at",
          render: (_value, build) => (
            <Text type="secondary">{buildMoment(build.started_at)}</Text>
          ),
        },
        {
          title: "Started by",
          dataIndex: "trigger",
          render: (_value, build) => (
            <>
              <Tag>{build.trigger === "publish" ? "Publish" : "Rebuild"}</Tag>
              {/* Only a publish carries an approver today; a manual rebuild does
                  not, and an em dash says so rather than inventing "unknown". */}
              <Text type="secondary">{build.actor || "—"}</Text>
            </>
          ),
        },
        {
          title: "Outcome",
          dataIndex: "status",
          render: (_value, build) => {
            const view = BUILD_STATUS_VIEW[build.status ?? ""] ?? {
              label: build.status ?? "—",
              color: "default",
              hint: "This build reported a status this page does not recognise.",
            };
            return (
              <Tooltip title={view.hint}>
                <Tag color={view.color}>{view.label}</Tag>
              </Tooltip>
            );
          },
        },
        {
          title: "Counts",
          render: (_value, build) => <Text type="secondary">{buildCounts(build)}</Text>,
        },
        {
          title: "Contract / manifest",
          render: (_value, build) => (
            <Text type="secondary">
              {build.projection_profile ?? "—"} / {build.manifest_state ?? "—"}
            </Text>
          ),
        },
        {
          title: "Validation",
          render: (_value, build) => <Text type="secondary">{buildQuality(build)}</Text>,
        },
        {
          title: "Reason",
          render: (_value, build) =>
            build.error ? (
              // The server bounds this before it is written and puts no source
              // text, no service reply and no credential in it.
              <Text type={build.status === "deferred" ? "secondary" : "danger"}>{build.error}</Text>
            ) : (
              <Text type="secondary">—</Text>
            ),
        },
      ]}
    />
  );
}

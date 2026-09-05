import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Space, Table, Tag, Tooltip, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import {
  api,
  PolicyPlatformApiError,
  type PolicyIndexBuildProgress,
  type PolicyIndexConsole,
  type PolicyIndexConsoleRow,
} from "./api";
import PolicyIndexProgressPanel from "./components/PolicyIndexProgressPanel";
import PolicyIndexBuildHistoryTable from "./components/PolicyIndexBuildHistoryTable";
import { newOperationId } from "./operationId";

const { Text, Title, Paragraph } = Typography;

/**
 * Every project's policy index, in one place, with the repair beside each one.
 *
 * WHY THIS SCREEN EXISTS
 *
 * The index state was only ever visible one project at a time, on that
 * project's Overview tab. So the question an operator actually has — "is
 * anything in this deployment unmatchable right now, and since when" — could
 * only be answered by opening every project in turn and remembering the
 * answers. A project whose index quietly failed four publishes ago was
 * indistinguishable from one nobody had looked at.
 *
 * WHY THE HEALTH WORDS ARE NOT COLLAPSED
 *
 * It is tempting to reduce this to green and red. Three of the seven states
 * would then be wrong in a way that costs somebody an afternoon:
 *
 *   - `unvalidated` is refused by retrieval exactly as a broken index is, but
 *     the repair is one validation run rather than a full re-render of every
 *     policy through a model. Painting it red sends an operator to do the
 *     expensive thing.
 *   - `empty` is a project with nothing published. Nothing is wrong. A warning
 *     on it trains people to ignore warnings.
 *   - `building` is about to be replaced by another reading, and an operator
 *     who does not know that will start a second build — which this deployment
 *     refuses, because only one runs at a time.
 *
 * ADMINISTRATORS ONLY, AND THE SERVER AGREES
 *
 * The nav entry is filtered by role and this page is only rendered for an
 * administrator, but neither is the authority: `GET /api/policy-index/states`
 * is ADMINISTER-band and answers 403 to anybody else, whatever the interface
 * offers.
 */

const HEALTH_VIEW: Record<
  PolicyIndexConsoleRow["health"],
  { label: string; color: string; hint: string }
> = {
  healthy: {
    label: "Healthy",
    color: "success",
    hint: "Built for the active published version, under the rendering contract this server expects, and its faithfulness check passed.",
  },
  unvalidated: {
    label: "Unvalidated",
    color: "warning",
    hint: "Built and current, but the corpus has never been checked against the record it was rendered from. Retrieval refuses it. The repair is a validation run, which re-renders nothing — not a rebuild.",
  },
  stale: {
    label: "Stale",
    color: "warning",
    hint: "Built for a superseded version, or under a superseded rendering contract. A question rendered under the current contract is not comparable with the text it would be scored against. A rebuild repairs both.",
  },
  failed: {
    label: "Failed",
    color: "error",
    hint: "The last build attempt did not finish. Nothing was deleted; the previous corpus is still there and the manifest keeps queries off it.",
  },
  building: {
    label: "Building",
    color: "processing",
    hint: "A build is running for this project right now. Every reading below is about to be replaced.",
  },
  not_built: {
    label: "Never built",
    color: "warning",
    hint: "No index build has ever been recorded for this project, and it has published policies that need one.",
  },
  empty: {
    label: "Nothing to index",
    color: "default",
    hint: "This project has no active published version, so there is correctly nothing to index. Not a fault.",
  },
};

/** Which health states a rebuild is the repair for.
 *
 *  `unvalidated` is excluded on purpose — a validation fixes it and re-renders
 *  nothing, so offering a rebuild would be offering the expensive repair for a
 *  cheap fault. `empty` is excluded because there is no work to do, and offering
 *  one would imply a fault that is not there. `building` is excluded because the
 *  slot is taken. Everything else is rebuildable, **including `failed`**: a
 *  broken index that could not be repaired from the one screen built to find it
 *  would be a dead end. */
export function consoleRowIsRebuildable(row: PolicyIndexConsoleRow): boolean {
  return row.health === "failed" || row.health === "stale" || row.health === "not_built";
}

export default function PolicyIndexConsolePage() {
  const [report, setReport] = useState<PolicyIndexConsole | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState<string | null>(null);
  const [watching, setWatching] = useState<PolicyIndexBuildProgress | null>(null);
  const [notice, setNotice] = useState<{ type: "error" | "info"; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await api.listPolicyIndexStates();
      setReport(next);
      setError(null);
      // THE SERVER IS THE AUTHORITY ON WHAT IS RUNNING.
      //
      // A build started before this page was opened — by a publish, by another
      // operator, on another replica — is recovered here rather than being
      // invisible because this component was not mounted when it began. Nothing
      // in this page treats its own state or browser storage as the record.
      setWatching(next.active.active ? next.active : null);
    } catch (e) {
      setError(e instanceof PolicyPlatformApiError ? e.detail : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = report?.active.active ? report.active : null;
  const anyBuildRunning = Boolean(active) || Boolean(watching && !watching.terminal);

  const handleRebuild = async (row: PolicyIndexConsoleRow) => {
    const operationId = newOperationId();
    setRebuilding(row.policy_set_key);
    setNotice(null);
    // Watched from the moment the request is made, not from the moment it
    // returns: the response does not exist until the build has finished, which
    // is the whole reason the id is generated here.
    setWatching({ active: true, operation_id: operationId, status: "running" });
    try {
      await api.rebuildPolicyIndex(row.policy_set_key, operationId);
      await load();
    } catch (e) {
      if (e instanceof PolicyPlatformApiError && e.status === 409) {
        setNotice({
          type: "info",
          text: "Another policy index build is already running, so this one did not start. Only one runs at a time across this deployment, because a build re-renders a whole corpus and rewrites an entire search index. Try again once the running build finishes.",
        });
        await load();
      } else {
        setWatching(null);
        setNotice({
          type: "error",
          text: e instanceof PolicyPlatformApiError ? e.detail : String(e),
        });
      }
    } finally {
      setRebuilding(null);
    }
  };

  const unhealthy = useMemo(
    () => (report?.projects ?? []).filter((row) => row.health !== "healthy" && row.health !== "empty"),
    [report],
  );

  const history = useMemo(
    () =>
      (report?.projects ?? [])
        .map((row) => row.latest_build)
        .filter((build): build is PolicyIndexBuildProgress => build.active)
        .sort((a, b) => String(b.started_at ?? "").localeCompare(String(a.started_at ?? ""))),
    [report],
  );

  return (
    <div className="page">
      <Title level={3}>Policy index console</Title>
      <Paragraph type="secondary">
        Every project's grounding index, as this server last recorded it. Read from the database
        only — nothing here probes the search service, so the page loads when the search service is
        the thing that is down. Live retrieval performs its own separate check when a case is
        actually run.
      </Paragraph>

      {error && (
        <Alert
          type="error"
          showIcon
          message="Could not read the recorded index states"
          description={error}
          style={{ marginBottom: 16 }}
        />
      )}

      {notice && (
        <Alert
          type={notice.type}
          showIcon
          message={notice.type === "error" ? "Rebuild could not be started" : "Rebuild did not start"}
          description={notice.text}
          style={{ marginBottom: 16 }}
        />
      )}

      {watching?.operation_id && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <PolicyIndexProgressPanel
            operationId={watching.operation_id}
            initial={watching}
            onSettled={() => void load()}
          />
        </Card>
      )}

      <Card
        size="small"
        title={
          <Space>
            <span>Projects</span>
            {unhealthy.length > 0 && (
              <Tag color="warning">{unhealthy.length} needing attention</Tag>
            )}
          </Space>
        }
        extra={
          <Button size="small" icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
            Refresh
          </Button>
        }
      >
        <Table
          size="small"
          rowKey="policy_set_key"
          loading={loading}
          pagination={false}
          dataSource={report?.projects ?? []}
          data-testid="policy-index-console-table"
          columns={[
            {
              title: "Project",
              dataIndex: "policy_set_name",
              render: (_v, row) => (
                <Space direction="vertical" size={0}>
                  <Text strong>{row.policy_set_name}</Text>
                  <Text type="secondary">{row.policy_set_key}</Text>
                  <Text type="secondary">{row.index_name}</Text>
                </Space>
              ),
            },
            {
              title: "Health",
              dataIndex: "health",
              render: (_v, row) => {
                const view = HEALTH_VIEW[row.health];
                return (
                  <Tooltip title={view.hint}>
                    <Tag color={view.color}>{view.label}</Tag>
                  </Tooltip>
                );
              },
            },
            {
              title: "Versions",
              render: (_v, row) => (
                <Text type="secondary">
                  active v{row.active_version_number ?? "—"} · indexed v
                  {row.indexed_version_number ?? "—"} · attempted v
                  {row.attempted_version_number ?? "—"}
                </Text>
              ),
            },
            {
              title: "Documents",
              dataIndex: "document_count",
              render: (_v, row) => <Text type="secondary">{row.document_count}</Text>,
            },
            {
              title: "Built / attempted",
              render: (_v, row) => (
                <Space direction="vertical" size={0}>
                  <Text type="secondary">
                    {row.built_at ? new Date(row.built_at).toLocaleString() : "—"}
                  </Text>
                  <Text type="secondary">
                    {row.attempted_at ? new Date(row.attempted_at).toLocaleString() : "—"}
                  </Text>
                </Space>
              ),
            },
            {
              title: "Validation",
              render: (_v, row) => (
                <Space direction="vertical" size={0}>
                  {/* Absent is not a pass and not a failure: it means the corpus
                      was never checked, and retrieval refuses on that exactly as
                      it refuses on a failure. */}
                  <Text type="secondary">{row.quality_state ?? "never checked"}</Text>
                  <Text type="secondary">
                    {row.quality_checked_documents ?? "—"} scored ·{" "}
                    {row.quality_structural_findings ?? "—"} structural
                  </Text>
                  <Text type="secondary">
                    min {row.quality_min_similarity ?? "—"} · mean{" "}
                    {row.quality_mean_similarity ?? "—"}
                  </Text>
                </Space>
              ),
            },
            {
              title: "Last reason",
              render: (_v, row) =>
                row.error ? (
                  <Text type="danger">{row.error}</Text>
                ) : (
                  <Text type="secondary">—</Text>
                ),
            },
            {
              title: "",
              render: (_v, row) => {
                const rebuildable = consoleRowIsRebuildable(row);
                if (!rebuildable) return null;
                const blocked = anyBuildRunning;
                return (
                  <Tooltip
                    title={
                      blocked
                        ? "Another policy index build is running. Only one runs at a time across this deployment, because a build re-renders a whole corpus and rewrites an entire search index."
                        : "Re-render and re-index every published policy in this project from the register."
                    }
                  >
                    {/* A disabled button inside a tooltip needs the wrapper to
                        receive the pointer events, or the explanation for the
                        disabling is unreachable — which is worse than no
                        tooltip, because the control looks broken. */}
                    <span>
                      <Button
                        size="small"
                        disabled={blocked}
                        loading={rebuilding === row.policy_set_key}
                        onClick={() => void handleRebuild(row)}
                      >
                        Rebuild
                      </Button>
                    </span>
                  </Tooltip>
                );
              },
            },
          ]}
        />
      </Card>

      <Card size="small" title="Most recent build per project" style={{ marginTop: 16 }}>
        <PolicyIndexBuildHistoryTable
          builds={history}
          emptyText="No index build has been recorded on this server yet."
        />
      </Card>
    </div>
  );
}

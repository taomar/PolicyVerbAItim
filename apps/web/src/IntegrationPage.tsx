/**
 * Integration — the subscription keys another system uses to call the decision API.
 *
 * WHY THERE IS NO "SHOW KEY" BUTTON
 *
 * The server stores a SHA-256 hash and nothing else, so after the response to
 * `generate` the plaintext exists only wherever the operator put it. That is
 * the security property, and it dictates the shape of this screen: a key is
 * displayed once, at generation, in a panel that says plainly it will not be
 * shown again. A lost key is replaced, not recovered.
 *
 * WHY REVOKED KEYS STAY IN THE TABLE
 *
 * "When did this stop working?" is the question an administrator asks after an
 * integration fails. A row that disappeared on revocation answers it with
 * silence.
 *
 * WHY GENERATING DOES NOT WARN ABOUT BREAKING ANYTHING
 *
 * It cannot break anything. Issuing a key never invalidates another, including
 * the configured environment key — several are valid at once by design, which
 * is what makes rotation a migration (issue, move the caller, revoke) rather
 * than a cutover.
 */
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Flex,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { ApiOutlined, CopyOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";

import { integrationApi, type SubscriptionKey } from "./api";

const { Text, Paragraph } = Typography;

function formatMoment(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString();
}

export default function IntegrationPage() {
  const [keys, setKeys] = useState<SubscriptionKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [generating, setGenerating] = useState(false);
  // Held only long enough to render the reveal panel. Never persisted, never
  // written to storage, and cleared when the panel closes.
  const [revealed, setRevealed] = useState<{ label: string; key: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await integrationApi.list();
      setKeys(result.keys);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load subscription keys.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleGenerate = async () => {
    const trimmed = label.trim();
    if (!trimmed) {
      void message.warning("Give the key a name so you can tell it apart later.");
      return;
    }
    setGenerating(true);
    try {
      const created = await integrationApi.generate(trimmed);
      setRevealed({ label: created.label, key: created.key });
      setLabel("");
      await load();
    } catch (err) {
      void message.error(
        err instanceof Error ? err.message : "Could not generate a subscription key.",
      );
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (record: SubscriptionKey) => {
    try {
      await integrationApi.revoke(record.id);
      void message.success(`"${record.label}" can no longer be used.`);
      await load();
    } catch (err) {
      void message.error(err instanceof Error ? err.message : "Could not revoke that key.");
    }
  };

  const copyRevealed = async () => {
    if (!revealed) return;
    try {
      await navigator.clipboard.writeText(revealed.key);
      void message.success("Key copied.");
    } catch {
      void message.warning("Could not copy automatically — select the key and copy it manually.");
    }
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "label",
      key: "label",
      render: (value: string) => <Text strong>{value}</Text>,
    },
    {
      title: "Status",
      key: "status",
      render: (_: unknown, record: SubscriptionKey) =>
        record.active ? (
          <Tag color="green">Active</Tag>
        ) : (
          <Tag color="default">Revoked {formatMoment(record.revoked_at)}</Tag>
        ),
    },
    { title: "Created", key: "created", render: (_: unknown, r: SubscriptionKey) => formatMoment(r.created_at) },
    { title: "By", dataIndex: "created_by", key: "created_by" },
    {
      title: "Last used",
      key: "last_used",
      render: (_: unknown, r: SubscriptionKey) =>
        r.last_used_at ? formatMoment(r.last_used_at) : <Text type="secondary">Never</Text>,
    },
    {
      title: "",
      key: "actions",
      render: (_: unknown, record: SubscriptionKey) =>
        record.active ? (
          <Popconfirm
            title="Revoke this key?"
            description="Any system still using it will stop being able to call the API."
            okText="Revoke"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleRevoke(record)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Revoke
            </Button>
          </Popconfirm>
        ) : null,
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card>
        <Flex align="flex-start" gap={12}>
          <ApiOutlined style={{ fontSize: 20, marginTop: 4 }} />
          <div>
            <Text strong style={{ fontSize: 16 }}>
              API subscription keys
            </Text>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              A caller sends one of these in the <Text code>X-Policy-Subscription-Key</Text> header
              to call the decision API. More than one can be active at a time, so you can issue a
              replacement, move the caller across, and revoke the old key without any downtime.
            </Paragraph>
          </div>
        </Flex>
      </Card>

      <Card title="Generate a key">
        <Space.Compact style={{ width: "100%", maxWidth: 560 }}>
          <Input
            placeholder="What will use this key? e.g. Expenses bot"
            value={label}
            maxLength={200}
            onChange={(event) => setLabel(event.target.value)}
            onPressEnter={() => void handleGenerate()}
            disabled={generating}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            loading={generating}
            onClick={() => void handleGenerate()}
          >
            Generate
          </Button>
        </Space.Compact>
        <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
          The key is shown once and stored only as a hash. If it is lost, generate another and
          revoke this one.
        </Paragraph>
      </Card>

      {error && <Alert type="error" showIcon message={error} />}

      <Card title="Keys">
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={keys}
          columns={columns}
          pagination={false}
          locale={{
            emptyText: <Empty description="No keys yet. Generate one to let a system call the API." />,
          }}
        />
      </Card>

      <Modal
        open={revealed !== null}
        title="Copy this key now"
        onCancel={() => setRevealed(null)}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} onClick={() => void copyRevealed()}>
            Copy
          </Button>,
          <Button key="done" type="primary" onClick={() => setRevealed(null)}>
            Done
          </Button>,
        ]}
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="This is the only time this key will be shown."
          description="It is stored as a hash, so it cannot be displayed again. If you lose it, generate a replacement and revoke this one."
        />
        <Text type="secondary">{revealed?.label}</Text>
        <Paragraph
          copyable={{ text: revealed?.key ?? "" }}
          code
          style={{ marginTop: 8, wordBreak: "break-all" }}
        >
          {revealed?.key}
        </Paragraph>
      </Modal>
    </Space>
  );
}

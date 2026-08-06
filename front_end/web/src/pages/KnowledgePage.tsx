import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Divider,
  Empty,
  Input,
  List,
  message,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  FileExcelOutlined,
  FileOutlined,
  FilePdfOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FolderOutlined,
} from "@ant-design/icons";
import { api, ApiBizError } from "../api/client";
import type { ResourceFile, ResourceTree, SearchData } from "../api/types";

function extIcon(ext: string) {
  switch (ext) {
    case "pdf":
      return <FilePdfOutlined style={{ color: "#e64545" }} />;
    case "doc":
    case "docx":
      return <FileWordOutlined style={{ color: "#2b579a" }} />;
    case "xls":
    case "xlsx":
      return <FileExcelOutlined style={{ color: "#217346" }} />;
    case "ppt":
    case "pptx":
      return <FilePptOutlined style={{ color: "#d24726" }} />;
    case "txt":
    case "md":
      return <FileTextOutlined style={{ color: "#5b6270" }} />;
    default:
      return <FileOutlined style={{ color: "#5b6270" }} />;
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function ResourceFiles() {
  const [tree, setTree] = useState<ResourceTree | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setTree(await api.resourceFiles());
    } catch (error) {
      const msg = error instanceof ApiBizError ? error.message : "加载资料文件失败";
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const total =
    (tree?.files.length ?? 0) +
    (tree?.directories.reduce((sum, d) => sum + d.files.length, 0) ?? 0);

  const renderFile = (file: ResourceFile) => (
    <List.Item
      key={file.path}
      style={{ cursor: "pointer", padding: "6px 0" }}
      onClick={() => window.open(api.resourceFileUrl(file.path), "_blank")}
    >
      <List.Item.Meta
        avatar={extIcon(file.ext)}
        title={
          <span style={{ color: "#1d2939", wordBreak: "break-all" }}>
            {file.name}
          </span>
        }
        description={formatSize(file.size)}
      />
    </List.Item>
  );

  if (!tree) {
    return loading ? <Empty description="加载中..." /> : <Empty description="暂无资料文件" />;
  }

  return (
    <>
      {tree.directories.map((dir) => (
        <div key={dir.path} style={{ marginBottom: 8 }}>
          <Typography.Text strong>
            <FolderOutlined style={{ marginRight: 6 }} />
            {dir.name}
          </Typography.Text>
          <List size="small" dataSource={dir.files} renderItem={renderFile} />
        </div>
      ))}
      {tree.files.length > 0 && (
        <>
          {tree.directories.length > 0 && <Divider style={{ margin: "12px 0" }} />}
          <List size="small" dataSource={tree.files} renderItem={renderFile} />
        </>
      )}
      {total === 0 && <Empty description="暂无资料文件" />}
    </>
  );
}

export default function KnowledgePage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchData | null>(null);

  const search = async () => {
    const q = query.trim();
    if (!q) {
      message.warning("请输入搜索关键词");
      return;
    }
    setLoading(true);
    try {
      setResult(await api.knowledgeSearch(q));
    } catch (error) {
      if (error instanceof ApiBizError && error.code === "KNOWLEDGE_NOT_FOUND") {
        setResult({ query: q, results: [], sources: [] });
      } else {
        const msg = error instanceof ApiBizError ? error.message : "搜索失败";
        message.error(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="知识库（办事流程 / 规章制度）">
      <Space direction="vertical" style={{ width: "100%" }}>
        <Typography.Text type="secondary">
          检索制度、办事流程、培养方案等知识，点击下方文件可直接查看或下载原始资料。
        </Typography.Text>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={search}
            placeholder="如：缓考申请、补办学生证"
          />
          <Button type="primary" loading={loading} onClick={search}>
            搜索
          </Button>
        </Space.Compact>
        {result && result.results.length === 0 && (
          <Typography.Text type="secondary">
            未找到相关内容，换个关键词试试。
          </Typography.Text>
        )}
        <List
          itemLayout="vertical"
          dataSource={result?.results ?? []}
          renderItem={(item) => (
            <List.Item
              key={item.title + item.source}
              extra={item.score !== undefined && <Tag>相关度 {item.score.toFixed(1)}</Tag>}
            >
              <List.Item.Meta
                title={item.title}
                description={`来源：${item.source}`}
              />
              <Typography.Paragraph
                style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}
              >
                {item.text}
              </Typography.Paragraph>
            </List.Item>
          )}
        />
        <Divider>资料文件</Divider>
        <ResourceFiles />
      </Space>
    </Card>
  );
}

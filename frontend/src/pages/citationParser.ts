import type { CitationInfo } from "../api/types";

export type CitationSegment =
  | { kind: "markdown"; text: string }
  | { kind: "citation"; citation: CitationInfo; fallback: string };

const COMPLETE_CITATION =
  /<citation\s+ref\s*=\s*(["'])([^"'<>]+)\1\s*>([\s\S]*?)<\/citation\s*>/gi;

/** 去掉无法解析的 citation 标记，保留其中对用户有意义的文字。 */
export function stripCitationMarkup(text: string): string {
  return text.replace(/<\/?citation\b[^>\r\n]*>?/gi, "");
}

/**
 * 将 AI 文本拆成 Markdown 与可信引用片段。只有后端 citations 中存在的 ref
 * 才会产生卡片；未知引用及畸形标签均降级为普通文字。
 */
export function parseCitationSegments(
  text: string,
  citations: CitationInfo[],
): CitationSegment[] {
  const byRef = new Map(citations.map((citation) => [citation.ref, citation]));
  const segments: CitationSegment[] = [];
  let cursor = 0;

  COMPLETE_CITATION.lastIndex = 0;
  for (const match of text.matchAll(COMPLETE_CITATION)) {
    const index = match.index ?? 0;
    const before = stripCitationMarkup(text.slice(cursor, index));
    if (before) segments.push({ kind: "markdown", text: before });

    const citation = byRef.get(match[2]);
    const fallback = stripCitationMarkup(match[3]).trim();
    if (citation) {
      segments.push({ kind: "citation", citation, fallback });
    } else if (fallback) {
      segments.push({ kind: "markdown", text: fallback });
    }
    cursor = index + match[0].length;
  }

  const remainder = stripCitationMarkup(text.slice(cursor));
  if (remainder) segments.push({ kind: "markdown", text: remainder });
  return segments;
}

export function hasResolvedCitation(text: string, citations: CitationInfo[]): boolean {
  return parseCitationSegments(text, citations).some((segment) => segment.kind === "citation");
}

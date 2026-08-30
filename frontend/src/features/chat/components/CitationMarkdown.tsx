import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { CitationInfo } from "../../../api/types";
import { parseCitationSegments } from "../utils/citationParser";
import { MapCitationCard } from "./MapCitationCard";

export function CitationMarkdown({
  text,
  citations,
}: {
  text: string;
  citations: CitationInfo[];
}) {
  const segments = parseCitationSegments(text, citations);
  return (
    <>
      {segments.map((segment, index) =>
        segment.kind === "citation" ? (
          <MapCitationCard key={`${segment.citation.ref}-${index}`} citation={segment.citation} />
        ) : (
          <ReactMarkdown key={`markdown-${index}`} remarkPlugins={[remarkGfm]}>
            {segment.text}
          </ReactMarkdown>
        ),
      )}
    </>
  );
}

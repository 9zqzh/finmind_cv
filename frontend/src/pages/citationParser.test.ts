import { describe, expect, it } from "vitest";
import type { CitationInfo } from "../api/types";
import {
  hasResolvedCitation,
  parseCitationSegments,
  stripCitationMarkup,
} from "./citationParser";

const citations: CitationInfo[] = [
  {
    ref: "c1",
    type: "map_place",
    title: "清远烧鹅饭店",
    url: "https://uri.amap.com/navigation?to=113.06,23.69",
    data: { rating: 4.5 },
  },
  {
    ref: "c2",
    type: "map_route",
    title: "学校 → 万达广场",
    url: "https://uri.amap.com/navigation?to=113.03,23.03",
    data: { mode: "walking" },
  },
];

describe("citation parsing", () => {
  it("keeps Markdown around multiple resolved citations", () => {
    const segments = parseCitationSegments(
      "**推荐**\n<citation ref=\"c1\">参考来源：烧鹅</citation>\n然后步行：<citation ref='c2'>参考来源：路线</citation>",
      citations,
    );

    expect(segments.filter((item) => item.kind === "citation")).toHaveLength(2);
    expect(segments[0]).toEqual({ kind: "markdown", text: "**推荐**\n" });
    expect(hasResolvedCitation("<citation ref=\"c1\">地点</citation>", citations)).toBe(true);
  });

  it("downgrades an unknown ref to its readable fallback", () => {
    expect(
      parseCitationSegments(
        "前文<citation ref=\"missing\">参考来源：未知地点</citation>后文",
        citations,
      ),
    ).toEqual([
      { kind: "markdown", text: "前文" },
      { kind: "markdown", text: "参考来源：未知地点" },
      { kind: "markdown", text: "后文" },
    ]);
  });

  it("strips malformed or attribute-injected markup but keeps body text", () => {
    expect(
      stripCitationMarkup(
        '<citation ref="c1" url="javascript:alert(1)">不可点击</citation>，<citation ref="c1">未闭合',
      ),
    ).toBe("不可点击，未闭合");
    expect(hasResolvedCitation('<citation ref="fake">伪造</citation>', citations)).toBe(false);
  });
});

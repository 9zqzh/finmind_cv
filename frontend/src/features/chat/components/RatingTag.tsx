import { Tag } from "antd";

/** 按评分高低着色 */
export function ratingTag(rating: number) {
  if (!rating) return <Tag>暂无评分</Tag>;
  const color =
    rating >= 4.5
      ? "green"
      : rating >= 4.0
        ? "blue"
        : rating >= 3.5
          ? "orange"
          : "default";
  return <Tag color={color}>⭐ {rating.toFixed(1)}</Tag>;
}

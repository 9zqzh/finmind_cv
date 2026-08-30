import { Card, Space, Tag, Typography } from "antd";
import { EnvironmentOutlined } from "@ant-design/icons";
import type { CitationInfo, MapPlace, MapRoute } from "../../../api/types";
import { MODE_LABELS } from "../constants";
import { formatDistance } from "../utils/format";
import { trustedAmapUrl } from "../utils/url";
import { PlaceCover } from "./PlaceCover";
import { ratingTag } from "./RatingTag";

export function MapCitationCard({ citation }: { citation: CitationInfo }) {
  const isPlace = citation.type === "map_place";
  const place = citation.data as unknown as MapPlace;
  const route = citation.data as unknown as MapRoute;
  const url = trustedAmapUrl(citation.url);
  const content = (
    <Card
      className={`map-citation-card${isPlace ? " map-citation-card--place" : ""}`}
      size="small"
      bordered
    >
      {isPlace && <PlaceCover imageUrl={place.image_url} name={citation.title} />}
      <div className="map-citation-card__content">
        <div className="map-citation-card__header">
          <EnvironmentOutlined className="map-citation-card__pin" />
          <Typography.Text strong className="map-citation-card__title">
            {citation.title}
          </Typography.Text>
          <span className="map-citation-card__action">
            {isPlace ? "查看位置" : "打开导航"} ↗
          </span>
        </div>
        {isPlace ? (
          <>
            <Space size={[4, 4]} wrap className="map-citation-card__tags">
              {ratingTag(Number(place.rating))}
              {Number(place.cost) > 0 && <Tag color="gold">人均 ¥{place.cost}</Tag>}
              {Number(place.comment_num) > 0 && <Tag>{place.comment_num} 条点评</Tag>}
              {formatDistance(place.distance) && (
                <Tag color="blue">距中心 {formatDistance(place.distance)}</Tag>
              )}
            </Space>
            {place.address && (
              <Typography.Text type="secondary" className="map-citation-card__meta">
                {String(place.address)}
              </Typography.Text>
            )}
          </>
        ) : (
          <div className="map-citation-card__route">
            <Tag color="geekblue">
              {MODE_LABELS[String(route.mode)] ?? route.mode ?? "路线"}
            </Tag>
            <Typography.Text type="secondary">
              {route.distance_text ?? "距离未知"} · {route.duration_text ?? "耗时未知"}
            </Typography.Text>
          </div>
        )}
      </div>
    </Card>
  );

  return url ? (
    <a
      className="map-citation-link"
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`${citation.title}，${isPlace ? "查看位置" : "打开导航"}`}
    >
      {content}
    </a>
  ) : (
    <div className="map-citation-link map-citation-link--disabled">{content}</div>
  );
}

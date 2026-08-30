import { trustedImageUrl } from "../utils/url";

export function PlaceCover({ imageUrl, name }: { imageUrl: unknown; name: string }) {
  const url = trustedImageUrl(imageUrl);
  if (!url) return null;
  return (
    <div className="map-place-cover">
      <img
        src={url}
        alt={`${name}门店图片`}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={(event) => {
          event.currentTarget.style.display = "none";
        }}
      />
    </div>
  );
}

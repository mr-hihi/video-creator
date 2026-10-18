import type { ImgHTMLAttributes } from "react";

type MarkdownImageProps = Pick<ImgHTMLAttributes<HTMLImageElement>, "src" | "alt" | "title">;

export function MarkdownImage({ src, alt = "", title }: MarkdownImageProps) {
  if (!src) return <span className="text-muted">{alt}</span>;
  return <img src={src} alt={alt} title={title} loading="lazy" />;
}

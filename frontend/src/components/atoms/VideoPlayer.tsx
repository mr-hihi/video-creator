import type { ImageOrientation } from "./AspectImage";

const VIDEO_ORIENTATION_CLASS_NAMES: Record<ImageOrientation, string> = {
  landscape: "aspect-video w-full",
  portrait: "mx-auto aspect-[9/16] w-full max-w-56",
};

interface VideoPlayerProps {
  src: string;
  label: string;
  orientation: ImageOrientation;
}

export function VideoPlayer({ src, label, orientation }: VideoPlayerProps) {
  return (
    <video
      controls
      preload="metadata"
      src={src}
      aria-label={label}
      className={`rounded-lg border border-border bg-background ${VIDEO_ORIENTATION_CLASS_NAMES[orientation]}`}
    />
  );
}

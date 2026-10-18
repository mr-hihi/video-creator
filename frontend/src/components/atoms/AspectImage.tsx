import Image from "next/image";

export type ImageOrientation = "landscape" | "portrait";

const ORIENTATION_CLASS_NAMES: Record<ImageOrientation, string> = {
  landscape: "aspect-video w-full",
  portrait: "mx-auto aspect-[9/16] w-full max-w-56",
};

const IMAGE_SIZES = "(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw";

interface AspectImageProps {
  src: string | undefined;
  alt: string;
  orientation: ImageOrientation;
  fallbackText: string;
}

export function AspectImage({ src, alt, orientation, fallbackText }: AspectImageProps) {
  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden rounded-lg border border-border bg-background p-2 text-center text-xs break-words text-muted ${ORIENTATION_CLASS_NAMES[orientation]}`}
    >
      {src ? <Image src={src} alt={alt} fill unoptimized sizes={IMAGE_SIZES} className="object-contain" /> : fallbackText}
    </div>
  );
}

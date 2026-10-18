"use client";

import { useRef } from "react";
import Image from "next/image";
import { AspectImage, type ImageOrientation } from "@/components/atoms/AspectImage";

interface EnlargeableImageProps {
  src: string;
  alt: string;
  orientation: ImageOrientation;
}

export function EnlargeableImage({ src, alt, orientation }: EnlargeableImageProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  return (
    <>
      <button
        type="button"
        aria-label={`Enlarge ${alt}`}
        onClick={() => dialogRef.current?.showModal()}
        className="block w-full cursor-zoom-in rounded-lg focus-visible:outline-2 focus-visible:outline-accent"
      >
        <AspectImage src={src} alt={alt} orientation={orientation} fallbackText={alt} />
      </button>
      <dialog ref={dialogRef} aria-label={alt} className="m-auto bg-transparent p-0 backdrop:bg-background/90">
        <form method="dialog">
          <button
            type="submit"
            aria-label="Close"
            className="relative block h-[85vh] w-[92vw] cursor-zoom-out focus-visible:outline-2 focus-visible:outline-accent"
          >
            <Image src={src} alt={alt} fill unoptimized sizes="92vw" className="object-contain" />
          </button>
        </form>
      </dialog>
    </>
  );
}

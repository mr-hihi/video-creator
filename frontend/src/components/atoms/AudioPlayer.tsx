interface AudioPlayerProps {
  src: string;
  label: string;
}

export function AudioPlayer({ src, label }: AudioPlayerProps) {
  return <audio controls preload="none" src={src} aria-label={label} className="w-full" />;
}

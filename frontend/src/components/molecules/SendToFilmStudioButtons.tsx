import { Button } from "@/components/atoms/Button";
import { SEND_TO_FILM_STUDIO_LABEL } from "@/features/films/constants";

interface SendToFilmStudioButtonsProps {
  canSubmit: boolean;
  isBusy: boolean;
  onCancel: () => void;
}

export function SendToFilmStudioButtons({ canSubmit, isBusy, onCancel }: SendToFilmStudioButtonsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button type="submit" disabled={!canSubmit}>
        {SEND_TO_FILM_STUDIO_LABEL}
      </Button>
      <Button variant="secondary" disabled={isBusy} onClick={onCancel}>
        Cancel
      </Button>
    </div>
  );
}

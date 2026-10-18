import type { AnchorHTMLAttributes } from "react";
import { buildButtonClassName, type ButtonVariant } from "./buttonStyles";

interface LinkButtonProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "className"> {
  href: string;
  variant?: ButtonVariant;
}

export function LinkButton({ variant = "primary", ...anchorProps }: LinkButtonProps) {
  return <a className={buildButtonClassName(variant)} {...anchorProps} />;
}

import type { ButtonHTMLAttributes } from "react";
import { buildButtonClassName, type ButtonVariant } from "./buttonStyles";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  variant?: ButtonVariant;
}

export function Button({ variant = "primary", type = "button", ...buttonProps }: ButtonProps) {
  return <button type={type} className={buildButtonClassName(variant)} {...buttonProps} />;
}

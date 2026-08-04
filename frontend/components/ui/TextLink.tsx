import Link, { type LinkProps } from "next/link";
import type { ReactNode } from "react";

// §11.8: color stopped being the only link signal once most colored text
// was removed from the palette — links are identified by underline.
export function TextLink({ children, className = "", ...props }: LinkProps & { children: ReactNode; className?: string }) {
  return (
    <Link
      className={`text-[11.5px] font-bold text-ink underline underline-offset-2 ${className}`}
      {...props}
    >
      {children}
    </Link>
  );
}

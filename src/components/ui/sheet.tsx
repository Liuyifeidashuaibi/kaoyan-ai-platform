"use client";

import * as React from "react";
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { XIcon } from "lucide-react";

import { cn } from "@/lib/utils";

function Sheet({ ...props }: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root {...props} />;
}

function SheetContent({
  className,
  children,
  side = "left",
  ...props
}: DialogPrimitive.Popup.Props & { side?: "left" | "right" }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Backdrop className="fixed inset-0 z-50 bg-black/20 data-open:animate-in data-open:fade-in-0" />
      <DialogPrimitive.Popup
        className={cn(
          "fixed z-50 flex h-full w-[280px] flex-col border-border bg-background shadow-lg outline-none data-open:animate-in data-open:fade-in-0 data-open:slide-in-from-left-4",
          side === "right" && "right-0 data-open:slide-in-from-right-4",
          side === "left" && "left-0",
          className
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground hover:bg-muted"
          aria-label="关闭"
        >
          <XIcon className="size-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Popup>
    </DialogPrimitive.Portal>
  );
}

export { Sheet, SheetContent };

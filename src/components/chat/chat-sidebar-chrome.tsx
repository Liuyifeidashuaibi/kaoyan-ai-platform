"use client";

import Image from "next/image";
import { PanelLeft, PanelLeftClose, SquarePen } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const iconBtnClass =
  "inline-flex size-9 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-muted/80";

function ChatLogoMark({ className }: { className?: string }) {
  return (
    <Image
      src="/logo.png"
      alt=""
      width={22}
      height={22}
      className={cn("dark:invert", className)}
    />
  );
}

type ChromeIconButtonProps = {
  onClick: () => void;
  label: string;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
  children: React.ReactNode;
};

function ChromeIconButton({
  onClick,
  label,
  side = "right",
  className,
  children,
}: ChromeIconButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger
        className={cn(iconBtnClass, className)}
        onClick={onClick}
        aria-label={label}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent side={side}>{label}</TooltipContent>
    </Tooltip>
  );
}

export function ChatSidebarOpenHeader({
  onCloseSidebar,
}: {
  onCloseSidebar: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center justify-between px-2 pt-2 pb-1">
      <div className={cn(iconBtnClass, "pointer-events-none")} aria-hidden>
        <ChatLogoMark />
      </div>
      <ChromeIconButton
        onClick={onCloseSidebar}
        label="Close sidebar"
        side="bottom"
      >
        <PanelLeftClose className="size-5" />
      </ChromeIconButton>
    </div>
  );
}

function ExpandSidebarIcon() {
  return (
    <>
      <ChatLogoMark className="transition-opacity group-hover:opacity-0" />
      <PanelLeft className="absolute size-5 opacity-0 transition-opacity group-hover:opacity-100" />
    </>
  );
}

export function ChatSidebarCollapsedRail({
  onExpandSidebar,
  onNewChat,
}: {
  onExpandSidebar: () => void;
  onNewChat: () => void;
}) {
  return (
    <aside className="hidden h-full w-14 shrink-0 flex-col items-center gap-0.5 border-r border-border bg-sidebar py-2 md:flex">
      <ChromeIconButton
        onClick={onExpandSidebar}
        label="Open sidebar"
        side="right"
        className="group relative"
      >
        <ExpandSidebarIcon />
      </ChromeIconButton>

      <ChromeIconButton onClick={onNewChat} label="New chat" side="right">
        <SquarePen className="size-5" />
      </ChromeIconButton>
    </aside>
  );
}

export function ChatSidebarMobileHeader({
  onToggleSidebar,
  title,
}: {
  onToggleSidebar: () => void;
  title: string;
}) {
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2 md:hidden">
      <ChromeIconButton
        onClick={onToggleSidebar}
        label="Open sidebar"
        side="bottom"
        className="group relative"
      >
        <ExpandSidebarIcon />
      </ChromeIconButton>
      <span className="truncate text-sm font-medium">{title}</span>
    </div>
  );
}

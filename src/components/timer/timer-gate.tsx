"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

interface TimerGateProps {
  status: "loading" | "ready" | "error" | "unauthenticated" | "unconfigured";
  error: string | null;
  title: string;
  loginNext: string;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function TimerGate({
  status,
  error,
  title,
  loginNext,
  onRetry,
  children,
}: TimerGateProps) {
  if (status === "loading") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Loader2 className="size-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  if (status === "unconfigured") {
    return (
      <div className="mx-auto max-w-lg px-6 py-16 text-center">
        <p className="text-sm text-neutral-500">
          {error ?? "Service is not configured."}
        </p>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return (
      <div className="mx-auto max-w-lg px-6 py-16 text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
          {title}
        </h1>
        <p className="mt-3 text-sm text-neutral-500">
          Sign in to save your study sessions to the cloud.
        </p>
        <Button asChild className="mt-6 rounded-xl">
          <Link href={`/login?next=${encodeURIComponent(loginNext)}`}>
            Sign In
          </Link>
        </Button>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="mx-auto max-w-lg px-6 py-16 text-center">
        <p className="text-sm text-neutral-500">{error}</p>
        {onRetry && (
          <Button
            type="button"
            variant="outline"
            className="mt-4 rounded-xl"
            onClick={onRetry}
          >
            Retry
          </Button>
        )}
      </div>
    );
  }

  return <>{children}</>;
}

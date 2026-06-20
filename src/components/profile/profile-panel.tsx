"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, ExternalLink, Heart, Loader2, Settings } from "lucide-react";

import { LogoutButton } from "@/components/auth/logout-button";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { getMyProfile, updateMyProfile } from "@/lib/api/community";
import type { CommunityUser } from "@/lib/api/types";
import {
  COMMUNITY_FAVORITES_DESCRIPTION,
  COMMUNITY_FAVORITES_LABEL,
  NOTEBOOK_DESCRIPTION,
  NOTEBOOK_LABEL,
  SUBJECT_CATEGORIES,
  communityFavoritesHref,
  notebookHref,
} from "@/lib/community/constants";

type ProfilePanelProps = {
  userId: string;
  email: string | undefined;
  createdAt: string | undefined;
};

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-right">{value}</span>
    </div>
  );
}

export function ProfilePanel({ userId, email, createdAt }: ProfilePanelProps) {
  const [profile, setProfile] = useState<CommunityUser | null>(null);
  const [subjectCategory, setSubjectCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const p = await getMyProfile();
        setProfile(p);
        setSubjectCategory(p.subject_category ?? "");
      } catch {
        setProfile(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [userId]);

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const p = await updateMyProfile({
        subject_category: subjectCategory || undefined,
      });
      setProfile(p);
      setMessage("Saved");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card className="max-w-lg">
        <CardContent className="flex justify-center py-12">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const profilePath = profile?.display_id || profile?.id || userId;
  const username =
    profile?.nickname ||
    profile?.display_id ||
    email?.split("@")[0] ||
    "—";

  return (
    <Card className="max-w-lg">
      <CardContent className="space-y-1 pt-6">
        <InfoRow label="Username" value={username} />
        <InfoRow label="Email" value={email ?? "Not set"} />
        <InfoRow
          label="Joined"
          value={createdAt ? formatDateTime(createdAt) : "Unknown"}
        />

        <Separator className="my-3" />

        <div className="flex items-center justify-between gap-4 py-2">
          <span className="text-sm text-muted-foreground">Subject Area</span>
          <select
            className="h-8 max-w-[10rem] rounded-md border border-input bg-transparent px-2 text-sm"
            value={subjectCategory}
            onChange={(e) => setSubjectCategory(e.target.value)}
          >
            <option value="">Not set</option>
            {SUBJECT_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <Separator className="my-3" />

        <div className="space-y-3 py-1">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Account
            </p>
            <Link
              href="/settings"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Settings className="mr-1.5 size-3.5" />
              Settings
            </Link>
            <p className="mt-1.5 text-xs text-muted-foreground">
              Translator download email and other module preferences.
            </p>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Community
            </p>
            <div className="flex flex-wrap gap-2">
              <Link
                href={`/user/${profilePath}`}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                <ExternalLink className="mr-1.5 size-3.5" />
                Community Profile
              </Link>
              <Link
                href={communityFavoritesHref()}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                <Heart className="mr-1.5 size-3.5" />
                {COMMUNITY_FAVORITES_LABEL}
              </Link>
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {COMMUNITY_FAVORITES_DESCRIPTION}
            </p>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Study Materials
            </p>
            <Link
              href={notebookHref()}
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <BookOpen className="mr-1.5 size-3.5" />
              {NOTEBOOK_LABEL}
            </Link>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {NOTEBOOK_DESCRIPTION}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 pt-3">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
          <LogoutButton />
        </div>

        {message && (
          <p className="pt-1 text-xs text-muted-foreground">{message}</p>
        )}
      </CardContent>
    </Card>
  );
}

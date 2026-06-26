"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, ExternalLink, Heart, Loader2, Mail } from "lucide-react";

import { LogoutButton } from "@/components/auth/logout-button";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { getMyProfile, updateMyProfile } from "@/lib/api/community";
import { getUserSettings, updateUserSettings } from "@/lib/api/settings";
import type { CommunityUser } from "@/lib/api/types";
import {
  COMMUNITY_FAVORITES_LABEL,
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
    <div className="flex items-center justify-between gap-4 py-2.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-right">{value}</span>
    </div>
  );
}

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm text-muted-foreground">{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function ProfilePanel({ userId, email, createdAt }: ProfilePanelProps) {
  const [profile, setProfile] = useState<CommunityUser | null>(null);
  const [subjectCategory, setSubjectCategory] = useState("");
  const [downloadEmail, setDownloadEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [p, s] = await Promise.all([getMyProfile(), getUserSettings()]);
        setProfile(p);
        setSubjectCategory(p.subject_category ?? "");
        setDownloadEmail(s.translation_download_email ?? "");
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
      await Promise.all([
        updateMyProfile({
          subject_category: subjectCategory || undefined,
        }),
        updateUserSettings({
          translation_download_email: downloadEmail.trim() || null,
        }),
      ]);
      setMessage("Saved");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card className="max-w-2xl">
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
  const initial = username.charAt(0).toUpperCase();

  return (
    <div className="grid gap-6 md:grid-cols-[280px_1fr]">
      {/* Left: User Info */}
      <Card className="h-fit">
        <CardContent className="flex flex-col items-center gap-4 pt-6">
          {/* Avatar */}
          <div className="flex size-20 items-center justify-center rounded-full bg-foreground text-2xl font-bold text-background">
            {initial}
          </div>

          <div className="w-full space-y-0.5">
            <InfoRow label="Username" value={username} />
            <InfoRow label="Email" value={email ?? "Not set"} />
            <InfoRow
              label="Joined"
              value={createdAt ? formatDateTime(createdAt) : "Unknown"}
            />
          </div>

          <Separator className="my-1" />

          <Link
            href={`/user/${profilePath}`}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            <ExternalLink className="mr-1.5 size-3.5" />
            Community Profile
          </Link>
        </CardContent>
      </Card>

      {/* Right: Settings (directly expanded) */}
      <Card>
        <CardContent className="space-y-8 pt-6">
          {/* Preferences */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Preferences</h3>
            <SettingRow
              label="Subject Area"
              hint="Used to filter relevant community content."
            >
              <select
                className="h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 text-sm"
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
            </SettingRow>
          </section>

          <Separator />

          {/* Translator Settings */}
          <section className="space-y-3">
            <h3 className="flex items-center gap-1.5 text-sm font-semibold">
              <Mail className="size-4" />
              Translator
            </h3>
            <SettingRow
              label="Download email"
              hint="Translation exports (Word, PDF, text) are emailed here instead of browser download. Leave empty to disable."
            >
              <Input
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={downloadEmail}
                onChange={(e) => setDownloadEmail(e.target.value)}
                className="max-w-xs"
              />
            </SettingRow>
          </section>

          <Separator />

          {/* Quick Links */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold">Quick Links</h3>
            <div className="flex flex-wrap gap-2">
              <Link
                href={communityFavoritesHref()}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                <Heart className="mr-1.5 size-3.5" />
                {COMMUNITY_FAVORITES_LABEL}
              </Link>
              <Link
                href={notebookHref()}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                <BookOpen className="mr-1.5 size-3.5" />
                {NOTEBOOK_LABEL}
              </Link>
            </div>
          </section>

          <Separator />

          {/* Actions */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
              {message && (
                <span className="text-xs text-emerald-600">{message}</span>
              )}
            </div>
            <LogoutButton />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

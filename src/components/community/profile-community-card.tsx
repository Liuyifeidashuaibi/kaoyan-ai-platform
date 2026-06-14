"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Users } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { getMyProfile, updateMyProfile } from "@/lib/api/community";
import type { CommunityUser } from "@/lib/api/types";
import { SUBJECT_CATEGORIES, communityFavoritesHref } from "@/lib/community/constants";

type ProfileCommunityCardProps = {
  userId: string;
};

export function ProfileCommunityCard({ userId }: ProfileCommunityCardProps) {
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
      setMessage("社区资料已保存");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card className="max-w-xl">
        <CardContent className="flex justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const profilePath = profile?.display_id || profile?.id || userId;

  return (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="size-5" />
          社区资料
        </CardTitle>
        <CardDescription>设置专业大类，其他用户可在社区主页看到你</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="display-id">用户 ID</Label>
          <p id="display-id" className="text-sm font-medium">
            {profile?.display_id ?? "—"}
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="subject">专业大类</Label>
          <select
            id="subject"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
            value={subjectCategory}
            onChange={(e) => setSubjectCategory(e.target.value)}
          >
            <option value="">未设置</option>
            {SUBJECT_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </Button>
          <Link
            href={`/user/${profilePath}`}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            查看社区主页
          </Link>
          <Link
            href={communityFavoritesHref()}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            我的收藏
          </Link>
        </div>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
      </CardContent>
    </Card>
  );
}

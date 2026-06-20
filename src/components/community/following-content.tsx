"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import { apiFetch } from "@/lib/api/client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";
import type { CommunityUser } from "@/lib/api/types";

export function FollowingContent() {
  const searchParams = useSearchParams();
  const userParam = searchParams.get("user");
  const [users, setUsers] = useState<CommunityUser[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const path = userParam
          ? `/api/community/following?user=${encodeURIComponent(userParam)}`
          : "/api/community/following";
        const data = await apiFetch<CommunityUser[]>(path, {
          headers: await getAuthHeaders(),
        });
        setUsers(data);
      } catch {
        setUsers([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [userParam]);

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex items-center gap-3">
        <Link href="/community" className={buttonVariants({ variant: "ghost", size: "icon-sm" })}>
          <ArrowLeft />
        </Link>
        <h1 className="text-2xl font-semibold">Following</h1>
      </div>
      {loading ? (
        <Loader2 className="mx-auto size-6 animate-spin text-muted-foreground" />
      ) : users.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">Not following anyone yet</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {users.map((u) => {
            const name = u.display_id || u.nickname || "User";
            return (
              <li key={u.id}>
                <Link
                  href={`/user/${u.display_id || u.id}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50"
                >
                  <Avatar size="sm">
                    <AvatarImage src={u.avatar_url ?? undefined} />
                    <AvatarFallback>{name.slice(0, 1)}</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">{name}</p>
                    {u.subject_category && (
                      <p className="text-xs text-muted-foreground">{u.subject_category}</p>
                    )}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

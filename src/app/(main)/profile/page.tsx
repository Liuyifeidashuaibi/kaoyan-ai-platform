import { redirect } from "next/navigation";

import { LogoutButton } from "@/components/auth/logout-button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { createClient } from "@/lib/supabase/server";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default async function ProfilePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login?next=/profile");
  }

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">个人中心</h1>
        <p className="text-muted-foreground">查看账号信息并管理登录状态</p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
          <CardDescription>当前登录账号的详细资料</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-muted-foreground">邮箱</span>
            <span className="text-sm font-medium">{user.email ?? "未设置"}</span>
          </div>
          <Separator />
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-muted-foreground">注册时间</span>
            <span className="text-sm font-medium">
              {user.created_at ? formatDateTime(user.created_at) : "未知"}
            </span>
          </div>
          <Separator />
          <div className="flex justify-end pt-2">
            <LogoutButton />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

import Link from "next/link";

import { hasAdminAllowlist } from "@/lib/admin/auth";
import { Button } from "@/components/ui/button";

export default function AdminForbiddenPage() {
  const noAllowlist = !hasAdminAllowlist();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-medium">
        {noAllowlist ? "后台未配置管理员" : "无管理权限"}
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">
        {noAllowlist ? (
          <>
            请在服务端环境变量{" "}
            <code className="rounded bg-muted px-1">ADMIN_EMAILS</code>{" "}
            中配置授权邮箱（逗号分隔），然后使用对应账号登录。
          </>
        ) : (
          <>
            当前账号不在管理员白名单中。请联系负责人将你的邮箱加入{" "}
            <code className="rounded bg-muted px-1">ADMIN_EMAILS</code>。
          </>
        )}
      </p>
      <div className="flex gap-2">
        <Button variant="outline" asChild>
          <Link href="/">返回首页</Link>
        </Button>
        <Button asChild>
          <Link href="/login?next=/admin/dashboard">切换账号</Link>
        </Button>
      </div>
    </div>
  );
}

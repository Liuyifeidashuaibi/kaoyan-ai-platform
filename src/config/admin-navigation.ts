import {
  Activity,
  Bot,
  GraduationCap,
  LayoutDashboard,
  MessageSquare,
  Settings,
  Users,
  type LucideIcon,
} from "lucide-react";

export type AdminNavItem = {
  id: string;
  label: string;
  href: string;
  /** 侧栏高亮匹配前缀，默认取 href */
  matchPrefix?: string;
  icon: LucideIcon;
  description?: string;
  badge?: "dot";
  children?: AdminSubNavItem[];
};

export type AdminSubNavItem = {
  label: string;
  href: string;
  description?: string;
};

export const adminNavItems: AdminNavItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    href: "/admin/dashboard",
    icon: LayoutDashboard,
    description: "运营总览与核心指标",
  },
  {
    id: "users",
    label: "用户中心",
    href: "/admin/users",
    icon: Users,
    description: "用户列表与行为统计",
    children: [
      { label: "用户列表", href: "/admin/users" },
      { label: "关注关系", href: "/admin/users/follows" },
      { label: "收藏统计", href: "/admin/users/favorites" },
      { label: "发帖统计", href: "/admin/users/posts" },
    ],
  },
  {
    id: "community",
    label: "社区中心",
    href: "/admin/community/posts",
    matchPrefix: "/admin/community",
    icon: MessageSquare,
    description: "帖子、评论与内容审核",
    children: [
      { label: "帖子管理", href: "/admin/community/posts" },
      { label: "评论管理", href: "/admin/community/comments" },
      { label: "举报管理", href: "/admin/community/reports" },
      { label: "内容审核", href: "/admin/community/moderation" },
    ],
  },
  {
    id: "schools",
    label: "择校中心",
    href: "/admin/schools/universities",
    matchPrefix: "/admin/schools",
    icon: GraduationCap,
    description: "院校数据与同步管理",
    children: [
      { label: "学校管理", href: "/admin/schools/universities" },
      { label: "学院管理", href: "/admin/schools/colleges" },
      { label: "专业管理", href: "/admin/schools/majors" },
      { label: "公告管理", href: "/admin/schools/announcements" },
      { label: "PDF 管理", href: "/admin/schools/pdfs" },
      { label: "同步记录", href: "/admin/schools/sync-logs" },
    ],
  },
  {
    id: "agents",
    label: "Agent 中心",
    href: "/admin/agents",
    icon: Bot,
    description: "Agent 控制台与任务编排",
    badge: "dot",
  },
  {
    id: "monitoring",
    label: "系统监控",
    href: "/admin/monitoring",
    matchPrefix: "/admin/monitoring",
    icon: Activity,
    description: "API、数据库与任务队列",
    children: [
      { label: "监控总览", href: "/admin/monitoring" },
      { label: "API 状态", href: "/admin/monitoring/api" },
      { label: "数据库", href: "/admin/monitoring/database" },
      { label: "Agent 状态", href: "/admin/monitoring/agents" },
      { label: "错误日志", href: "/admin/monitoring/errors" },
      { label: "任务队列", href: "/admin/monitoring/queue" },
    ],
  },
  {
    id: "settings",
    label: "系统设置",
    href: "/admin/settings",
    matchPrefix: "/admin/settings",
    icon: Settings,
    description: "通用配置与权限",
    children: [
      { label: "设置首页", href: "/admin/settings" },
      { label: "通用设置", href: "/admin/settings/general" },
      { label: "角色权限", href: "/admin/settings/roles" },
      { label: "第三方集成", href: "/admin/settings/integrations" },
    ],
  },
];

export function isAdminNavItemActive(pathname: string, item: AdminNavItem) {
  if (item.id === "dashboard") {
    return pathname === "/admin/dashboard";
  }
  const prefix = item.matchPrefix ?? item.href;
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

export function getAdminNavItem(pathname: string): AdminNavItem | undefined {
  return adminNavItems.find((item) => isAdminNavItemActive(pathname, item));
}

export function getAdminBreadcrumbs(pathname: string): { label: string; href?: string }[] {
  const crumbs: { label: string; href?: string }[] = [
    { label: "运营台", href: "/admin/dashboard" },
  ];

  const active = adminNavItems.find((item) => isAdminNavItemActive(pathname, item));

  if (!active || active.id === "dashboard") {
    if (pathname === "/admin/dashboard") {
      crumbs.push({ label: "Dashboard" });
    }
    return crumbs;
  }

  crumbs.push({ label: active.label, href: active.href });

  const child = active.children?.find(
    (c) => pathname === c.href || pathname.startsWith(`${c.href}/`)
  );
  if (child && child.href !== active.href) {
    crumbs.push({ label: child.label });
  } else if (pathname !== active.href) {
    const segments = pathname.split("/").filter(Boolean);
    const last = segments[segments.length - 1];
    if (last && !active.children?.some((c) => c.href.endsWith(last))) {
      crumbs.push({ label: last });
    }
  }

  return crumbs;
}

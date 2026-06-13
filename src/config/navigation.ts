import {
  BookOpen,
  GraduationCap,
  Home,
  MessageSquare,
  Timer,
  User,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  description?: string;
};

export const navItems: NavItem[] = [
  {
    href: "/",
    label: "首页",
    icon: Home,
    description: "平台概览与学习入口",
  },
  {
    href: "/chat",
    label: "AI 聊天",
    icon: MessageSquare,
    description: "智能答疑与备考助手",
  },
  {
    href: "/wrong-questions",
    label: "错题本",
    icon: BookOpen,
    description: "错题整理与 AI 解析",
  },
  {
    href: "/schools",
    label: "择校",
    icon: GraduationCap,
    description: "院校与专业查询（/choose-school）",
  },
  {
    href: "/study/tomato",
    label: "番茄钟",
    icon: Timer,
    description: "专注计时与本地统计",
  },
  {
    href: "/community",
    label: "社区",
    icon: Users,
    description: "研友交流与分享",
  },
  {
    href: "/profile",
    label: "个人中心",
    icon: User,
    description: "账号与目标设置",
  },
];

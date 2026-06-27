import {
  BookOpen,
  Bot,
  GraduationCap,
  Home,
  Languages,
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
    label: "Home",
    icon: Home,
    description: "Platform overview",
  },
  {
    href: "/chat",
    label: "Chat",
    icon: MessageSquare,
    description: "AI study assistant",
  },
  {
    href: "/agent",
    label: "Agent",
    icon: Bot,
    description: "Document generation workbench",
  },
  {
    href: "/wrong-questions",
    label: "Notebook",
    icon: BookOpen,
    description: "Private study materials library",
  },
  {
    href: "/translator",
    label: "Translator",
    icon: Languages,
    description: "AI translation tools",
  },
  {
    href: "/choose-school",
    label: "School",
    icon: GraduationCap,
    description: "University search",
  },
  {
    href: "/study/tomato",
    label: "Timer",
    icon: Timer,
    description: "Focus timer",
  },
  {
    href: "/community",
    label: "Community",
    icon: Users,
    description: "Study community",
  },
  {
    href: "/profile",
    label: "Profile",
    icon: User,
    description: "Account settings",
  },
];

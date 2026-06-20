import Link from "next/link";
import {
  BookOpen,
  GraduationCap,
  MessageSquare,
  User,
  Users,
} from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const features = [
  {
    href: "/chat",
    label: "Chat",
    description: "AI Q&A with streaming replies and image upload",
    icon: MessageSquare,
  },
  {
    href: "/wrong-questions",
    label: "Notebook",
    description: "Private study materials library",
    icon: BookOpen,
  },
  {
    href: "/choose-school",
    label: "School",
    description: "Search universities and majors",
    icon: GraduationCap,
  },
  {
    href: "/community",
    label: "Community",
    description: "Share experiences and connect with peers",
    icon: Users,
  },
  {
    href: "/profile",
    label: "Profile",
    description: "Account, favorites, and notebook",
    icon: User,
  },
] as const;

export default function HomePage() {
  return (
    <div className="flex flex-col gap-8 p-6 md:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">PNIXPG</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.href} className="flex flex-col">
              <CardHeader>
                <div className="mb-2 flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </div>
                <CardTitle>{item.label}</CardTitle>
                <CardDescription>{item.description}</CardDescription>
              </CardHeader>
              <CardContent className="mt-auto">
                <Link
                  href={item.href}
                  className={cn(buttonVariants({ variant: "outline" }), "w-full")}
                >
                  Open {item.label}
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

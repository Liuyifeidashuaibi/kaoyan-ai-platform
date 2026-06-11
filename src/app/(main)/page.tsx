import Link from "next/link";
import { BookOpen, MessageSquare, Timer } from "lucide-react";

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
    label: "AI 聊天",
    description: "多轮答疑、流式回复，支持上传数学题图片",
    icon: MessageSquare,
  },
  {
    href: "/wrong-questions",
    label: "错题本",
    description: "分类整理错题，AI 解析，一键追问",
    icon: BookOpen,
  },
  {
    href: "/study/tomato",
    label: "番茄钟",
    description: "专注计时与本地学习统计",
    icon: Timer,
  },
] as const;

export default function HomePage() {
  return (
    <div className="flex flex-col gap-8 p-6 md:p-8">
      <div className="max-w-2xl space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">考研 AI 平台</h1>
        <p className="text-muted-foreground">
          智能备考助手：AI 答疑、错题整理与专注学习，从这里开始。
        </p>
      </div>

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
                  进入 {item.label}
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

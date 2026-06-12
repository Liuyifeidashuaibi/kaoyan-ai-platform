"use client";

import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { TabNav } from "@/components/schools/tab-nav";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { getAnnouncements, type Announcement } from "@/lib/api/schools";

interface AnnouncementsTabProps {
  universityId: string;
}

const ANN_TABS = [
  { value: "招生公告", label: "招生公告" },
  { value: "招生简章", label: "招生简章" },
  { value: "调剂公告", label: "调剂" },
  { value: "推免公告", label: "推免" },
];

export function AnnouncementsTab({ universityId }: AnnouncementsTabProps) {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState("招生公告");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await getAnnouncements(universityId);
        setAnnouncements(data);
      } catch (err) {
        console.error("加载公告失败:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [universityId]);

  const filtered = announcements.filter((a) => a.type === activeType);

  return (
    <div className="flex flex-col h-full">
      <TabNav
        tabs={ANN_TABS}
        active={activeType}
        onChange={setActiveType}
        className="border-t-0"
      />

      <div className="flex-1 overflow-y-auto bg-card">
        {loading ? (
          <SkeletonList count={5} className="rounded-none" />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="暂无相关公告"
            description="公告数据将在爬虫运行后自动同步"
          />
        ) : (
          <div className="pb-8">
            {filtered.map((ann) => (
              <AnnouncementRow key={ann.id} ann={ann} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AnnouncementRow({ ann }: { ann: Announcement }) {
  return (
    <a
      href={ann.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-start gap-3 px-4 py-3.5 border-b border-border/60 last:border-0 hover:bg-muted/30 transition-colors"
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm leading-snug line-clamp-2">{ann.title}</p>
        <p className="mt-1 text-xs text-muted-foreground">{ann.publish_time}</p>
      </div>
      <ExternalLink className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
    </a>
  );
}

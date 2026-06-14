export const SUBJECT_CATEGORIES = [
  "哲学", "经济学", "法学", "教育学", "文学",
  "历史学", "理学", "工学", "农学", "医学",
  "军事学", "管理学", "艺术学",
] as const;

export type SubjectCategory = (typeof SUBJECT_CATEGORIES)[number];

export const POST_TYPES = [
  { value: "experience" as const, label: "经验帖" },
  { value: "material" as const, label: "资料帖" },
];

export type PostType = (typeof POST_TYPES)[number]["value"];

export const POST_TYPE_LABELS: Record<PostType, string> = {
  experience: "经验帖",
  material: "资料帖",
};

export const COMMUNITY_SORT_TABS = [
  { value: "latest" as const, label: "最新" },
  { value: "hot" as const, label: "最热" },
];

/** 社区收藏列表页 */
export function communityFavoritesHref() {
  return "/favorites";
}

export const SUBJECT_CATEGORIES = [
  "哲学", "经济学", "法学", "教育学", "文学",
  "历史学", "理学", "工学", "农学", "医学",
  "军事学", "管理学", "艺术学",
] as const;

/** 发帖必填年级 */
export const COHORT_GRADES = ["23级", "24级", "25级", "26级"] as const;

export type CohortGrade = (typeof COHORT_GRADES)[number];

export type SubjectCategory = (typeof SUBJECT_CATEGORIES)[number];

export const POST_TYPES = [
  { value: "experience" as const, label: "Experience" },
  { value: "material" as const, label: "Resources" },
];

export type PostType = (typeof POST_TYPES)[number]["value"];

export const POST_TYPE_LABELS: Record<PostType, string> = {
  experience: "Experience",
  material: "Resources",
};

export const COMMUNITY_SORT_TABS = [
  { value: "latest" as const, label: "Latest" },
  { value: "hot" as const, label: "Hot" },
];

/** Community post favorites — not Notebook uploads */
export const COMMUNITY_FAVORITES_LABEL = "Favorites";
export const COMMUNITY_FAVORITES_DESCRIPTION =
  "Community posts you saved for later";

export function communityFavoritesHref() {
  return "/favorites";
}

export const NOTEBOOK_LABEL = "Notebook";
export const NOTEBOOK_DESCRIPTION =
  "Private study materials — for your personal use only";

export function notebookHref() {
  return "/wrong-questions";
}

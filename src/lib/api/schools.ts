/**
 * 择校模块 Supabase 数据查询工具函数
 * 使用 universities / majors / scores / announcements / recommendations / adjustments 表
 */
import { createClient } from "@/lib/supabase/client";

// ──────────────────────────────────────────────────────────────
// 类型别名
// ──────────────────────────────────────────────────────────────
export type University = {
  id: string;
  name: string;
  logo_url: string | null;
  province: string;
  city: string;
  level_985: boolean;
  level_211: boolean;
  double_first_class: string | null;
  school_type: string | null;
  intro: string | null;
  description: string | null;
  address: string | null;
  website: string | null;
  code: string | null;
};

export type UniversityWithMajorCount = University & { major_count: number };

export type Major = {
  id: string;
  university_id: string;
  college: string | null;
  name: string;
  code: string | null;
  degree_type: string | null;
  study_mode: string | null;
  exam_type: string | null;
  enrollment_count: number | null;
  subject_category: string | null;
  first_discipline: string | null;
};

export type Score = {
  id: string;
  university_id: string;
  major_id: string;
  year: number;
  total_score: number;
  politics_score: number;
  english_score: number;
  professional1_score: number | null;
  professional2_score: number | null;
  line_diff: number | null;
};

export type ScoreWithMajor = Score & {
  majors: Pick<Major, "name" | "code" | "degree_type" | "study_mode" | "college"> | null;
};

export type Announcement = {
  id: string;
  university_id: string;
  title: string;
  publish_time: string;
  url: string;
  type: string;
};

export type Recommendation = {
  id: string;
  university_id: string;
  title: string;
  type: string;
  status: string;
  start_time: string | null;
  end_time: string | null;
  url: string;
};

export type Adjustment = {
  id: string;
  university_id: string;
  major_id: string | null;
  year: number;
  major_name: string;
  quota: number | null;
  requirements: string | null;
  contact: string | null;
  url: string | null;
};

export interface UniversityFilters {
  level985?: boolean;
  level211?: boolean;
  doubleFirstClass?: boolean;
  region?: string;
  search?: string;
}

// 省份 → 大区映射
export const REGION_MAP: Record<string, string[]> = {
  全国: [],
  华北: ["北京", "天津", "河北", "山西", "内蒙古"],
  华东: ["上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"],
  华南: ["广东", "广西", "海南"],
  华中: ["河南", "湖北", "湖南"],
  西南: ["重庆", "四川", "贵州", "云南", "西藏"],
  西北: ["陕西", "甘肃", "青海", "宁夏", "新疆"],
  东北: ["辽宁", "吉林", "黑龙江"],
};

export const SUBJECT_CATEGORIES = [
  "哲学", "经济学", "法学", "教育学", "文学",
  "历史学", "理学", "工学", "农学", "医学",
  "军事学", "管理学", "艺术学",
];

// ──────────────────────────────────────────────────────────────
// 院校查询
// ──────────────────────────────────────────────────────────────

export async function getUniversities(
  filters: UniversityFilters = {}
): Promise<UniversityWithMajorCount[]> {
  const client = createClient();
  let query = client
    .from("universities")
    .select(
      "id, name, logo_url, province, city, level_985, level_211, double_first_class, school_type, intro, description, address, website, code, majors(count)",
      { count: "exact" }
    )
    .order("name", { ascending: true });

  const levelConditions: string[] = [];
  if (filters.level985) levelConditions.push("level_985.eq.true");
  if (filters.level211) levelConditions.push("level_211.eq.true");
  if (filters.doubleFirstClass) levelConditions.push("double_first_class.not.is.null");

  if (levelConditions.length > 0 && levelConditions.length < 3) {
    query = query.or(levelConditions.join(","));
  }

  if (filters.region && filters.region !== "全国") {
    const provinces = REGION_MAP[filters.region] ?? [];
    if (provinces.length > 0) query = query.in("province", provinces);
  }

  if (filters.search?.trim()) {
    const kw = filters.search.trim();
    query = query.or(`name.ilike.%${kw}%,city.ilike.%${kw}%,province.ilike.%${kw}%`);
  }

  const { data, error } = await query;
  if (error) throw error;

  return (data ?? []).map((row) => {
    const majorsArr = row.majors as unknown as { count: number }[];
    const major_count = majorsArr?.[0]?.count ?? 0;
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { majors: _m, ...university } = row as typeof row & { majors: unknown };
    return { ...university, major_count } as UniversityWithMajorCount;
  });
}

export async function getUniversity(id: string): Promise<University | null> {
  const client = createClient();
  const { data, error } = await client
    .from("universities")
    .select("id, name, logo_url, province, city, level_985, level_211, double_first_class, school_type, intro, description, address, website, code")
    .eq("id", id)
    .single();
  if (error) return null;
  return data as University;
}

// ──────────────────────────────────────────────────────────────
// 专业查询
// ──────────────────────────────────────────────────────────────

export async function getMajors(
  universityId: string,
  filters: { studyMode?: string; degreeType?: string; search?: string } = {}
): Promise<Major[]> {
  const client = createClient();
  let query = client
    .from("majors")
    .select("id, university_id, college, name, code, degree_type, study_mode, exam_type, enrollment_count, subject_category, first_discipline")
    .eq("university_id", universityId)
    .order("code", { ascending: true });

  if (filters.studyMode) query = query.eq("study_mode", filters.studyMode);
  if (filters.degreeType) query = query.eq("degree_type", filters.degreeType);
  if (filters.search?.trim()) {
    const kw = filters.search.trim();
    query = query.or(`name.ilike.%${kw}%,code.ilike.%${kw}%,college.ilike.%${kw}%`);
  }

  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Major[];
}

export type MajorWithSchool = Major & {
  university: Pick<University, "id" | "name" | "province" | "level_985" | "level_211" | "double_first_class"> | null;
};

export async function getMajorsByCategory(
  subjectCategory: string,
  filters: UniversityFilters = {}
): Promise<MajorWithSchool[]> {
  const client = createClient();
  let query = client
    .from("majors")
    .select("id, university_id, college, name, code, degree_type, study_mode, exam_type, enrollment_count, subject_category, first_discipline, university:universities(id, name, province, level_985, level_211, double_first_class)")
    .eq("subject_category", subjectCategory)
    .order("code", { ascending: true });

  const { data, error } = await query;
  if (error) throw error;

  const all = (data ?? []) as (Major & { university: University })[];

  return all.filter((m) => {
    if (!m.university) return false;
    if (!filters.level985 && !filters.level211 && !filters.doubleFirstClass) return true;
    if (filters.level985 && m.university.level_985) return true;
    if (filters.level211 && m.university.level_211) return true;
    if (filters.doubleFirstClass && m.university.double_first_class) return true;
    return false;
  }) as MajorWithSchool[];
}

// ──────────────────────────────────────────────────────────────
// 分数线查询
// ──────────────────────────────────────────────────────────────

export async function getScores(
  universityId: string,
  filters: { year?: number; degreeType?: string; search?: string } = {}
): Promise<ScoreWithMajor[]> {
  const client = createClient();
  let query = client
    .from("scores")
    .select(`id, university_id, major_id, year, total_score, politics_score, english_score, professional1_score, professional2_score, line_diff, majors(name, code, degree_type, study_mode, college)`)
    .eq("university_id", universityId)
    .order("year", { ascending: false })
    .order("total_score", { ascending: false });

  if (filters.year) query = query.eq("year", filters.year);

  const { data, error } = await query;
  if (error) throw error;

  let result = (data ?? []) as ScoreWithMajor[];

  if (filters.degreeType) {
    result = result.filter((r) => r.majors?.degree_type === filters.degreeType);
  }
  if (filters.search?.trim()) {
    const kw = filters.search.trim().toLowerCase();
    result = result.filter(
      (r) =>
        r.majors?.name?.toLowerCase().includes(kw) ||
        r.majors?.code?.toLowerCase().includes(kw)
    );
  }

  return result;
}

export async function getScoreYears(universityId: string): Promise<number[]> {
  const client = createClient();
  const { data, error } = await client
    .from("scores")
    .select("year")
    .eq("university_id", universityId)
    .order("year", { ascending: false });
  if (error) return [];
  return [...new Set((data ?? []).map((r: { year: number }) => r.year))];
}

// ──────────────────────────────────────────────────────────────
// 公告查询
// ──────────────────────────────────────────────────────────────

export async function getAnnouncements(
  universityId: string,
  type?: string
): Promise<Announcement[]> {
  const client = createClient();
  let query = client
    .from("announcements")
    .select("id, university_id, title, publish_time, url, type")
    .eq("university_id", universityId)
    .order("publish_time", { ascending: false });
  if (type) query = query.eq("type", type);
  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Announcement[];
}

// ──────────────────────────────────────────────────────────────
// 推免查询
// ──────────────────────────────────────────────────────────────

export async function getRecommendations(
  universityId: string,
  type?: string,
  status?: string
): Promise<Recommendation[]> {
  const client = createClient();
  let query = client
    .from("recommendations")
    .select("id, university_id, title, type, status, start_time, end_time, url")
    .eq("university_id", universityId)
    .order("start_time", { ascending: false });
  if (type) query = query.eq("type", type);
  if (status) query = query.eq("status", status);
  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Recommendation[];
}

// ──────────────────────────────────────────────────────────────
// 调剂查询
// ──────────────────────────────────────────────────────────────

export async function getAdjustments(
  universityId: string,
  year?: number
): Promise<Adjustment[]> {
  const client = createClient();
  let query = client
    .from("adjustments")
    .select("id, university_id, major_id, year, major_name, quota, requirements, contact, url")
    .eq("university_id", universityId)
    .order("year", { ascending: false });
  if (year) query = query.eq("year", year);
  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Adjustment[];
}

// ──────────────────────────────────────────────────────────────
// 工具函数
// ──────────────────────────────────────────────────────────────

export function getUniversityLevelTags(uni: University): string[] {
  const tags: string[] = [];
  if (uni.level_985) tags.push("985");
  if (uni.level_211) tags.push("211");
  if (uni.double_first_class) {
    if (uni.double_first_class.includes("一流大学A")) tags.push("双一流A");
    else if (uni.double_first_class.includes("一流大学B")) tags.push("双一流B");
    else tags.push("一流学科");
  }
  return tags;
}

export function getUniversityInitial(name: string): string {
  const cleaned = name.replace(/^中国/, "").replace(/大学$/, "").replace(/学院$/, "");
  return cleaned.slice(0, 2);
}

export function getLineDiffColor(diff: number | null): string {
  if (diff === null) return "text-muted-foreground";
  if (diff > 0) return "text-emerald-600";
  if (diff < 0) return "text-red-500";
  return "text-muted-foreground";
}

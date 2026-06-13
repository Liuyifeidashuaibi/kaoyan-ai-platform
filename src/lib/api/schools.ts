/**
 * 择校模块 Supabase 数据查询工具函数
 * 使用 universities / majors / scores 表（择校核心）
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
  address: string | null;
  website: string | null;
  school_code: string | null;
  graduate_url: string | null;
};

export type UniversityWithMajorCount = University & {
  major_count: number;
  enrollment_total: number;
};

/** 按 6 位专业代码聚合后的专业维度数据 */
export type AggregatedMajor = {
  code: string;
  name: string;
  /** 各校使用的其他名称（用于搜索匹配） */
  alt_names: string[];
  degree_type: string;
  subject_category: string | null;
  first_discipline: string | null;
  university_count: number;
  total_enrollment: number;
};

/** 某专业代码下开设院校 */
export type MajorUniversityOffering = {
  major_id: string;
  university_id: string;
  name: string;
  degree_type: string | null;
  college: string | null;
  study_mode: string | null;
  exam_type: string | null;
  enrollment_count: number | null;
  university: Pick<
    University,
    "id" | "name" | "province" | "city" | "level_985" | "level_211" | "double_first_class" | "school_type"
  > | null;
};

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
  score_type?: string | null;
  source_url?: string | null;
  publish_date?: string | null;
  confidence?: number | null;
  remarks?: string | null;
};

export type ScoreWithMajor = Score & {
  majors: Pick<Major, "name" | "code" | "degree_type" | "study_mode" | "college"> | null;
};

export type MajorStatistics = {
  id: string;
  university_id: string;
  college_id: string | null;
  major_id: string;
  year: number;
  min_score: number | null;
  avg_score: number | null;
  max_score: number | null;
  admitted_count: number;
  retest_count: number | null;
  admission_rate: number | null;
  retest_line: number | null;
  quota: number | null;
  exempt_count: number | null;
  source_url: string | null;
  source_title: string | null;
  publish_date: string | null;
  raw_file_path: string | null;
  majors: Pick<Major, "name" | "code" | "degree_type" | "study_mode" | "college"> | null;
};

export type MajorStatisticsGroup = {
  majorId: string;
  name: string;
  code: string | null;
  college: string | null;
  degreeType: string | null;
  stats: MajorStatistics[];
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
  province?: string;
  schoolType?: string;
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

/** 学科门类编号（用于双栏筛选左栏展示） */
export const SUBJECT_CATEGORY_CODES: Record<string, string> = {
  哲学: "01", 经济学: "02", 法学: "03", 教育学: "04", 文学: "05",
  历史学: "06", 理学: "07", 工学: "08", 农学: "09", 医学: "10",
  军事学: "11", 管理学: "12", 艺术学: "13",
};

export const SCHOOL_TYPES = [
  "综合", "理工", "师范", "财经", "政法", "医药", "农林", "艺术", "民族", "体育",
] as const;

export const DEGREE_TYPE_OPTIONS = [
  { value: "", label: "全部" },
  { value: "学硕", label: "学术型硕士" },
  { value: "专硕", label: "专业型硕士" },
] as const;

export interface MajorAggregatedFilters {
  level985?: boolean;
  level211?: boolean;
  doubleFirstClass?: boolean;
  degreeType?: string;
  subjectCategory?: string;
  firstDiscipline?: string;
  search?: string;
}

function normalizeMajorCode(code: string | null): string | null {
  if (!code) return null;
  const digits = code.replace(/\D/g, "");
  if (digits.length < 6) return null;
  return digits.slice(0, 6);
}

function subjectCategoryFromCode(code: string): string | null {
  const prefix = code.replace(/\D/g, "").slice(0, 2);
  return (
    Object.entries(SUBJECT_CATEGORY_CODES).find(([, c]) => c === prefix)?.[0] ??
    null
  );
}

function resolveSubjectCategory(
  code: string,
  stored: string | null
): string | null {
  return stored ?? subjectCategoryFromCode(code);
}

const INVALID_TEXT_RE =
  /电话|手机|@\d|https?:\/\/|\.com|!\[|IE|浏览器|验证码|温馨提示|招生办|联系老师|导师|可接收|考生|本科毕业|浏览效果|建议使用|招生简章|专业目录|请点击/i;

const PROF_CODE_PREFIXES = new Set([
  "025", "035", "045", "055", "065", "075", "085", "095", "105", "115", "125", "135", "145",
]);

/** 6 位专业代码是否像研招专业代码 */
export function isValidMajorCode(code: string | null | undefined): boolean {
  const digits = (code ?? "").replace(/\D/g, "");
  if (digits.length !== 6) return false;
  const prefix2 = digits.slice(0, 2);
  const prefix3 = digits.slice(0, 3);
  const valid2 =
    (prefix2 >= "01" && prefix2 <= "15") ||
    prefix2 === "10" ||
    prefix2 === "11" ||
    prefix2 === "12" ||
    prefix2 === "13" ||
    prefix2 === "14";
  if (!valid2 && !PROF_CODE_PREFIXES.has(prefix3)) return false;
  if (digits.startsWith("10") && Number(digits.slice(2, 4)) >= 50) return false;
  return true;
}

/** 过滤爬虫误抓的噪声专业名（电话、HTML 碎片、老师姓名等） */
export function isValidMajorName(name: string | null | undefined): boolean {
  const n = (name ?? "").trim();
  if (!n || n.length < 2 || n.length > 35) return false;
  if (INVALID_TEXT_RE.test(n)) return false;
  if (/^电话[：:]/.test(n)) return false;
  if (/^0\d{2,3}[-\s]?\d{7,}/.test(n)) return false;
  if (/^!\[/.test(n)) return false;
  // 人名误识别：陈老师、骆老师
  if (/^[\u4e00-\u9fa5]{1,3}老师$/.test(n)) return false;
  if (/[\u4e00-\u9fa5]{1,2}老师/.test(n) && n.length <= 6) return false;
  // 须以中文为主
  const chinese = (n.match(/[\u4e00-\u9fa5]/g) ?? []).length;
  if (chinese < n.length * 0.5) return false;
  return true;
}

/** 同时校验专业名与代码 */
export function isValidMajorRecord(
  major: Pick<Major, "name" | "code">
): boolean {
  return isValidMajorName(major.name) && isValidMajorCode(major.code);
}

/** 一级学科名称校验（用于专业分类筛选） */
export function isValidDisciplineName(name: string | null | undefined): boolean {
  const n = (name ?? "").trim();
  if (!n || n.length < 2 || n.length > 24) return false;
  if (INVALID_TEXT_RE.test(n)) return false;
  if (/老师|导师|电话|未知学院|IE|浏览效果|可接收|考生/.test(n)) return false;
  if (SUBJECT_CATEGORIES.includes(n)) return true;
  if (/学$|论$|法$|史$|学$/.test(n) || n.endsWith("工程")) return true;
  return n.length <= 12 && !/\d{4,}/.test(n);
}

function isLikelyCollegeName(name: string): boolean {
  return /学院|系|中心|部|研究所|研究院|实验室/.test(name);
}

/** 院校详情页专业分组：学院 > 一级学科 > 学科门类 */
export function resolveMajorGroupLabel(
  major: Pick<Major, "college" | "first_discipline" | "subject_category">
): string {
  const college = major.college?.trim();
  const discipline = major.first_discipline?.trim();
  const category = major.subject_category?.trim();
  if (college && college !== "未知学院" && isLikelyCollegeName(college)) {
    return college;
  }
  // college 为空表示研招网未提供院系，按一级学科分组
  if (discipline && isValidDisciplineName(discipline)) return discipline;
  if (category) return category;
  return "其他专业";
}

/** 专业 Tab 按所属学院分组（仅展示 college，无则归入未标注） */
export function resolveCollegeGroupLabel(
  major: Pick<Major, "college">
): string {
  const college = major.college?.trim();
  if (college && college !== "未知学院" && isLikelyCollegeName(college)) {
    return college;
  }
  return "未标注学院";
}

export type CollegeStats = {
  /** 已标注学院数量（去重） */
  labeledColleges: number;
  /** 未标注学院的专业条数 */
  unlabeledMajors: number;
  totalMajors: number;
};

/** 院校专业学院覆盖统计 */
export function computeCollegeStats(
  majors: Pick<Major, "college">[]
): CollegeStats {
  const colleges = new Set<string>();
  let unlabeled = 0;
  for (const m of majors) {
    const label = resolveCollegeGroupLabel(m);
    if (label === "未标注学院") {
      unlabeled += 1;
    } else {
      colleges.add(label);
    }
  }
  return {
    labeledColleges: colleges.size,
    unlabeledMajors: unlabeled,
    totalMajors: majors.length,
  };
}

export type ScoreCollegeGroup = {
  college: string;
  groups: MajorScoreGroup[];
};

/** 复试线按学院分组（院校详情页分数线 Tab） */
export function groupScoresByCollege(
  scoreGroups: MajorScoreGroup[]
): ScoreCollegeGroup[] {
  const map = new Map<string, MajorScoreGroup[]>();
  for (const g of scoreGroups) {
    const label =
      g.college?.trim() &&
      g.college !== "未知学院" &&
      isLikelyCollegeName(g.college)
        ? g.college.trim()
        : "未标注学院";
    const list = map.get(label) ?? [];
    list.push(g);
    map.set(label, list);
  }
  return [...map.entries()]
    .sort(([a], [b]) => {
      if (a === "未标注学院") return 1;
      if (b === "未标注学院") return -1;
      return a.localeCompare(b, "zh-CN");
    })
    .map(([college, groups]) => ({ college, groups }));
}

function degreeTypeLabel(type: string | null): string {
  if (type === "专硕") return "专业型硕士";
  if (type === "学硕") return "学术型硕士";
  return type ?? "学术型硕士";
}

function passesUniversityLevelFilter(
  uni: Pick<University, "level_985" | "level_211" | "double_first_class">,
  filters: UniversityFilters | MajorAggregatedFilters
): boolean {
  const hasLevel =
    filters.level985 || filters.level211 || filters.doubleFirstClass;
  if (!hasLevel) return true;
  if (filters.level985 && uni.level_985) return true;
  if (filters.level211 && uni.level_211) return true;
  if (filters.doubleFirstClass && uni.double_first_class) return true;
  return false;
}

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
      "id, name, logo_url, province, city, level_985, level_211, double_first_class, school_type, intro, address, website, school_code, graduate_url, majors(count)",
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

  if (filters.province && filters.province !== "全部") {
    query = query.eq("province", filters.province);
  } else if (filters.region && filters.region !== "全国") {
    const provinces = REGION_MAP[filters.region] ?? [];
    if (provinces.length > 0) query = query.in("province", provinces);
  }

  if (filters.schoolType && filters.schoolType !== "全部") {
    query = query.eq("school_type", filters.schoolType);
  }

  if (filters.search?.trim()) {
    const kw = filters.search.trim();
    query = query.or(`name.ilike.%${kw}%,city.ilike.%${kw}%,province.ilike.%${kw}%`);
  }

  const { data, error } = await query;
  if (error) throw error;

  type UniRow = University & { majors: { count: number }[] | null };
  return ((data ?? []) as UniRow[]).map((row) => {
    const major_count = row.majors?.[0]?.count ?? 0;
    const { majors: _m, ...university } = row;
    return {
      ...university,
      major_count,
      enrollment_total: 0,
    };
  });
}

/** 获取全部省份（用于筛选下拉） */
export async function getProvinces(): Promise<string[]> {
  const client = createClient();
  const { data, error } = await client
    .from("universities")
    .select("province")
    .order("province");
  if (error) return [];
  const rows = (data ?? []) as { province: string | null }[];
  return [...new Set(rows.map((r) => r.province).filter(Boolean))] as string[];
}

export async function getUniversity(id: string): Promise<University | null> {
  const client = createClient();
  const { data, error } = await client
    .from("universities")
    .select("id, name, logo_url, province, city, level_985, level_211, double_first_class, school_type, intro, address, website, school_code, graduate_url")
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
  const pageSize = 1000;
  let from = 0;
  const all: Major[] = [];

  while (true) {
    let query = client
      .from("majors")
      .select(
        "id, university_id, college, name, code, degree_type, study_mode, exam_type, enrollment_count, subject_category, first_discipline"
      )
      .eq("university_id", universityId)
      .order("code", { ascending: true })
      .range(from, from + pageSize - 1);

    if (filters.studyMode) query = query.eq("study_mode", filters.studyMode);
    if (filters.degreeType) query = query.eq("degree_type", filters.degreeType);
    if (filters.search?.trim()) {
      const kw = filters.search.trim();
      query = query.or(`name.ilike.%${kw}%,code.ilike.%${kw}%,college.ilike.%${kw}%`);
    }

    const { data, error } = await query;
    if (error) throw error;
    const batch = (data ?? []) as Major[];
    all.push(...batch);
    if (batch.length < pageSize) break;
    from += pageSize;
  }

  return all.filter((m) => isValidMajorRecord(m));
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

type MajorRowWithUni = Major & {
  university: University | null;
};

let majorsCatalogCache: MajorRowWithUni[] | null = null;
let majorsCatalogPromise: Promise<MajorRowWithUni[]> | null = null;
let universitiesListCache: UniversityWithMajorCount[] | null = null;
let universitiesListPromise: Promise<UniversityWithMajorCount[]> | null = null;

export function invalidateSchoolsCache(): void {
  majorsCatalogCache = null;
  majorsCatalogPromise = null;
  universitiesListCache = null;
  universitiesListPromise = null;
}

/** 预加载专业目录（页面 mount 时调用，加速「按专业」Tab） */
export function prefetchMajorsCatalog(): Promise<MajorRowWithUni[]> {
  if (majorsCatalogCache) return Promise.resolve(majorsCatalogCache);
  if (!majorsCatalogPromise) {
    majorsCatalogPromise = loadAllMajorsWithUniversity()
      .then((rows) => {
        majorsCatalogCache = rows.filter((r) => isValidMajorRecord(r));
        return majorsCatalogCache;
      })
      .catch((err) => {
        majorsCatalogPromise = null;
        throw err;
      });
  }
  return majorsCatalogPromise;
}

/** 用校验后的专业缓存重算院校专业数 / 招生人数 */
function enrichUniversitiesWithValidatedCounts(
  unis: UniversityWithMajorCount[],
  catalog: MajorRowWithUni[]
): UniversityWithMajorCount[] {
  const stats = new Map<string, { count: number; enrollment: number }>();
  for (const row of catalog) {
    if (!isValidMajorRecord(row)) continue;
    const s = stats.get(row.university_id) ?? { count: 0, enrollment: 0 };
    s.count += 1;
    s.enrollment += row.enrollment_count ?? 0;
    stats.set(row.university_id, s);
  }
  return unis.map((u) => {
    const s = stats.get(u.id);
    return {
      ...u,
      major_count: s?.count ?? u.major_count,
      enrollment_total: s?.enrollment ?? 0,
    };
  });
}

/** 预加载院校列表（先返回院校基础数据，专业数后台用目录校准） */
export function prefetchUniversitiesList(): Promise<UniversityWithMajorCount[]> {
  if (universitiesListCache) return Promise.resolve(universitiesListCache);
  if (!universitiesListPromise) {
    universitiesListPromise = getUniversities({
      level985: true,
      level211: true,
      doubleFirstClass: true,
    })
      .then((rows) => {
        universitiesListCache = rows;
        void prefetchMajorsCatalog()
          .then((catalog) => {
            universitiesListCache = enrichUniversitiesWithValidatedCounts(rows, catalog);
          })
          .catch(() => {});
        return rows;
      })
      .catch((err) => {
        universitiesListPromise = null;
        throw err;
      });
  }
  return universitiesListPromise;
}

export function prefetchSchoolsData(): Promise<[MajorRowWithUni[], UniversityWithMajorCount[]]> {
  return Promise.all([prefetchMajorsCatalog(), prefetchUniversitiesList()]);
}

export function isSchoolsDataReady(): boolean {
  return majorsCatalogCache !== null && universitiesListCache !== null;
}

/** 客户端筛选院校（基于预加载缓存，Tab 切换无网络延迟） */
export function filterUniversitiesClient(
  list: UniversityWithMajorCount[],
  filters: UniversityFilters = {}
): UniversityWithMajorCount[] {
  return list.filter((uni) => {
    if (!passesUniversityLevelFilter(uni, filters)) return false;

    if (filters.province && filters.province !== "全部" && uni.province !== filters.province) {
      return false;
    }
    if (filters.region && filters.region !== "全国") {
      const provinces = REGION_MAP[filters.region] ?? [];
      if (provinces.length > 0 && !provinces.includes(uni.province)) return false;
    }
    if (filters.schoolType && filters.schoolType !== "全部" && uni.school_type !== filters.schoolType) {
      return false;
    }
    if (filters.search?.trim()) {
      const kw = filters.search.trim().toLowerCase();
      if (
        !uni.name.toLowerCase().includes(kw) &&
        !uni.city?.toLowerCase().includes(kw) &&
        !(uni.province ?? "").includes(kw)
      ) {
        return false;
      }
    }
    return true;
  });
}

export type UniversitySortMode = "default" | "type" | "level" | "region";
export type UniversitySortDirection = "asc" | "desc";

export type UniversityListGroup = {
  key: string;
  label: string;
  universities: UniversityWithMajorCount[];
};

const REGION_ORDER = [
  "华北",
  "华东",
  "华南",
  "华中",
  "西南",
  "西北",
  "东北",
] as const;

const LEVEL_GROUP_ORDER = ["985高校", "211高校", "双一流高校", "其他院校"] as const;

function compareByName(
  a: UniversityWithMajorCount,
  b: UniversityWithMajorCount,
  direction: UniversitySortDirection
): number {
  const cmp = a.name.localeCompare(b.name, "zh-CN");
  return direction === "asc" ? cmp : -cmp;
}

function getUniversityLevelGroup(uni: UniversityWithMajorCount): string {
  if (uni.level_985) return "985高校";
  if (uni.level_211) return "211高校";
  if (uni.double_first_class) return "双一流高校";
  return "其他院校";
}

function getUniversityLevelRank(uni: UniversityWithMajorCount): number {
  if (uni.level_985) return 0;
  if (uni.level_211) return 1;
  if (uni.double_first_class) return 2;
  return 3;
}

function getUniversityRegion(uni: UniversityWithMajorCount): string {
  for (const region of REGION_ORDER) {
    if ((REGION_MAP[region] ?? []).includes(uni.province)) return region;
  }
  return "其他";
}

function getSchoolTypeSortKey(type: string | null): number {
  if (!type) return SCHOOL_TYPES.length;
  const idx = SCHOOL_TYPES.indexOf(type as (typeof SCHOOL_TYPES)[number]);
  return idx >= 0 ? idx : SCHOOL_TYPES.length;
}

function getRegionSortIndex(region: string): number {
  const idx = REGION_ORDER.indexOf(region as (typeof REGION_ORDER)[number]);
  return idx >= 0 ? idx : REGION_ORDER.length;
}

function sortUniversitiesInGroup(
  list: UniversityWithMajorCount[],
  mode: UniversitySortMode,
  direction: UniversitySortDirection
): UniversityWithMajorCount[] {
  const sorted = [...list];
  sorted.sort((a, b) => {
    if (mode === "default") {
      const levelDiff = getUniversityLevelRank(a) - getUniversityLevelRank(b);
      if (levelDiff !== 0) return direction === "asc" ? levelDiff : -levelDiff;
      return compareByName(a, b, direction);
    }
    if (mode === "type") {
      const typeDiff = getSchoolTypeSortKey(a.school_type) - getSchoolTypeSortKey(b.school_type);
      if (typeDiff !== 0) return direction === "asc" ? typeDiff : -typeDiff;
      return compareByName(a, b, "asc");
    }
    if (mode === "level") {
      const levelDiff = getUniversityLevelRank(a) - getUniversityLevelRank(b);
      if (levelDiff !== 0) return direction === "asc" ? levelDiff : -levelDiff;
      return compareByName(a, b, "asc");
    }
    const regionDiff = getRegionSortIndex(getUniversityRegion(a)) - getRegionSortIndex(getUniversityRegion(b));
    if (regionDiff !== 0) return direction === "asc" ? regionDiff : -regionDiff;
    const provinceDiff = (a.province ?? "").localeCompare(b.province ?? "", "zh-CN");
    if (provinceDiff !== 0) return direction === "asc" ? provinceDiff : -provinceDiff;
    return compareByName(a, b, "asc");
  });
  return sorted;
}

/** 按模式分组/排序院校列表（默认模式不分组） */
export function organizeUniversitiesClient(
  list: UniversityWithMajorCount[],
  mode: UniversitySortMode,
  direction: UniversitySortDirection = "asc"
): UniversityListGroup[] {
  if (mode === "default") {
    return [
      {
        key: "all",
        label: "全部院校",
        universities: sortUniversitiesInGroup(list, "default", direction),
      },
    ];
  }

  const buckets = new Map<string, UniversityWithMajorCount[]>();

  for (const uni of list) {
    let key: string;
    let label: string;
    if (mode === "type") {
      key = uni.school_type?.trim() || "未分类";
      label = key;
    } else if (mode === "level") {
      key = getUniversityLevelGroup(uni);
      label = key;
    } else {
      key = getUniversityRegion(uni);
      label = key;
    }
    const arr = buckets.get(key) ?? [];
    arr.push(uni);
    buckets.set(key, arr);
  }

  const orderKeys = (keys: string[]): string[] => {
    if (mode === "type") {
      const ordered = [...SCHOOL_TYPES.map(String), "未分类"].filter((k) => buckets.has(k));
      const rest = [...buckets.keys()].filter((k) => !ordered.includes(k)).sort((a, b) =>
        a.localeCompare(b, "zh-CN")
      );
      const merged = [...ordered, ...rest];
      return direction === "asc" ? merged : [...merged].reverse();
    }
    if (mode === "level") {
      const ordered = [...LEVEL_GROUP_ORDER].filter((k) => buckets.has(k));
      const orderedSet = new Set<string>(ordered);
      const rest = [...buckets.keys()].filter((k) => !orderedSet.has(k));
      const merged = [...ordered, ...rest];
      return direction === "asc" ? merged : [...merged].reverse();
    }
    const ordered = [...REGION_ORDER, "其他"].filter((k) => buckets.has(k));
    return direction === "asc" ? ordered : [...ordered].reverse();
  };

  return orderKeys([...buckets.keys()]).map((key) => ({
    key,
    label: key,
    universities: sortUniversitiesInGroup(buckets.get(key) ?? [], mode, "asc"),
  }));
}

function pickCanonicalMajorName(nameCounts: Map<string, number>): string {
  let best = "";
  let bestCount = 0;
  for (const [name, count] of nameCounts) {
    if (count > bestCount || (count === bestCount && name.length > best.length)) {
      best = name;
      bestCount = count;
    }
  }
  return best;
}

/** 客户端聚合专业：先按校记录，再按 code+学位 汇总为多校开设 */
export function aggregateMajorsClient(
  rows: MajorRowWithUni[],
  filters: MajorAggregatedFilters = {}
): AggregatedMajor[] {
  const map = new Map<
    string,
    AggregatedMajor & { _nameCounts: Map<string, number>; _uniIds: Set<string> }
  >();

  for (const row of rows) {
    if (!row.university || !passesUniversityLevelFilter(row.university, filters)) continue;
    if (!isValidMajorRecord(row)) continue;

    const code = normalizeMajorCode(row.code);
    if (!code) continue;

    if (filters.degreeType && row.degree_type !== filters.degreeType) continue;

    const subjectCategory = resolveSubjectCategory(code, row.subject_category);
    if (filters.subjectCategory && subjectCategory !== filters.subjectCategory) continue;
    if (filters.firstDiscipline && row.first_discipline !== filters.firstDiscipline) continue;

    const key = `${code}::${row.degree_type ?? "学硕"}`;
    const existing = map.get(key);
    if (!existing) {
      const counts = new Map([[row.name, 1]]);
      map.set(key, {
        code,
        name: row.name,
        alt_names: [],
        degree_type: row.degree_type ?? "学硕",
        subject_category: subjectCategory,
        first_discipline: row.first_discipline,
        university_count: 1,
        total_enrollment: row.enrollment_count ?? 0,
        _nameCounts: counts,
        _uniIds: new Set([row.university_id]),
      });
    } else {
      existing._uniIds.add(row.university_id);
      existing.university_count = existing._uniIds.size;
      existing.total_enrollment += row.enrollment_count ?? 0;
      existing._nameCounts.set(
        row.name,
        (existing._nameCounts.get(row.name) ?? 0) + 1
      );
      if (!existing.first_discipline && row.first_discipline) {
        existing.first_discipline = row.first_discipline;
      }
      if (!existing.subject_category && subjectCategory) {
        existing.subject_category = subjectCategory;
      }
    }
  }

  let result: AggregatedMajor[] = [...map.values()].map((m) => {
    const canonical = pickCanonicalMajorName(m._nameCounts);
    const alt_names = [...m._nameCounts.keys()].filter((n) => n !== canonical);
    const { _nameCounts: _, _uniIds: __, ...rest } = m;
    return { ...rest, name: canonical, alt_names };
  });

  if (filters.search?.trim()) {
    const kw = filters.search.trim().toLowerCase();
    result = result.filter(
      (m) =>
        m.name.toLowerCase().includes(kw) ||
        m.code.includes(kw) ||
        (m.first_discipline ?? "").toLowerCase().includes(kw) ||
        m.alt_names.some((n) => n.toLowerCase().includes(kw))
    );
  }

  return result.sort((a, b) => a.code.localeCompare(b.code));
}

/** 客户端构建学科树（基于预加载缓存） */
export function buildDisciplineTreeClient(
  rows: MajorRowWithUni[]
): Record<string, string[]> {
  const tree: Record<string, Set<string>> = {};

  for (const row of rows) {
    if (!isValidMajorRecord(row)) continue;
    const code = normalizeMajorCode(row.code);
    if (!code || !row.first_discipline) continue;
    if (!isValidDisciplineName(row.first_discipline)) continue;
    const cat = resolveSubjectCategory(code, row.subject_category);
    if (!cat) continue;
    (tree[cat] ??= new Set()).add(row.first_discipline);
  }

  return Object.fromEntries(
    Object.entries(tree).map(([cat, set]) => [cat, [...set].sort()])
  );
}

async function loadAllMajorsWithUniversity(): Promise<MajorRowWithUni[]> {
  const client = createClient();
  const pageSize = 1000;
  let from = 0;
  const all: MajorRowWithUni[] = [];

  while (true) {
    const { data, error } = await client
      .from("majors")
      .select(
        "id, university_id, college, name, code, degree_type, study_mode, exam_type, enrollment_count, subject_category, first_discipline, university:universities(id, name, province, city, level_985, level_211, double_first_class, school_type)"
      )
      .order("code", { ascending: true })
      .range(from, from + pageSize - 1);

    if (error) throw error;
    const batch = (data ?? []) as MajorRowWithUni[];
    all.push(...batch);
    if (batch.length < pageSize) break;
    from += pageSize;
  }

  return all;
}

async function fetchAllMajorsWithUniversity(): Promise<MajorRowWithUni[]> {
  if (majorsCatalogCache) return majorsCatalogCache;
  return prefetchMajorsCatalog();
}

export type SchoolSearchHit = UniversityWithMajorCount & {
  matchedMajors: string[];
  matchReason: "school" | "major" | "both";
};

export type UnifiedSearchResult = {
  schools: SchoolSearchHit[];
  majors: AggregatedMajor[];
};

/** 统一搜索：院校 + 聚合专业（基于本地缓存，无 500 条上限） */
export async function searchUnified(keyword: string): Promise<UnifiedSearchResult> {
  const kw = keyword.trim();
  if (!kw) return { schools: [], majors: [] };

  const kwLower = kw.toLowerCase();
  const [allUnis, catalog] = await Promise.all([
    prefetchUniversitiesList(),
    prefetchMajorsCatalog(),
  ]);

  const hitMap = new Map<string, SchoolSearchHit>();
  const uniById = new Map(allUnis.map((u) => [u.id, u]));

  for (const uni of allUnis) {
    const nameMatch = uni.name.toLowerCase().includes(kwLower);
    const locMatch =
      uni.city?.toLowerCase().includes(kwLower) ||
      (uni.province ?? "").includes(kw);
    if (nameMatch || locMatch) {
      hitMap.set(uni.id, {
        ...uni,
        matchedMajors: [],
        matchReason: "school",
      });
    }
  }

  for (const row of catalog) {
    if (!isValidMajorRecord(row)) continue;
    const majorName = row.name;
    const code = normalizeMajorCode(row.code) ?? "";
    const discipline = row.first_discipline ?? "";
    const matched =
      majorName.toLowerCase().includes(kwLower) ||
      code.includes(kw) ||
      discipline.toLowerCase().includes(kwLower);
    if (!matched) continue;

    const uni = uniById.get(row.university_id);
    if (!uni) continue;

    const existing = hitMap.get(uni.id);
    if (existing) {
      if (!existing.matchedMajors.includes(majorName)) {
        existing.matchedMajors.push(majorName);
      }
      if (existing.matchReason === "school") existing.matchReason = "both";
    } else {
      hitMap.set(uni.id, {
        ...uni,
        matchedMajors: [majorName],
        matchReason: "major",
      });
    }
  }

  const schools = [...hitMap.values()].sort((a, b) =>
    a.name.localeCompare(b.name, "zh-CN")
  );

  const majors = aggregateMajorsClient(catalog, {
    level985: true,
    level211: true,
    doubleFirstClass: true,
    search: kw,
  });

  return { schools, majors };
}

/** @deprecated 使用 searchUnified */
export async function searchSchoolsUnified(
  keyword: string
): Promise<SchoolSearchHit[]> {
  const { schools } = await searchUnified(keyword);
  return schools;
}

/** 按院校聚合专业开设方向（专业详情页用） */
export type GroupedMajorUniversity = {
  university_id: string;
  university: MajorUniversityOffering["university"];
  colleges: string[];
  study_modes: string[];
  total_enrollment: number;
  offerings: MajorUniversityOffering[];
};

export function groupMajorOfferingsByUniversity(
  offerings: MajorUniversityOffering[]
): GroupedMajorUniversity[] {
  const map = new Map<string, GroupedMajorUniversity>();

  for (const item of offerings) {
    if (!item.university) continue;
    let group = map.get(item.university_id);
    if (!group) {
      group = {
        university_id: item.university_id,
        university: item.university,
        colleges: [],
        study_modes: [],
        total_enrollment: 0,
        offerings: [],
      };
      map.set(item.university_id, group);
    }
    group.offerings.push(item);
    if (item.college && !group.colleges.includes(item.college)) {
      group.colleges.push(item.college);
    }
    if (item.study_mode && !group.study_modes.includes(item.study_mode)) {
      group.study_modes.push(item.study_mode);
    }
    group.total_enrollment += item.enrollment_count ?? 0;
  }

  return [...map.values()].sort((a, b) =>
    (a.university?.name ?? "").localeCompare(b.university?.name ?? "", "zh-CN")
  );
}

/** 专业维度：按 6 位代码聚合全部目标院校招生专业 */
export async function getAggregatedMajors(
  filters: MajorAggregatedFilters = {}
): Promise<AggregatedMajor[]> {
  const rows = await fetchAllMajorsWithUniversity();
  return aggregateMajorsClient(rows, filters);
}

/** 获取某专业代码下全部开设院校 */
export async function getUniversitiesByMajorCode(
  code: string,
  degreeType?: string
): Promise<MajorUniversityOffering[]> {
  const normalized = normalizeMajorCode(code) ?? code;
  const rows = await fetchAllMajorsWithUniversity();

  return rows
    .filter((row) => {
      if (!isValidMajorRecord(row)) return false;
      const rowCode = normalizeMajorCode(row.code);
      if (rowCode !== normalized) return false;
      if (degreeType && row.degree_type !== degreeType) return false;
      return true;
    })
    .map((row) => ({
      major_id: row.id,
      university_id: row.university_id,
      name: row.name,
      degree_type: row.degree_type,
      college: row.college,
      study_mode: row.study_mode,
      exam_type: row.exam_type,
      enrollment_count: row.enrollment_count,
      university: row.university
        ? {
            id: row.university.id,
            name: row.university.name,
            province: row.university.province,
            city: row.university.city,
            level_985: row.university.level_985,
            level_211: row.university.level_211,
            double_first_class: row.university.double_first_class,
            school_type: row.university.school_type,
          }
        : null,
    }));
}

/** 从现有专业数据构建学科大类 → 二级专业映射 */
export async function getDisciplineTree(): Promise<
  Record<string, string[]>
> {
  const rows = await fetchAllMajorsWithUniversity();
  return buildDisciplineTreeClient(rows);
}

export function formatMajorPath(major: Pick<
  AggregatedMajor,
  "degree_type" | "subject_category" | "first_discipline" | "name"
>): string {
  const degree = degreeTypeLabel(major.degree_type);
  const parts = [degree, major.subject_category, major.first_discipline ?? major.name].filter(
    Boolean
  );
  return parts.join(" — ");
}

export function isHotUniversity(uni: University): boolean {
  return uni.level_985;
}

/** 择校动态数据展示年份（复试线） */
export const SCHOOL_CONTENT_YEAR = 2025;

/** 仅展示进复试分数线对应的考试年份 */
export const SCORE_DISPLAY_YEARS = [2026, 2025] as const;

/** 拟录取统计展示年份 */
export const STATISTICS_DISPLAY_YEARS = [2026, 2025, 2024] as const;

// ──────────────────────────────────────────────────────────────
// 真实上岸线 / 拟录取统计
// ──────────────────────────────────────────────────────────────

export async function getMajorStatistics(
  universityId: string,
  filters: { year?: number; degreeType?: string; search?: string; majorCode?: string } = {}
): Promise<MajorStatistics[]> {
  const client = createClient();
  let query = client
    .from("major_statistics")
    .select(
      `id, university_id, college_id, major_id, year, min_score, avg_score, max_score, admitted_count, retest_count, admission_rate, retest_line, quota, exempt_count, source_url, source_title, publish_date, raw_file_path, majors(name, code, degree_type, study_mode, college)`
    )
    .eq("university_id", universityId)
    .in("year", [...STATISTICS_DISPLAY_YEARS])
    .order("year", { ascending: false })
    .order("min_score", { ascending: true });

  if (filters.year != null) {
    query = query.eq("year", filters.year);
  }

  const { data, error } = await query;
  if (error) throw error;

  let result = (data ?? []) as MajorStatistics[];

  if (filters.degreeType) {
    result = result.filter((r) => r.majors?.degree_type === filters.degreeType);
  }
  if (filters.majorCode?.trim()) {
    const normalized = normalizeMajorCode(filters.majorCode.trim());
    if (normalized) {
      result = result.filter(
        (r) => normalizeMajorCode(r.majors?.code ?? null) === normalized
      );
    }
  }
  if (filters.search?.trim()) {
    const kw = filters.search.trim().toLowerCase();
    result = result.filter(
      (r) =>
        r.majors?.name?.toLowerCase().includes(kw) ||
        r.majors?.code?.toLowerCase().includes(kw) ||
        (r.majors?.college ?? "").toLowerCase().includes(kw)
    );
  }

  return result;
}

export async function getStatisticsYears(universityId: string): Promise<number[]> {
  const client = createClient();
  const { data, error } = await client
    .from("major_statistics")
    .select("year")
    .eq("university_id", universityId)
    .in("year", [...STATISTICS_DISPLAY_YEARS]);
  if (error) return [];
  const rows = (data ?? []) as { year: number }[];
  return [
    ...new Set(rows.map((r) => r.year)),
  ]
    .filter((y) => (STATISTICS_DISPLAY_YEARS as readonly number[]).includes(y))
    .sort((a, b) => b - a);
}

export function groupStatisticsByMajor(stats: MajorStatistics[]): MajorStatisticsGroup[] {
  const map = new Map<string, MajorStatisticsGroup>();

  for (const stat of stats) {
    let group = map.get(stat.major_id);
    if (!group) {
      group = {
        majorId: stat.major_id,
        name: stat.majors?.name ?? "—",
        code: stat.majors?.code ?? null,
        college: stat.majors?.college ?? null,
        degreeType: stat.majors?.degree_type ?? null,
        stats: [],
      };
      map.set(stat.major_id, group);
    }
    group.stats.push(stat);
  }

  return [...map.values()].sort((a, b) => {
    const codeA = normalizeMajorCode(a.code) ?? "";
    const codeB = normalizeMajorCode(b.code) ?? "";
    return codeA.localeCompare(codeB) || a.name.localeCompare(b.name, "zh-CN");
  });
}

export type StatisticsCollegeGroup = {
  college: string;
  groups: MajorStatisticsGroup[];
};

export function groupStatisticsByCollege(
  groups: MajorStatisticsGroup[]
): StatisticsCollegeGroup[] {
  const map = new Map<string, MajorStatisticsGroup[]>();
  for (const g of groups) {
    const college = resolveCollegeGroupLabel({ college: g.college });
    const list = map.get(college) ?? [];
    list.push(g);
    map.set(college, list);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b, "zh-CN"))
    .map(([college, groupsInCollege]) => ({
      college,
      groups: groupsInCollege,
    }));
}

/** 专业维度：按代码查全部开设院校的录取统计 */
export async function getStatisticsByMajorCode(
  code: string,
  degreeType?: string
): Promise<MajorStatistics[]> {
  const offerings = await getUniversitiesByMajorCode(code, degreeType);
  const majorIds = offerings.map((o) => o.major_id);
  if (majorIds.length === 0) return [];

  const client = createClient();
  const all: MajorStatistics[] = [];
  const batchSize = 100;

  for (let i = 0; i < majorIds.length; i += batchSize) {
    const batch = majorIds.slice(i, i + batchSize);
    const { data, error } = await client
      .from("major_statistics")
      .select(
        `id, university_id, college_id, major_id, year, min_score, avg_score, max_score, admitted_count, retest_count, admission_rate, retest_line, quota, exempt_count, source_url, source_title, publish_date, raw_file_path, majors(name, code, degree_type, study_mode, college)`
      )
      .in("major_id", batch)
      .in("year", [...STATISTICS_DISPLAY_YEARS])
      .order("year", { ascending: false })
      .order("min_score", { ascending: true });
    if (error) throw error;
    all.push(...((data ?? []) as MajorStatistics[]));
  }

  return all;
}

/** 返回已有真实上岸线数据的院校 ID 集合 */
export async function getUniversitiesWithStatistics(): Promise<Set<string>> {
  const client = createClient();
  const { data, error } = await client
    .from("major_statistics")
    .select("university_id")
    .in("year", [...STATISTICS_DISPLAY_YEARS]);
  if (error) return new Set();
  const rows = (data ?? []) as { university_id: string }[];
  return new Set(rows.map((r) => r.university_id));
}

// ──────────────────────────────────────────────────────────────
// 复试线查询（进复试最低分，仅 2025/2026）
// ──────────────────────────────────────────────────────────────

export async function getScores(
  universityId: string,
  filters: { year?: number; degreeType?: string; search?: string; majorCode?: string } = {}
): Promise<ScoreWithMajor[]> {
  const client = createClient();
  let query = client
    .from("scores")
    .select(`id, university_id, major_id, year, total_score, politics_score, english_score, professional1_score, professional2_score, line_diff, score_type, source_url, publish_date, confidence, remarks, majors(name, code, degree_type, study_mode, college)`)
    .eq("university_id", universityId)
    .in("year", [...SCORE_DISPLAY_YEARS])
    .order("year", { ascending: false })
    .order("total_score", { ascending: false });

  if (filters.year != null) {
    query = query.eq("year", filters.year);
  }

  const { data, error } = await query;
  if (error) throw error;

  let result = (data ?? []) as ScoreWithMajor[];

  if (filters.degreeType) {
    result = result.filter((r) => r.majors?.degree_type === filters.degreeType);
  }
  if (filters.majorCode?.trim()) {
    const normalized = normalizeMajorCode(filters.majorCode.trim());
    if (normalized) {
      result = result.filter(
        (r) => normalizeMajorCode(r.majors?.code ?? null) === normalized
      );
    }
  }
  if (filters.search?.trim()) {
    const kw = filters.search.trim().toLowerCase();
    result = result.filter(
      (r) =>
        r.majors?.name?.toLowerCase().includes(kw) ||
        r.majors?.code?.toLowerCase().includes(kw) ||
        (r.majors?.college ?? "").toLowerCase().includes(kw)
    );
  }

  return result;
}

/** 返回该校已有复试线记录的专业代码集合（6 位，用于专业页联动高亮） */
export async function getScoredMajorCodes(universityId: string): Promise<Set<string>> {
  const scores = await getScores(universityId);
  const codes = new Set<string>();
  for (const s of scores) {
    const code = normalizeMajorCode(s.majors?.code ?? null);
    if (code) codes.add(code);
  }
  return codes;
}

export async function getScoreYears(universityId: string): Promise<number[]> {
  const client = createClient();
  const { data, error } = await client
    .from("scores")
    .select("year")
    .eq("university_id", universityId)
    .in("year", [...SCORE_DISPLAY_YEARS]);
  if (error) return [];
  const rows = (data ?? []) as { year: number }[];
  const years = [
    ...new Set(rows.map((r) => r.year)),
  ]
    .filter((y) => (SCORE_DISPLAY_YEARS as readonly number[]).includes(y))
    .sort((a, b) => b - a);
  return years;
}

/** 专业维度：按代码查全部开设院校的历年复试分数线（1:1 绑定 major_id） */
export async function getScoresByMajorCode(
  code: string,
  degreeType?: string
): Promise<ScoreWithMajor[]> {
  const offerings = await getUniversitiesByMajorCode(code, degreeType);
  const majorIds = offerings.map((o) => o.major_id);
  if (majorIds.length === 0) return [];

  const client = createClient();
  const all: ScoreWithMajor[] = [];
  const batchSize = 100;

  for (let i = 0; i < majorIds.length; i += batchSize) {
    const batch = majorIds.slice(i, i + batchSize);
    const { data, error } = await client
      .from("scores")
      .select(
        `id, university_id, major_id, year, total_score, politics_score, english_score, professional1_score, professional2_score, line_diff, score_type, source_url, publish_date, confidence, remarks, majors(name, code, degree_type, study_mode, college)`
      )
      .in("major_id", batch)
      .in("year", [...SCORE_DISPLAY_YEARS])
      .order("year", { ascending: false })
      .order("total_score", { ascending: false });
    if (error) throw error;
    all.push(...((data ?? []) as ScoreWithMajor[]));
  }

  return all;
}

export type MajorScoreGroup = {
  majorId: string;
  name: string;
  code: string | null;
  college: string | null;
  degreeType: string | null;
  scores: ScoreWithMajor[];
};

/** 按专业分组历年复试分数线（院校详情页用） */
export function groupScoresByMajor(scores: ScoreWithMajor[]): MajorScoreGroup[] {
  const map = new Map<string, MajorScoreGroup>();

  for (const score of scores) {
    let group = map.get(score.major_id);
    if (!group) {
      group = {
        majorId: score.major_id,
        name: score.majors?.name ?? "—",
        code: score.majors?.code ?? null,
        college: score.majors?.college ?? null,
        degreeType: score.majors?.degree_type ?? null,
        scores: [],
      };
      map.set(score.major_id, group);
    }
    group.scores.push(score);
  }

  return [...map.values()].sort((a, b) => {
    const codeA = normalizeMajorCode(a.code) ?? "";
    const codeB = normalizeMajorCode(b.code) ?? "";
    return codeA.localeCompare(codeB) || a.name.localeCompare(b.name, "zh-CN");
  });
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
    .or(
      `start_time.gte.${SCHOOL_CONTENT_YEAR}-01-01,start_time.is.null`
    )
    .order("start_time", { ascending: false });
  if (type) query = query.eq("type", type);
  if (status) query = query.eq("status", status);
  const { data, error } = await query;
  if (error) throw error;
  const yearStart = `${SCHOOL_CONTENT_YEAR}-01-01`;
  const yearEnd = `${SCHOOL_CONTENT_YEAR + 1}-01-01`;
  return ((data ?? []) as Recommendation[]).filter((r) => {
    if (r.start_time) {
      return r.start_time >= yearStart && r.start_time < yearEnd;
    }
    return r.title.includes(String(SCHOOL_CONTENT_YEAR));
  });
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
    .eq("year", year ?? SCHOOL_CONTENT_YEAR)
    .order("year", { ascending: false });
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
    if (uni.double_first_class.includes("一流大学A")) tags.push("双一流");
    else if (uni.double_first_class.includes("一流大学B")) tags.push("双一流");
    else tags.push("双一流");
  }
  return tags;
}

export function getExamZone(province: string): string {
  const zoneA = ["北京", "天津", "上海", "江苏", "浙江", "福建", "山东", "河南", "湖北", "湖南", "广东", "河北", "山西", "辽宁", "吉林", "黑龙江", "安徽", "江西", "重庆", "四川", "陕西"];
  return zoneA.includes(province) ? "A区" : "B区";
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

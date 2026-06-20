import { adminFetch } from "@/lib/admin/api/client";

import type { Paginated } from "@/lib/admin/api/users";



export type AdminSchool = {

  id: string;

  name: string;

  province: string | null;

  city: string | null;

  school_type: string | null;

  level_985: boolean;

  level_211: boolean;

  double_first_class: string | null;

  level: string | null;

  website: string | null;

  intro: string | null;

  updated_at: string;

};



export type AdminMajor = {

  id: string;

  name: string;

  code: string | null;

  college: string | null;

  subject_category: string | null;

  degree_type: string | null;

  study_mode: string | null;

  university_id: string;

  updated_at: string;

};



export type AdminCollege = {

  id: string;

  name: string;

  official_site: string | null;

  university_id: string;

  updated_at: string;

};



export async function fetchAdminColleges(params: {

  page?: number;

  pageSize?: number;

  q?: string;

}) {

  const sp = new URLSearchParams();

  if (params.page) sp.set("page", String(params.page));

  if (params.pageSize) sp.set("page_size", String(params.pageSize));

  if (params.q) sp.set("q", params.q);

  return adminFetch<Paginated<AdminCollege>>(`/api/admin/colleges?${sp}`);

}



export async function fetchAdminSchools(params: {

  page?: number;

  pageSize?: number;

  q?: string;

}) {

  const sp = new URLSearchParams();

  if (params.page) sp.set("page", String(params.page));

  if (params.pageSize) sp.set("page_size", String(params.pageSize));

  if (params.q) sp.set("q", params.q);

  return adminFetch<Paginated<AdminSchool>>(`/api/admin/schools?${sp}`);

}



export async function fetchAdminMajors(params: {

  page?: number;

  pageSize?: number;

  q?: string;

}) {

  const sp = new URLSearchParams();

  if (params.page) sp.set("page", String(params.page));

  if (params.pageSize) sp.set("page_size", String(params.pageSize));

  if (params.q) sp.set("q", params.q);

  return adminFetch<Paginated<AdminMajor>>(`/api/admin/majors?${sp}`);

}



export type AdminAnnouncement = {

  id: string;

  university_id: string;

  title: string;

  publish_time: string;

  url: string;

  type: string;

  created_at: string;

};



export type AdminPdf = {

  id: string;

  file_name: string;

  file_type: string;

  file_path: string;

  file_size: number | null;

  source_url: string | null;

  school_id: string | null;

  created_at: string;

};



export type SyncLogsResponse = {

  meta: { revision: number; updated_at: string; note: string | null } | null;

  items: {

    id: string;

    university_id: string;

    url: string;

    title: string | null;

    page_type: string | null;

    status: string;

    last_fetch_time: string | null;

    updated_at: string;

  }[];

  total: number;

  page: number;

  pageSize: number;

};



export async function fetchAdminAnnouncements(params: {

  page?: number;

  pageSize?: number;

  q?: string;

}) {

  const sp = new URLSearchParams();

  if (params.page) sp.set("page", String(params.page));

  if (params.pageSize) sp.set("page_size", String(params.pageSize));

  if (params.q) sp.set("q", params.q);

  return adminFetch<Paginated<AdminAnnouncement>>(`/api/admin/schools/announcements?${sp}`);

}



export async function fetchAdminPdfs(params: {

  page?: number;

  pageSize?: number;

  q?: string;

}) {

  const sp = new URLSearchParams();

  if (params.page) sp.set("page", String(params.page));

  if (params.pageSize) sp.set("page_size", String(params.pageSize));

  if (params.q) sp.set("q", params.q);

  return adminFetch<Paginated<AdminPdf>>(`/api/admin/schools/pdfs?${sp}`);

}



export async function fetchSyncLogs(params: { page?: number; pageSize?: number }) {

  const sp = new URLSearchParams();

  if (params.page) sp.set("page", String(params.page));

  if (params.pageSize) sp.set("page_size", String(params.pageSize));

  return adminFetch<SyncLogsResponse>(`/api/admin/schools/sync-logs?${sp}`);

}



export type SchoolInput = {

  name: string;

  province?: string | null;

  city?: string | null;

  school_type?: string | null;

  level_985?: boolean;

  level_211?: boolean;

  double_first_class?: string | null;

  website?: string | null;

  intro?: string | null;

};



export type MajorInput = {

  university_id: string;

  name: string;

  code?: string | null;

  college?: string | null;

  subject_category?: string | null;

  degree_type?: string | null;

  study_mode?: string | null;

};



export type CollegeInput = {

  university_id: string;

  name: string;

  official_site?: string | null;

};



export async function createAdminSchool(body: SchoolInput) {

  return adminFetch<AdminSchool>("/api/admin/schools", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function updateAdminSchool(id: string, body: SchoolInput) {

  return adminFetch<AdminSchool>(`/api/admin/schools/${id}`, {

    method: "PATCH",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function createAdminMajor(body: MajorInput) {

  return adminFetch<AdminMajor>("/api/admin/majors", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function updateAdminMajor(

  id: string,

  body: Partial<Omit<MajorInput, "university_id">>

) {

  return adminFetch<AdminMajor>(`/api/admin/majors/${id}`, {

    method: "PATCH",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function createAdminCollege(body: CollegeInput) {

  return adminFetch<AdminCollege>("/api/admin/colleges", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function updateAdminCollege(

  id: string,

  body: Partial<Omit<CollegeInput, "university_id">>

) {

  return adminFetch<AdminCollege>(`/api/admin/colleges/${id}`, {

    method: "PATCH",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function fetchUniversityOptions(q = "") {

  const res = await fetchAdminSchools({ page: 1, pageSize: 100, q });

  return res?.items ?? [];

}



export type AnnouncementInput = {

  university_id: string;

  title: string;

  publish_time: string;

  url: string;

  type?: string | null;

  content?: string | null;

};



export type PdfInput = {

  file_name: string;

  file_path: string;

  school_id?: string | null;

  file_type?: string | null;

  file_size?: number | null;

  source_url?: string | null;

};



export async function createAdminAnnouncement(body: AnnouncementInput) {

  return adminFetch<AdminAnnouncement>("/api/admin/schools/announcements", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function updateAdminAnnouncement(

  id: string,

  body: Partial<Omit<AnnouncementInput, "university_id">>

) {

  return adminFetch<AdminAnnouncement>(`/api/admin/schools/announcements/${id}`, {

    method: "PATCH",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function deleteAdminAnnouncement(id: string) {

  return adminFetch<{ id: string }>(`/api/admin/schools/announcements/${id}`, {

    method: "DELETE",

  });

}



export async function createAdminPdf(body: PdfInput) {

  return adminFetch<AdminPdf>("/api/admin/schools/pdfs", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function updateAdminPdf(id: string, body: Partial<PdfInput>) {

  return adminFetch<AdminPdf>(`/api/admin/schools/pdfs/${id}`, {

    method: "PATCH",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify(body),

  });

}



export async function deleteAdminPdf(id: string) {

  return adminFetch<{ id: string }>(`/api/admin/schools/pdfs/${id}`, {

    method: "DELETE",

  });

}



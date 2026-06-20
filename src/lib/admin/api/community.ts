import { adminFetch } from "@/lib/admin/api/client";
import type { Paginated } from "@/lib/admin/api/users";

export type AdminPost = {
  id: string;
  title: string;
  post_type: string;
  subject_category: string;
  view_count: number;
  favorite_count: number;
  comment_count: number;
  is_hidden: boolean;
  created_at: string;
  author_id: string;
};

export async function fetchAdminPosts(params: {
  page?: number;
  pageSize?: number;
  q?: string;
}) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  if (params.q) sp.set("q", params.q);
  return adminFetch<Paginated<AdminPost>>(`/api/admin/community/posts?${sp}`);
}

export type AdminComment = {
  id: string;
  post_id: string;
  author_id: string;
  content: string;
  parent_id: string | null;
  created_at: string;
};

export type AdminReport = {
  id: string;
  title: string;
  author_id: string;
  is_hidden: boolean;
  created_at: string;
  comment_count?: number;
  favorite_count?: number;
  reason?: string;
  status?: string;
};

export async function fetchAdminComments(params: {
  page?: number;
  pageSize?: number;
  q?: string;
}) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  if (params.q) sp.set("q", params.q);
  return adminFetch<Paginated<AdminComment>>(`/api/admin/community/comments?${sp}`);
}

export async function fetchAdminModeration(params: { page?: number; pageSize?: number }) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  return adminFetch<Paginated<AdminReport>>(`/api/admin/community/moderation?${sp}`);
}

export async function fetchAdminReports(params: { page?: number; pageSize?: number }) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  return adminFetch<Paginated<AdminReport>>(`/api/admin/community/reports?${sp}`);
}

export type PostModerateAction = "hide" | "show" | "delete";

export async function moderatePost(postId: string, action: PostModerateAction) {
  return adminFetch<{ id: string }>(`/api/admin/community/posts/${postId}/moderate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
}

export async function deleteAdminComment(commentId: string) {
  return adminFetch<{ id: string; deleted: boolean }>(
    `/api/admin/community/comments/${commentId}`,
    { method: "DELETE" }
  );
}

export type AdminPostDetail = AdminPost & {
  content: string;
  attachments: unknown;
  author?: { id: string; nickname: string | null; email: string | null; display_id: string | null };
  recent_comments: { id: string; content: string; author_id: string; created_at: string }[];
};

export async function fetchAdminPostDetail(postId: string) {
  return adminFetch<AdminPostDetail>(`/api/admin/community/posts/${postId}`);
}

export async function batchModeratePosts(postIds: string[], action: PostModerateAction) {
  return adminFetch<{ success: string[]; failed: string[]; action: string }>(
    "/api/admin/community/posts/batch-moderate",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ post_ids: postIds, action }),
    }
  );
}

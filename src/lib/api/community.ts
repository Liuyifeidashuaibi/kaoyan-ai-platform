import { apiFetch, ApiError } from "@/lib/api/client";
import { getAuthHeaders } from "@/lib/api/auth-fetch";
import type {
  CommunityComment,
  CommunityPost,
  CommunitySearchResult,
  CommunityUser,
  PaginatedPosts,
  WrongQuestion,
} from "@/lib/api/types";
import type { PostType } from "@/lib/community/constants";

type ListPostsParams = {
  sort?: "latest" | "hot";
  page?: number;
  post_type?: PostType;
  subject_category?: string;
  author_id?: string;
  q?: string;
};

function buildQuery(params: Record<string, string | number | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  return apiFetch<T>(path, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init?.headers ?? {}),
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
    },
  });
}

export async function listPosts(params: ListPostsParams = {}) {
  const headers = await getAuthHeaders();
  return apiFetch<PaginatedPosts>(
    `/api/community/posts${buildQuery(params as Record<string, string | number | undefined>)}`,
    { headers }
  );
}

export async function getPost(postId: string) {
  const headers = await getAuthHeaders();
  return apiFetch<CommunityPost>(`/api/community/posts/${postId}`, { headers });
}

export async function createPost(body: {
  post_type: PostType;
  subject_category: string;
  grade: string;
  university_id?: string | null;
  university_name?: string | null;
  title: string;
  content: string;
  attachments?: { url: string; name: string; mime_type: string }[];
}) {
  return authFetch<CommunityPost>("/api/community/posts", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updatePost(
  postId: string,
  body: { title?: string; content?: string; is_hidden?: boolean }
) {
  return authFetch<CommunityPost>(`/api/community/posts/${postId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deletePost(postId: string) {
  return authFetch<null>(`/api/community/posts/${postId}`, { method: "DELETE" });
}

export async function listComments(postId: string) {
  return apiFetch<CommunityComment[]>(`/api/community/posts/${postId}/comments`);
}

export async function createComment(
  postId: string,
  content: string,
  parentId?: string | null
) {
  return authFetch<CommunityComment>(`/api/community/posts/${postId}/comments`, {
    method: "POST",
    body: JSON.stringify({ content, parent_id: parentId ?? null }),
  });
}

export async function toggleFavorite(postId: string) {
  return authFetch<{ favorited: boolean }>(
    `/api/community/posts/${postId}/favorite`,
    { method: "POST" }
  );
}

export async function listFavorites(page = 1) {
  return authFetch<PaginatedPosts>(`/api/community/favorites?page=${page}`);
}

export async function followUser(targetId: string) {
  return authFetch<{ following: boolean }>(
    `/api/community/users/${targetId}/follow`,
    { method: "POST" }
  );
}

export async function unfollowUser(targetId: string) {
  return authFetch<{ following: boolean }>(
    `/api/community/users/${targetId}/follow`,
    { method: "DELETE" }
  );
}

export async function listFollowing() {
  return authFetch<CommunityUser[]>("/api/community/following");
}

export async function listFollowers() {
  return authFetch<CommunityUser[]>("/api/community/followers");
}

export async function getUserProfile(identifier: string) {
  const headers = await getAuthHeaders();
  return apiFetch<CommunityUser>(`/api/community/users/${identifier}`, { headers });
}

export async function getMyProfile() {
  return authFetch<CommunityUser>("/api/community/users/me");
}

export async function updateMyProfile(body: {
  subject_category?: string;
  avatar_url?: string;
}) {
  return authFetch<CommunityUser>("/api/community/users/me", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function searchCommunity(q: string) {
  return apiFetch<CommunitySearchResult>(
    `/api/community/search${buildQuery({ q })}`
  );
}

export async function uploadCommunityAttachment(file: File) {
  const form = new FormData();
  form.append("file", file);
  const authHeaders = await getAuthHeaders();
  const base = await import("@/lib/config/api").then((m) => m.ensureApiBaseUrl());
  const res = await fetch(`${await base}/api/community/upload`, {
    method: "POST",
    headers: authHeaders,
    body: form,
  });
  const json = (await res.json()) as {
    success: boolean;
    data: { url: string; name: string; mime_type: string };
    message: string;
  };
  if (!res.ok || !json.success) {
    throw new ApiError(json.message || "上传失败", res.status);
  }
  return json.data;
}

export async function addPostToWrongQuestions(postId: string) {
  return authFetch<WrongQuestion>(
    `/api/community/posts/${postId}/add-to-wrong-questions`,
    { method: "POST" }
  );
}

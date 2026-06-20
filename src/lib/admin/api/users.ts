import { adminFetch } from "@/lib/admin/api/client";

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};

export type AdminUser = {
  id: string;
  email: string | null;
  nickname: string | null;
  avatar_url: string | null;
  display_id: string | null;
  created_at: string;
};

export async function fetchAdminUsers(params: {
  page?: number;
  pageSize?: number;
  q?: string;
}) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  if (params.q) sp.set("q", params.q);
  return adminFetch<Paginated<AdminUser>>(`/api/admin/users?${sp}`);
}

export type UserFollow = {
  follower_id: string;
  following_id: string;
  created_at: string;
};

export type UserFavorite = {
  user_id: string;
  post_id: string;
  created_at: string;
};

export type UserPostStat = {
  author_id: string;
  post_count: number;
};

export type AdminUserDetail = AdminUser & {
  bio?: string | null;
  target_year?: number | null;
  stats: {
    posts: number;
    followers: number;
    following: number;
    favorites: number;
  };
};

export async function fetchAdminUserDetail(userId: string) {
  return adminFetch<AdminUserDetail>(`/api/admin/users/${userId}`);
}

export async function fetchAdminFollows(params: { page?: number; pageSize?: number }) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  return adminFetch<Paginated<UserFollow>>(`/api/admin/users/follows?${sp}`);
}

export async function fetchAdminFavorites(params: { page?: number; pageSize?: number }) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  return adminFetch<Paginated<UserFavorite>>(`/api/admin/users/favorites?${sp}`);
}

export async function fetchAdminPostStats(params: { page?: number; pageSize?: number }) {
  const sp = new URLSearchParams();
  if (params.page) sp.set("page", String(params.page));
  if (params.pageSize) sp.set("page_size", String(params.pageSize));
  return adminFetch<Paginated<UserPostStat>>(`/api/admin/users/post-stats?${sp}`);
}

export async function fetchAdminUserPosts(userId: string, page = 1) {
  return adminFetch<Paginated<{ id: string; title: string; post_type: string; is_hidden: boolean; created_at: string; comment_count: number; favorite_count: number }>>(
    `/api/admin/users/${userId}/posts?page=${page}&page_size=10`
  );
}

export async function fetchAdminUserFollowsFor(userId: string, page = 1) {
  return adminFetch<Paginated<{ following_id: string; created_at: string }>>(
    `/api/admin/users/${userId}/follows?page=${page}&page_size=10`
  );
}

export async function fetchAdminUserFavoritesFor(userId: string, page = 1) {
  return adminFetch<Paginated<{ post_id: string; created_at: string }>>(
    `/api/admin/users/${userId}/favorites?page=${page}&page_size=10`
  );
}

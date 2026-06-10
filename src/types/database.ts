export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export type Database = {
  public: {
    Tables: {
      users: {
        Row: {
          id: string;
          email: string | null;
          nickname: string | null;
          avatar_url: string | null;
          bio: string | null;
          target_year: number | null;
          target_school_id: string | null;
          target_major_id: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id: string;
          email?: string | null;
          nickname?: string | null;
          avatar_url?: string | null;
          bio?: string | null;
          target_year?: number | null;
          target_school_id?: string | null;
          target_major_id?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          email?: string | null;
          nickname?: string | null;
          avatar_url?: string | null;
          bio?: string | null;
          target_year?: number | null;
          target_school_id?: string | null;
          target_major_id?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      schools: {
        Row: {
          id: string;
          name: string;
          code: string | null;
          province: string | null;
          city: string | null;
          level: string | null;
          website: string | null;
          description: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          code?: string | null;
          province?: string | null;
          city?: string | null;
          level?: string | null;
          website?: string | null;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          name?: string;
          code?: string | null;
          province?: string | null;
          city?: string | null;
          level?: string | null;
          website?: string | null;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      majors: {
        Row: {
          id: string;
          school_id: string;
          name: string;
          code: string | null;
          category: string | null;
          degree_type: string | null;
          description: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          school_id: string;
          name: string;
          code?: string | null;
          category?: string | null;
          degree_type?: string | null;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          school_id?: string;
          name?: string;
          code?: string | null;
          category?: string | null;
          degree_type?: string | null;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      study_records: {
        Row: {
          id: string;
          user_id: string;
          subject: string;
          duration_minutes: number;
          pomodoro_count: number;
          notes: string | null;
          studied_at: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          subject: string;
          duration_minutes?: number;
          pomodoro_count?: number;
          notes?: string | null;
          studied_at?: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          subject?: string;
          duration_minutes?: number;
          pomodoro_count?: number;
          notes?: string | null;
          studied_at?: string;
          created_at?: string;
        };
      };
      chat_messages: {
        Row: {
          id: string;
          user_id: string;
          session_id: string;
          role: "user" | "assistant" | "system";
          content: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          session_id?: string;
          role: "user" | "assistant" | "system";
          content: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          session_id?: string;
          role?: "user" | "assistant" | "system";
          content?: string;
          created_at?: string;
        };
      };
      admission_data: {
        Row: {
          id: string;
          school_id: string;
          major_id: string;
          year: number;
          enrollment_count: number | null;
          applicant_count: number | null;
          min_score: number | null;
          max_score: number | null;
          avg_score: number | null;
          notes: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          school_id: string;
          major_id: string;
          year: number;
          enrollment_count?: number | null;
          applicant_count?: number | null;
          min_score?: number | null;
          max_score?: number | null;
          avg_score?: number | null;
          notes?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          school_id?: string;
          major_id?: string;
          year?: number;
          enrollment_count?: number | null;
          applicant_count?: number | null;
          min_score?: number | null;
          max_score?: number | null;
          avg_score?: number | null;
          notes?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
  };
};

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
      universities: {
        Row: {
          id: string;
          name: string;
          code: string | null;
          logo_url: string | null;
          province: string | null;
          city: string | null;
          level_985: boolean;
          level_211: boolean;
          double_first_class: string | null;
          school_type: string | null;
          intro: string | null;
          description: string | null;
          address: string | null;
          website: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          code?: string | null;
          logo_url?: string | null;
          province?: string | null;
          city?: string | null;
          level_985?: boolean;
          level_211?: boolean;
          double_first_class?: string | null;
          school_type?: string | null;
          intro?: string | null;
          description?: string | null;
          address?: string | null;
          website?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          name?: string;
          code?: string | null;
          logo_url?: string | null;
          province?: string | null;
          city?: string | null;
          level_985?: boolean;
          level_211?: boolean;
          double_first_class?: string | null;
          school_type?: string | null;
          intro?: string | null;
          description?: string | null;
          address?: string | null;
          website?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      majors: {
        Row: {
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
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          university_id: string;
          college?: string | null;
          name: string;
          code?: string | null;
          degree_type?: string | null;
          study_mode?: string | null;
          exam_type?: string | null;
          enrollment_count?: number | null;
          subject_category?: string | null;
          first_discipline?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          university_id?: string;
          college?: string | null;
          name?: string;
          code?: string | null;
          degree_type?: string | null;
          study_mode?: string | null;
          exam_type?: string | null;
          enrollment_count?: number | null;
          subject_category?: string | null;
          first_discipline?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      scores: {
        Row: {
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
          created_at: string;
        };
        Insert: {
          id?: string;
          university_id: string;
          major_id: string;
          year: number;
          total_score: number;
          politics_score: number;
          english_score: number;
          professional1_score?: number | null;
          professional2_score?: number | null;
          line_diff?: number | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          university_id?: string;
          major_id?: string;
          year?: number;
          total_score?: number;
          politics_score?: number;
          english_score?: number;
          professional1_score?: number | null;
          professional2_score?: number | null;
          line_diff?: number | null;
          created_at?: string;
        };
      };
      announcements: {
        Row: {
          id: string;
          university_id: string;
          title: string;
          publish_time: string;
          url: string;
          type: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          university_id: string;
          title: string;
          publish_time: string;
          url: string;
          type: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          university_id?: string;
          title?: string;
          publish_time?: string;
          url?: string;
          type?: string;
          created_at?: string;
        };
      };
      recommendations: {
        Row: {
          id: string;
          university_id: string;
          title: string;
          type: string;
          status: string;
          start_time: string | null;
          end_time: string | null;
          url: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          university_id: string;
          title: string;
          type: string;
          status: string;
          start_time?: string | null;
          end_time?: string | null;
          url: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          university_id?: string;
          title?: string;
          type?: string;
          status?: string;
          start_time?: string | null;
          end_time?: string | null;
          url?: string;
          created_at?: string;
        };
      };
      adjustments: {
        Row: {
          id: string;
          university_id: string;
          major_id: string | null;
          year: number;
          major_name: string;
          quota: number | null;
          requirements: string | null;
          contact: string | null;
          url: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          university_id: string;
          major_id?: string | null;
          year: number;
          major_name: string;
          quota?: number | null;
          requirements?: string | null;
          contact?: string | null;
          url?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          university_id?: string;
          major_id?: string | null;
          year?: number;
          major_name?: string;
          quota?: number | null;
          requirements?: string | null;
          contact?: string | null;
          url?: string | null;
          created_at?: string;
        };
      };
      study_subjects: {
        Row: {
          id: string;
          user_id: string;
          name: string;
          color: string;
          total_seconds: number;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          name: string;
          color: string;
          total_seconds?: number;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          name?: string;
          color?: string;
          total_seconds?: number;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: "study_subjects_user_id_fkey";
            columns: ["user_id"];
            isOneToOne: false;
            referencedRelation: "users";
            referencedColumns: ["id"];
          },
        ];
      };
      study_timer_sessions: {
        Row: {
          id: string;
          user_id: string;
          subject_id: string;
          mode: "stopwatch" | "countdown";
          duration_seconds: number;
          started_at: string;
          ended_at: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          subject_id: string;
          mode: "stopwatch" | "countdown";
          duration_seconds: number;
          started_at: string;
          ended_at: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          subject_id?: string;
          mode?: "stopwatch" | "countdown";
          duration_seconds?: number;
          started_at?: string;
          ended_at?: string;
          created_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: "study_timer_sessions_user_id_fkey";
            columns: ["user_id"];
            isOneToOne: false;
            referencedRelation: "users";
            referencedColumns: ["id"];
          },
          {
            foreignKeyName: "study_timer_sessions_subject_id_fkey";
            columns: ["subject_id"];
            isOneToOne: false;
            referencedRelation: "study_subjects";
            referencedColumns: ["id"];
          },
        ];
      };
    };
    Views: Record<string, never>;
    Functions: {
      increment_subject_total_seconds: {
        Args: {
          p_subject_id: string;
          p_user_id: string;
          p_delta_seconds: number;
        };
        Returns: undefined;
      };
    };
    Enums: Record<string, never>;
  };
};

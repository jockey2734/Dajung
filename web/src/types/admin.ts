// Mirrors api/app/schemas/admin.py + admin_accounts.py exactly (S18/S19).
// api/app/schemas/admin.py + admin_accounts.py를 그대로 반영 (S18/S19).

export type Role = "owner" | "president" | "staff";

export interface AdminUserOut {
  id: string;
  name: string;
  email: string;
  title: string | null;
  role: Role;
  status: "active" | "suspended" | "deleted";
  expires_at: string | null;
  last_seen_at: string | null;
  must_change_password: boolean;
}

export interface PresidentUserOut {
  id: string;
  email: string;
  name: string;
  role: Role;
  title: string | null;
  expires_at: string | null;
}

export interface PresidentTransferOut {
  id: string;
  from_user: PresidentUserOut | null;
  to_user: PresidentUserOut;
  actor: PresidentUserOut;
  note: string | null;
  created_at: string;
}

export interface TemporaryPasswordOut {
  user_id: string;
  temporary_password: string;
}

// S19 backend renders status in Korean already — the FE maps colors only.
// S19 백엔드가 상태를 한국어로 반환 — FE는 색만 입힌다.
export interface InvitationOut {
  id: string;
  note: string | null;
  expires_at: string;
  status: "활성" | "만료" | "사용됨";
  used_at: string | null;
}

export interface InvitationCreatedOut {
  id: string;
  code: string;
  note: string | null;
  expires_at: string;
}

export interface RosterOut {
  id: string;
  semester: string;
  department: string;
  member_name: string;
  position: string | null;
  user_id: string | null;
  created_at: string;
}

export interface DocumentUploadOut {
  folder: string;
  filename: string;
  status: "processing";
}

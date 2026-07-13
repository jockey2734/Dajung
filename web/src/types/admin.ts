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

export type PantryKind = "tea" | "coffee" | "other";
export type PantryRemainingPct = 0 | 25 | 50 | 75 | 100;
export type SortField = "updated_at" | "name" | "remaining_pct";
export type OrderField = "asc" | "desc";

export interface PantryUserOut {
  id: string;
  name: string;
}

export interface PantryItemOut {
  id: string;
  name: string;
  kind: PantryKind;
  remaining_pct: PantryRemainingPct;
  capacity_g: number | null;
  estimated_g: number | null;
  note: string | null;
  updated_by: PantryUserOut;
  created_at: string;
  updated_at: string;
}

export interface CoffeeAlertOut {
  alert: boolean;
  total_estimated_g: number;
  threshold_g: number;
}

export interface PantryListResponse {
  items: PantryItemOut[];
  coffee_alert: CoffeeAlertOut;
}

export interface PantryItemResponse {
  item: PantryItemOut;
  coffee_alert: CoffeeAlertOut;
}

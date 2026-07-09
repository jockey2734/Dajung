"use client";

import { useState, useEffect, useCallback } from "react";
import type { 
  PantryItemOut, 
  CoffeeAlertOut, 
  PantryKind, 
  PantryRemainingPct 
} from "@/types/pantry";

export type SortField = "updated_at" | "name" | "remaining_pct";
export type OrderField = "asc" | "desc";

export function usePantry() {
  const [items, setItems] = useState<PantryItemOut[]>([]);
  const [alert, setAlert] = useState<CoffeeAlertOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [sort, setSort] = useState<SortField>("updated_at");
  const [order, setOrder] = useState<OrderField>("desc");

  const fetchPantry = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/pantry?sort=${sort}&order=${order}`);
      if (!res.ok) throw new Error("Failed to fetch pantry items");
      const data = await res.json();
      setItems(data.items);
      setAlert(data.coffee_alert);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [sort, order]);

  useEffect(() => {
    fetchPantry();
  }, [fetchPantry]);

  const updateItem = async (id: string, updates: Partial<PantryItemOut>) => {
    // Optimistic update
    const previousItems = [...items];
    setItems((prev) => 
      prev.map((item) => (item.id === id ? { ...item, ...updates } : item))
    );

    try {
      const res = await fetch(`/api/pantry/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error("Update failed");
      
      const data = await res.json();
      // Update with server response (which might have updated estimated_g and updated_by)
      setItems((prev) => prev.map((item) => (item.id === id ? data.item : item)));
      setAlert(data.coffee_alert);
    } catch (err) {
      // Rollback
      setItems(previousItems);
      throw err;
    }
  };

  const addItem = async (newItem: { name: string; kind: PantryKind; remaining_pct: PantryRemainingPct; capacity_g: number | null; note: string | null }) => {
    try {
      const res = await fetch("/api/pantry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newItem),
      });
      if (!res.ok) throw new Error("Add failed");
      
      const data = await res.json();
      // Add to state and re-sort by refetching
      await fetchPantry(); 
    } catch (err) {
      throw err;
    }
  };

  const deleteItem = async (id: string) => {
    // Optimistic delete
    const previousItems = [...items];
    setItems((prev) => prev.filter((item) => item.id !== id));

    try {
      const res = await fetch(`/api/pantry/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Delete failed");
      
      // Need to fetch to get updated coffee alert since delete doesn't return coffee_alert
      await fetchPantry();
    } catch (err) {
      setItems(previousItems);
      throw err;
    }
  };

  return {
    items,
    alert,
    loading,
    error,
    sort,
    order,
    setSort,
    setOrder,
    updateItem,
    addItem,
    deleteItem,
    refresh: fetchPantry
  };
}

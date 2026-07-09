"use client";

import { useEffect, useState } from "react";
import { usePantry } from "@/lib/use-pantry";
import { CoffeeAlertBanner } from "./coffee-alert-banner";
import { PantryTable } from "./pantry-table";
import { PantryCardList } from "./pantry-card-list";

export function PantryClient() {
  const { 
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
    deleteItem 
  } = usePantry();

  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const handleSortChange = (field: "updated_at" | "name" | "remaining_pct") => {
    if (sort === field) {
      setOrder(order === "asc" ? "desc" : "asc");
    } else {
      setSort(field);
      setOrder("desc");
    }
  };

  if (loading && items.length === 0) {
    return <div className="p-8 text-center text-taupe">로딩 중...</div>;
  }

  return (
    <div className="flex flex-col gap-4 w-full max-w-5xl mx-auto p-4 sm:p-6 pb-20">
      <div className="flex justify-between items-end mb-2">
        <h1 className="text-heading-2 font-semibold text-ink tracking-tight">다정 찻장</h1>
      </div>

      <CoffeeAlertBanner alert={alert} />

      {error && (
        <div className="bg-semantic-error-soft text-semantic-error p-3 rounded-md text-sm mb-4 border border-semantic-error/20">
          오류가 발생했습니다: {error}
        </div>
      )}

      {isMobile ? (
        <PantryCardList 
          items={items} 
          sort={sort} 
          order={order} 
          onSortChange={handleSortChange}
          onUpdate={updateItem}
          onDelete={deleteItem}
          onAdd={addItem}
        />
      ) : (
        <PantryTable 
          items={items} 
          sort={sort} 
          order={order} 
          onSortChange={handleSortChange}
          onUpdate={updateItem}
          onDelete={deleteItem}
          onAdd={addItem}
        />
      )}
    </div>
  );
}

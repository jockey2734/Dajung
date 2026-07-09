"use client";

import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";

import type { PantryItemOut, PantryKind, PantryRemainingPct, SortField, OrderField } from "@/types/pantry";

function RemainingSegmentBar({ pct, isCoffee }: { pct: PantryRemainingPct, isCoffee: boolean }) {
  const blocks = pct / 25;
  const isWarning = isCoffee && pct <= 25;
  const isDanger = isCoffee && pct === 0;
  
  const colorClass = isDanger 
    ? "bg-semantic-error" 
    : isWarning 
      ? "bg-semantic-warning" 
      : "bg-espresso";
      
  return (
    <div className="flex gap-[2px]">
      {[1, 2, 3, 4, 5].map(i => (
        <div 
          key={i} 
          className={`h-2 w-4 rounded-sm ${i <= blocks ? colorClass : 'bg-muted-token'}`} 
        />
      ))}
    </div>
  )
}

function KindBadge({ kind }: { kind: PantryKind }) {
  const label = kind === "coffee" ? "커피" : kind === "tea" ? "차" : "기타";
  const bgClass = kind === "coffee" ? "bg-espresso text-cream" : kind === "tea" ? "bg-tea-green-soft text-tea-green" : "bg-surface text-taupe border border-hairline";
  
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-caption-bold ${bgClass}`}>
      {label}
    </span>
  );
}

interface PantryCardListProps {
  items: PantryItemOut[];
  sort: SortField;
  order: OrderField;
  onSortChange: (field: SortField) => void;
  onUpdate: (id: string, updates: Partial<PantryItemOut>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onAdd: (item: { name: string; kind: PantryKind; remaining_pct: PantryRemainingPct; capacity_g: number | null; note: string | null }) => Promise<void>;
}

export function PantryCardList({ items, sort, order, onSortChange, onUpdate, onDelete, onAdd }: PantryCardListProps) {
  const [editingItem, setEditingItem] = useState<PantryItemOut | null>(null);
  const [adding, setAdding] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Edit / Add form state
  const [formName, setFormName] = useState("");
  const [formKind, setFormKind] = useState<PantryKind>("coffee");
  const [formPct, setFormPct] = useState<PantryRemainingPct>(100);
  const [formCapacity, setFormCapacity] = useState("");
  const [formNote, setFormNote] = useState("");

  const openEdit = (item: PantryItemOut) => {
    setEditingItem(item);
    setFormName(item.name);
    setFormKind(item.kind);
    setFormPct(item.remaining_pct);
    setFormCapacity(item.capacity_g?.toString() || "");
    setFormNote(item.note || "");
  };

  const openAdd = () => {
    setAdding(true);
    setFormName("");
    setFormKind("coffee");
    setFormPct(100);
    setFormCapacity("");
    setFormNote("");
  };

  const handleSave = async () => {
    if (!formName.trim()) return;
    
    const capacity_g = formCapacity ? parseInt(formCapacity, 10) : null;
    
    if (editingItem) {
      await onUpdate(editingItem.id, {
        name: formName,
        kind: formKind,
        remaining_pct: formPct,
        capacity_g,
        note: formNote || null
      });
      setEditingItem(null);
    } else if (adding) {
      await onAdd({
        name: formName,
        kind: formKind,
        remaining_pct: formPct,
        capacity_g,
        note: formNote || null
      });
      setAdding(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center px-1">
        <select 
          value={sort}
          onChange={(e) => onSortChange(e.target.value as SortField)}
          className="bg-transparent text-sm text-taupe font-medium outline-none"
        >
          <option value="updated_at">최근수정순</option>
          <option value="name">이름순</option>
          <option value="remaining_pct">잔량순</option>
        </select>
        <Button size="sm" onClick={openAdd} className="bg-espresso text-cream hover:bg-espresso/90">
          + 추가
        </Button>
      </div>

      <div className="grid gap-3">
        {items.map(item => (
          <div 
            key={item.id}
            onClick={() => openEdit(item)}
            className="flex flex-col gap-2 p-3 rounded-lg border border-hairline bg-canvas shadow-sm cursor-pointer hover:border-input transition-colors"
          >
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-ink">{item.name}</span>
                <KindBadge kind={item.kind} />
              </div>
              <div className="flex items-center gap-2">
                <RemainingSegmentBar pct={item.remaining_pct} isCoffee={item.kind === "coffee"} />
                <span className="text-sm font-mono text-taupe">{item.remaining_pct}%</span>
              </div>
            </div>
            
            <div className="flex justify-between items-end mt-1">
              <div className="text-caption text-taupe line-clamp-1 flex-1 pr-4">
                {item.note || "-"}
              </div>
              <div className="text-micro text-sand whitespace-nowrap">
                {item.updated_by.name} · {formatDistanceToNow(new Date(item.updated_at), { locale: ko })} 전
              </div>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={!!editingItem || adding} onOpenChange={(open) => {
        if (!open) { setEditingItem(null); setAdding(false); }
      }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{editingItem ? "항목 수정" : "새 항목 추가"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <label className="text-right text-sm font-medium">이름</label>
              <Input 
                value={formName} 
                onChange={e => setFormName(e.target.value)} 
                className="col-span-3" 
                autoFocus
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <label className="text-right text-sm font-medium">종류</label>
              <select 
                value={formKind} 
                onChange={e => setFormKind(e.target.value as PantryKind)}
                className="col-span-3 h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="coffee">커피</option>
                <option value="tea">차</option>
                <option value="other">기타</option>
              </select>
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <label className="text-right text-sm font-medium">잔량</label>
              <select 
                value={formPct} 
                onChange={e => setFormPct(parseInt(e.target.value) as PantryRemainingPct)}
                className="col-span-3 h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value={100}>100%</option>
                <option value={75}>75%</option>
                <option value={50}>50%</option>
                <option value={25}>25%</option>
                <option value={0}>0%</option>
              </select>
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <label className="text-right text-sm font-medium">용량(g)</label>
              <Input 
                value={formCapacity} 
                onChange={e => setFormCapacity(e.target.value)} 
                className="col-span-3" 
                type="number"
                disabled={formKind !== "coffee"}
                placeholder="커피만 입력"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <label className="text-right text-sm font-medium">메모</label>
              <Input 
                value={formNote} 
                onChange={e => setFormNote(e.target.value)} 
                className="col-span-3" 
              />
            </div>
          </div>
          <DialogFooter className="flex justify-between items-center sm:justify-between">
            {editingItem ? (
              <Button 
                variant="ghost" 
                className="text-semantic-error hover:text-semantic-error hover:bg-semantic-error-soft px-2"
                onClick={() => { setDeleteId(editingItem.id); setEditingItem(null); }}
              >
                <Trash2 className="w-4 h-4 mr-2" /> 삭제
              </Button>
            ) : <div />}
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => { setEditingItem(null); setAdding(false); }}>취소</Button>
              <Button onClick={handleSave}>저장</Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>항목 삭제</DialogTitle>
            <DialogDescription>
              정말 이 항목을 삭제하시겠습니까?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>취소</Button>
            <Button variant="destructive" onClick={async () => {
              if (deleteId) await onDelete(deleteId);
              setDeleteId(null);
            }}>삭제</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
